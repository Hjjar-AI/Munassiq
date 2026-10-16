"""Content operations shared by REST and the future dashboard."""
import calendar
import json
from datetime import datetime, time, timedelta, timezone as utc
from zoneinfo import ZoneInfo
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from accounts.services import audit
from .models import Item, Notice, Occurrence, Revision
from .search import normalize, similar_names
from .serializers import EventSerializer, ServiceSerializer

PUBLIC_STATUSES = ['approved', 'pending_changes']


def is_reviewer(actor):
    return bool(actor and actor.is_active and (actor.has_role('moderator') or actor.has_role('admin')))


def require_reviewer(actor):
    if not is_reviewer(actor):
        raise PermissionDenied('Moderator or administrator role required.')


def require_creator(actor):
    if not actor or not actor.has_role('organizer'):
        raise PermissionDenied('Organizer role required, including for moderators and administrators.')


def public_items(kind=None):
    query = Item.objects.filter(status__in=PUBLIC_STATUSES, published_revision__isnull=False)
    return query.filter(kind=kind) if kind else query


def archive_time(occurrence):
    zone = ZoneInfo(occurrence.time_zone)
    end = occurrence.ends_at.astimezone(zone)
    return datetime.combine(end.date()+timedelta(days=1), time.min, tzinfo=zone).astimezone(utc.utc)


def archived(occurrence, now=None):
    return (now or timezone.now()) >= archive_time(occurrence)


def normalize_payload(kind, payload, actor=None, item=None):
    serializer = EventSerializer(data=payload) if kind == 'event' else ServiceSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    # Serializer output converts dates, times and Decimal into portable JSON.
    result = json.loads(json.dumps(serializer.data, cls=DjangoJSONEncoder))
    from .models import Asset
    asset_ids = result['image_ids'] + ([result['pdf_id']] if result.get('pdf_id') else [])
    if len(asset_ids) != len(set(asset_ids)):
        raise ValidationError('Do not repeat an attachment.')
    for asset_id in asset_ids:
        asset = get_object_or_404(Asset, pk=asset_id)
        if asset.kind != ('pdf' if asset_id == result.get('pdf_id') else 'image'):
            raise ValidationError('Attachment type does not match its field.')
        public = public_items().filter(published_revision__assets=asset).exists()
        existing = bool(item and item.revisions.filter(assets=asset).exists())
        if not public and not existing and (not actor or asset.owner_id != actor.pk):
            raise PermissionDenied("Cannot attach another account's private upload.")
    if kind == 'event' and result['service_id']:
        venue = public_items('service').select_related('published_revision').filter(pk=result['service_id']).first()
        if venue:
            detail = venue.published_revision.payload
        elif item and item.published_revision and item.published_revision.payload.get('service_id') == result['service_id'] and item.published_revision.payload.get('venue_snapshot'):
            detail = item.published_revision.payload['venue_snapshot']
            result['service_id'] = None
        else:
            raise ValidationError({'service_id': 'Choose a published service venue.'})
        result['venue_snapshot'] = {key: detail[key] for key in ('name', 'address', 'latitude', 'longitude', 'city_id', 'country_id')}
        if result['country_id'] != detail['country_id'] or (result['city_id'] and result['city_id'] != detail['city_id']):
            raise ValidationError('Event country/city must match its service venue.')
        for key in ('address', 'latitude', 'longitude', 'city_id'):
            result[key] = detail[key]
    return result


def duplicate_services(name, exclude=None):
    candidates = Item.objects.filter(kind='service').exclude(status='soft_deleted')
    if exclude:
        candidates = candidates.exclude(pk=exclude)
    matches = []
    for item in candidates.select_related('proposed_revision', 'published_revision'):
        revision = item.proposed_revision or item.published_revision
        if revision and similar_names(name, revision.payload['name']):
            matches.append(item.pk)
    return matches


def schedule(payload):
    start = datetime.fromisoformat(payload['starts_at'].replace('Z', '+00:00'))
    local = start.astimezone(ZoneInfo(payload['time_zone']))
    nominal_day, month_index = local.day, local.year*12+local.month-1
    result = []
    while len(result) < payload['occurrence_count']:
        if not result:
            current = local
        elif payload['recurrence'] == 'weekly':
            current = local + timedelta(weeks=len(result))
        else:
            month_index += 1
            year, month_zero = divmod(month_index, 12)
            month = month_zero+1
            if nominal_day > calendar.monthrange(year, month)[1]:
                continue
            current = local.replace(year=year, month=month, day=nominal_day)
        # Never silently invent a recurring clock time in a DST gap or overlap.
        if current.astimezone(utc.utc).astimezone(current.tzinfo).replace(tzinfo=None) != current.replace(tzinfo=None):
            raise ValidationError('A recurrence falls in a daylight-saving gap; choose another local time.')
        if result and current.replace(fold=0).utcoffset() != current.replace(fold=1).utcoffset():
            raise ValidationError('A recurrence has an ambiguous local time; choose another local time.')
        result.append(current.astimezone(utc.utc))
    return result


def notify_owner(item, kind, **metadata):
    if item.owner_id:
        Notice.objects.create(user_id=item.owner_id, kind=kind, metadata={'item_id': item.pk, **metadata})


@transaction.atomic
def create_item(actor, kind, payload):
    require_creator(actor)
    detail = normalize_payload(kind, payload, actor=actor)
    if kind == 'event':
        starts = schedule(detail)
        if starts[0] <= timezone.now() and not is_reviewer(actor):
            raise ValidationError('Only organizers with moderator/admin authority may create past events.')
    item = Item.objects.create(owner=actor, kind=kind)
    revision = Revision.objects.create(item=item, author=actor, payload=detail)
    revision.assets.set(detail['image_ids'] + ([detail['pdf_id']] if detail.get('pdf_id') else []))
    item.proposed_revision = revision
    if kind == 'service':
        item.duplicate_flag = bool(duplicate_services(detail['name'], item.pk))
    item.save()
    if is_reviewer(actor):
        audit(actor, 'item.create', item, kind=kind)
    return item


@transaction.atomic
def edit_item(actor, item_id, payload, moderator=False):
    item = get_object_or_404(Item.objects.select_for_update().select_related('published_revision', 'proposed_revision'), pk=item_id)
    if moderator:
        require_reviewer(actor)
        if item.locked and item.reviewer_id != actor.pk:
            raise ValidationError('Another reviewer holds this lock; an admin must unlock it first.')
    else:
        require_creator(actor)
        if item.owner_id != actor.pk:
            raise PermissionDenied('Only your own items can be changed.')
        if item.status in ['hidden', 'soft_deleted'] or item.locked:
            raise ValidationError('This item is hidden, deleted or currently locked for review.')
        if item.kind == 'event' and item.occurrences.exists() and all(archived(row) for row in item.occurrences.all()):
            raise ValidationError('Archived events are read-only for organizers.')
    baseline = (item.published_revision or item.proposed_revision) if moderator else (item.proposed_revision or item.published_revision)
    merged = dict(baseline.payload) if baseline else {}
    merged.update(payload)
    detail = normalize_payload(item.kind, merged, actor=actor, item=item)
    if item.kind == 'event':
        if item.published_revision:
            original = item.published_revision.payload
            timing_keys = ['starts_at', 'duration_minutes', 'time_zone', 'recurrence', 'occurrence_count']
            if any(detail[key] != original[key] for key in timing_keys):
                raise ValidationError('Use occurrence rescheduling to change a published schedule.')
            from .registration import occupied
            if any(not archived(row) and detail['seat_limit'] < occupied(row) for row in item.occurrences.all()):
                raise ValidationError('Remove registrations before lowering capacity below occupied seats.')
        elif schedule(detail)[0] <= timezone.now() and not is_reviewer(actor):
            raise ValidationError('Cannot submit a past event.')
    revision = Revision.objects.create(item=item, author=actor, payload=detail)
    revision.assets.set(detail['image_ids'] + ([detail['pdf_id']] if detail.get('pdf_id') else []))
    item.proposed_revision = revision
    item.rejection_reason = ''
    item.duplicate_flag = item.kind == 'service' and bool(duplicate_services(detail['name'], item.pk))
    if moderator:
        if item.status == 'soft_deleted':
            raise ValidationError('Restore the item before editing.')
        was_hidden = item.status == 'hidden'
        apply_revision(item, correct_archive=True)
        if was_hidden:
            item.status = 'hidden'
            item.save(update_fields=['status'])
        audit(actor, 'item.edit', item, revision_id=revision.pk)
        notify_owner(item, 'item.moderator_edit')
    else:
        item.status = 'pending_changes' if item.published_revision_id else 'pending'
        item.save()
    return item


def apply_revision(item, correct_archive=False):
    first_publication = item.published_revision_id is None
    detail = item.proposed_revision.payload
    item.published_revision = item.proposed_revision
    item.proposed_revision = None
    item.status, item.locked, item.reviewer = 'approved', False, None
    item.name = detail.get('name', detail.get('title', ''))
    item.normalized_name = normalize(item.name)
    item.search_text = normalize(' '.join(str(detail.get(key, '')) for key in ('name', 'title', 'description', 'speaker_name', 'topic', 'address')))
    item.country_id, item.city_id = detail['country_id'], detail['city_id']
    item.latitude, item.longitude = detail['latitude'], detail['longitude']
    item.price, item.currency_id = detail.get('price'), detail.get('currency_id')
    item.save()
    item.categories.set(detail['category_ids'])
    if item.kind == 'event':
        first = datetime.fromisoformat(detail['starts_at'].replace('Z', '+00:00'))
        deadline = datetime.fromisoformat(detail['registration_deadline'].replace('Z', '+00:00')) if detail['registration_deadline'] else None
        offset = (first-deadline) if deadline else None
        existing = list(item.occurrences.select_for_update().order_by('starts_at'))
        if not existing:
            for start in schedule(detail):
                Occurrence.objects.create(event=item, revision=item.published_revision, starts_at=start,
                    ends_at=start+timedelta(minutes=detail['duration_minutes']), time_zone=detail['time_zone'],
                    seat_limit=detail['seat_limit'], registration_deadline=start-offset if offset is not None else None,
                    cancellation_cutoff_minutes=detail['cancellation_cutoff_minutes'])
        else:
            from .registration import occupied, promote
            for occurrence in existing:
                if archived(occurrence):
                    if correct_archive:
                        occurrence.revision = item.published_revision
                        occurrence.save(update_fields=['revision'])
                    continue
                occurrence.revision = item.published_revision
                if detail['seat_limit'] < occupied(occurrence):
                    raise ValidationError('Proposed capacity is below current occupied seats.')
                occurrence.seat_limit = detail['seat_limit']
                occurrence.registration_deadline = occurrence.starts_at-offset if offset is not None else None
                occurrence.cancellation_cutoff_minutes = detail['cancellation_cutoff_minutes']
                occurrence.save()
                promote(occurrence)
    if first_publication and item.kind == 'event':
        from notifications.services import published_event
        published_event(item)


@transaction.atomic
def claim_review(actor, item_id):
    require_reviewer(actor)
    item = get_object_or_404(Item.objects.select_for_update(), pk=item_id, status__in=['pending', 'pending_changes'])
    if item.locked and item.reviewer_id != actor.pk:
        raise ValidationError('Another reviewer holds this lock.')
    item.locked, item.reviewer = True, actor
    item.save(update_fields=['locked', 'reviewer'])
    audit(actor, 'item.review_claim', item)
    return item


@transaction.atomic
def decide(actor, item_id, approved, reason):
    require_reviewer(actor)
    item = get_object_or_404(Item.objects.select_for_update().select_related('proposed_revision'), pk=item_id, status__in=['pending', 'pending_changes'])
    if not item.locked or item.reviewer_id != actor.pk:
        raise PermissionDenied('Claim this review before deciding.')
    if approved:
        apply_revision(item)
    else:
        item.status = 'approved' if item.published_revision_id else 'rejected'
        item.locked, item.reviewer = False, None
        item.rejection_reason = reason
        # Keep the rejected proposal for the owner's next edit; it never goes live.
        item.save()
    audit(actor, 'item.approve' if approved else 'item.reject', item)
    notify_owner(item, 'item.approved' if approved else 'item.rejected', reason=reason)
    return item


@transaction.atomic
def unlock(actor, item_id):
    if not actor.has_role('admin'):
        raise PermissionDenied('Administrator role required.')
    item = get_object_or_404(Item.objects.select_for_update(), pk=item_id)
    item.locked, item.reviewer = False, None
    item.save(update_fields=['locked', 'reviewer'])
    audit(actor, 'item.review_unlock', item)
    return item


@transaction.atomic
def change_visibility(actor, item_id, action):
    require_reviewer(actor)
    item = get_object_or_404(Item.objects.select_for_update(), pk=item_id)
    if action == 'delete':
        if item.status == 'soft_deleted':
            audit(actor, 'item.delete_noop', item)
            return item
        item.previous_status = item.status
        item.status, item.deleted_at = 'soft_deleted', timezone.now()
        from .registration import cancel_occurrence
        for occurrence in item.occurrences.select_for_update():
            cancel_occurrence(occurrence, 'event.deleted')
    elif action == 'restore':
        if item.status != 'soft_deleted' or item.deleted_at + timedelta(days=3) <= timezone.now():
            raise ValidationError('Restoration is available for three days after deletion.')
        item.status, item.deleted_at = item.previous_status, None
        item.occurrences.filter(cancel_reason='event.deleted').update(cancelled_at=None, cancel_reason='')
    elif action == 'hide':
        if item.status == 'soft_deleted':
            raise ValidationError('Deleted items cannot be hidden.')
        if item.status != 'hidden':
            item.hidden_previous_status, item.status = item.status, 'hidden'
    elif action == 'unhide':
        if item.status != 'hidden':
            raise ValidationError('Item is not hidden.')
        if item.published_revision_id:
            item.status = 'pending_changes' if item.hidden_previous_status == 'pending_changes' and item.proposed_revision_id else 'approved'
        else:
            item.status = item.hidden_previous_status if item.hidden_previous_status in ['pending', 'rejected'] else 'pending'
    item.locked, item.reviewer = False, None
    item.save()
    audit(actor, 'item.'+action, item)
    notify_owner(item, 'item.'+action)
    return item


def is_open(payload, now=None):
    local = (now or timezone.now()).astimezone(ZoneInfo(payload['time_zone']))
    weekday, minute = local.weekday(), local.hour*60+local.minute
    for row in payload['hours']:
        start, end = time.fromisoformat(row['start']), time.fromisoformat(row['end'])
        start, end = start.hour*60+start.minute, end.hour*60+end.minute
        if end > start and weekday == row['day'] and start <= minute < end:
            return True
        if end <= start and ((weekday == row['day'] and minute >= start) or (weekday == (row['day']+1)%7 and minute < end)):
            return True
    return False
