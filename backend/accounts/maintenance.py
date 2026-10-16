"""Idempotent account cleanup, with directory stewardship and released seats."""
import logging
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .credentials import credential_path
from .models import EmailMessage, EmailToken, LoginBucket, MaintenanceRun, OrganizerRequest, Session, User


def remove_private_file(name):
    try:
        credential_path(name).unlink(missing_ok=True)
    except OSError:
        # Do not log document contents or names. A later cleanup retries orphans.
        logging.getLogger(__name__).error('Private credential deletion deferred to cleanup')


def delete_user(user):
    from catalog.maintenance import prepare_account_deletion
    from core.recovery import record_deletion
    record_deletion("user", user)
    prepare_account_deletion(user)
    names = list(OrganizerRequest.objects.filter(user=user).exclude(credential_name='').values_list('credential_name', flat=True))
    user.delete()
    for name in names:
        transaction.on_commit(lambda name=name: remove_private_file(name))


def cleanup_accounts():
    now = timezone.now()
    run = MaintenanceRun.objects.create(name='accounts.cleanup')
    with transaction.atomic():
        stale = list(User.objects.select_for_update().filter(verified_at=None, created_at__lte=now-timedelta(days=7)))
        for user in stale:
            delete_user(user)
        EmailToken.objects.filter(expires_at__lte=now).delete()
        EmailMessage.objects.filter(expires_at__lte=now).delete()
        Session.objects.filter(expires_at__lte=now).delete()
        LoginBucket.objects.filter(window_start__lt=now-timedelta(days=2)).delete()
    # Old unreferenced private documents may remain after interrupted deletion.
    # Grace period protects an upload whose database transaction is still committing.
    references = set(OrganizerRequest.objects.exclude(credential_name='').values_list('credential_name', flat=True))
    for path in Path(settings.PRIVATE_CREDENTIAL_ROOT).iterdir():
        if path.is_file() and path.name not in references and path.stat().st_mtime < (now-timedelta(hours=1)).timestamp():
            remove_private_file(path.name)
    run.finished_at, run.processed = timezone.now(), len(stale)
    run.save(update_fields=['finished_at', 'processed'])
    return len(stale)
