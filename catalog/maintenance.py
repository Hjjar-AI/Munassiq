"""Idempotent content jobs and approved account-deletion stewardship."""
import logging
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from accounts.models import MaintenanceRun
from accounts.services import audit
from .files import path_for
from .models import Asset, EventView, Item, Occurrence, Registration, RegistrationTransition
from .registration import ACTIVE, cancel_occurrence, locked_occurrence, promote, transition
from .services import archive_time


def remove_asset_file(asset):
    try:
        path_for(asset).unlink(missing_ok=True)
    except OSError:
        logging.getLogger(__name__).error('Directory media deletion deferred to orphan cleanup')


def prepare_account_deletion(user):
    """Called inside the account-deletion transaction, before cascade removal."""
    owned = list(Item.objects.select_for_update().filter(owner=user).select_related('published_revision'))
    for item in owned:
        if not item.published_revision_id:
            item.delete()
            continue
        # Approved policy: retain published content with no personal author/contact attribution.
        for revision in item.revisions.all():
            detail = dict(revision.payload)
            if detail.get('contact_scope', 'personal') == 'personal':
                for field in ('phone', 'contact_person', 'registration_contact', 'registration_url'):
                    if field in detail:
                        detail[field] = ''
            revision.payload = detail
            revision.author = None
            revision.save(update_fields=['payload', 'author'])
        item.owner = None
        item.save(update_fields=['owner'])
    rows = list(Registration.objects.filter(user=user).select_related('occurrence'))
    for record in rows:
        occurrence = locked_occurrence(record.occurrence_id)
        record.occurrence = occurrence
        if record.state in ACTIVE:
            transition(record, 'cancelled', 'account.deleted')
        # The account export/delete requirement removes the person's own history.
        RegistrationTransition.objects.filter(registration=record).delete()
        record.delete()
        promote(occurrence)


def run_jobs():
    run = MaintenanceRun.objects.create(name='catalog.lifecycle')
    now, processed = timezone.now(), 0
    for occurrence_id in Occurrence.objects.order_by('event_id', 'pk').values_list('pk', flat=True):
        with transaction.atomic():
            occurrence = locked_occurrence(occurrence_id)
            if now >= archive_time(occurrence) and not occurrence.archived_at:
                occurrence.archived_at = archive_time(occurrence)
                occurrence.save(update_fields=['archived_at'])
                processed += 1
            for record in occurrence.registrations.filter(state='pending_reconfirm', reconfirm_deadline__lte=now).select_related('user', 'occurrence'):
                transition(record, 'cancelled', 'reconfirm.expired')
                processed += 1
            promote(occurrence)
    with transaction.atomic():
        for item in Item.objects.select_for_update().filter(status='soft_deleted', deleted_at__lte=now-timedelta(days=3)):
            audit(None, 'item.hard_delete', item, kind=item.kind)
            item.delete()
            processed += 1
        # Attachments still referenced by any surviving revision remain on disk.
        for asset in Asset.objects.filter(revisions__isnull=True, organizerprofile__isnull=True, created_at__lte=now-timedelta(days=1)):
            transaction.on_commit(lambda asset=asset: remove_asset_file(asset))
            asset.delete()
        EventView.objects.filter(day__lt=now.date()-timedelta(days=2)).delete()
    # Interrupted writes/deletions can leave unreferenced disk files. Never inspect credentials here.
    references = set(Asset.objects.values_list('name', flat=True))
    for path in Path(settings.MEDIA_ROOT).iterdir():
        if path.is_file() and path.name not in references and path.stat().st_mtime < (now-timedelta(hours=1)).timestamp():
            try:
                path.unlink()
            except OSError:
                logging.getLogger(__name__).error('Directory media orphan deletion deferred')
    run.finished_at, run.processed = timezone.now(), processed
    run.save(update_fields=['finished_at', 'processed'])
    return processed
