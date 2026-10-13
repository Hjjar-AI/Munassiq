from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from rest_framework.exceptions import ValidationError
from .models import Registration
from .services import archived, is_open

PROTECTED_FIELDS = ['phone', 'contact_person', 'registration_contact', 'registration_url']


def display_zone(name):
    try:
        return ZoneInfo(name)
    except (ValueError, ZoneInfoNotFoundError):
        raise ValidationError({'time_zone': 'Use an IANA time-zone name.'})


def occurrence_data(row, user_zone='UTC'):
    zone, local = display_zone(user_zone), ZoneInfo(row.time_zone)
    return {'id': row.pk, 'starts_at': row.starts_at, 'ends_at': row.ends_at,
        'event_local_start': row.starts_at.astimezone(local).isoformat(),
        'event_local_end': row.ends_at.astimezone(local).isoformat(),
        'user_local_start': row.starts_at.astimezone(zone).isoformat(),
        'time_zone': row.time_zone, 'cancelled': bool(row.cancelled_at), 'archived': archived(row),
        'seat_limit': row.seat_limit, 'registration_deadline': row.registration_deadline,
        'cancellation_cutoff_minutes': row.cancellation_cutoff_minutes}


def item_data(item, user=None, private=False, include_archive=False, archived_only=False, user_zone='UTC', occurrence_ids=None):
    revision = (item.proposed_revision or item.published_revision) if private else item.published_revision
    payload = dict(revision.payload) if revision else {}
    result = {'id': item.pk, 'kind': item.kind, 'status': item.status if private else 'approved',
        'owner_id': item.owner_id, 'payload': payload}
    if private:
        result.update(locked=item.locked, reviewer_name=item.reviewer.name if item.reviewer else None,
            rejection_reason=item.rejection_reason, duplicate_flag=item.duplicate_flag,
            proposed_revision_id=item.proposed_revision_id)
    if item.kind == 'event':
        occurrences = list(item.occurrences.order_by('starts_at', 'pk'))
        if occurrence_ids is not None:
            occurrences = [row for row in occurrences if row.pk in occurrence_ids]
        if not private:
            occurrences = [row for row in occurrences if (archived(row) if archived_only else include_archive or not archived(row))]
        if not private and occurrences and occurrences[0].revision_id:
            payload = dict(occurrences[0].revision.payload)
            result['payload'] = payload
        result['occurrences'] = [occurrence_data(row, user_zone) for row in occurrences]
        result['date_range'] = {'start': occurrences[0].starts_at, 'end': max(row.ends_at for row in occurrences)} if occurrences else None
        if not private:
            # Live occurrence rows are authoritative after immediate rescheduling.
            for field in ('starts_at', 'duration_minutes', 'registration_deadline', 'seat_limit', 'cancellation_cutoff_minutes'):
                payload.pop(field, None)
    else:
        result['open_now'] = is_open(payload) if revision else False
    if not private and payload.get('service_id'):
        from .services import public_items
        if not public_items('service').filter(pk=payload['service_id']).exists():
            payload['service_id'] = None
    if not user or not user.is_authenticated:
        for field in PROTECTED_FIELDS:
            payload.pop(field, None)
    return result


def registration_data(record, overlap_warning=False):
    return {'id': record.pk, 'occurrence_id': record.occurrence_id, 'state': record.state,
        'reconfirm_deadline': record.reconfirm_deadline, 'overlap_warning': overlap_warning}
