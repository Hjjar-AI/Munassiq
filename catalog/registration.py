"""Explicit registration state machine; caller-visible state and notice are atomic."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from accounts.services import audit
from .models import Item, Notice, Occurrence, Registration, RegistrationTransition

ACTIVE = ['registered', 'waitlisted', 'pending_reconfirm']
SEATED = ['registered', 'pending_reconfirm']
TRANSITIONS = {
    '': {'registered', 'waitlisted'},
    'registered': {'pending_reconfirm', 'cancelled'},
    'waitlisted': {'registered', 'cancelled'},
    'pending_reconfirm': {'registered', 'cancelled'},
    'cancelled': {'registered', 'waitlisted'},
}


def occupied(occurrence):
    return occurrence.registrations.filter(state__in=SEATED).count()


def transition(record, state, reason, notice_kind=None):
    old = record.state
    if old == state:
        return record
    if state not in TRANSITIONS.get(old, set()):
        raise ValidationError(f'Invalid registration transition: {old} -> {state}.')
    record.state = state
    if state != 'pending_reconfirm':
        record.reconfirm_deadline = None
    record.save()
    RegistrationTransition.objects.create(registration=record, occurrence_key=str(record.occurrence_id), old_state=old, new_state=state, reason=reason)
    Notice.objects.create(user=record.user, kind=notice_kind or ('waitlist.promoted' if reason == 'waitlist.promotion' else 'registration.'+state),
        metadata={'occurrence_id': record.occurrence_id, 'registration_id': record.pk,
            'old_state': old, 'state': state, 'reason': reason,
            'starts_at': record.occurrence.starts_at.isoformat(),
            'reconfirm_deadline': record.reconfirm_deadline.isoformat() if record.reconfirm_deadline else None})
    return record


def locked_occurrence(occurrence_id):
    # Stable lock order: item first, occurrence second. SQLite uses IMMEDIATE
    # transactions; PostgreSQL can use these explicit row locks.
    event_id = get_object_or_404(Occurrence.objects.only('event_id'), pk=occurrence_id).event_id
    get_object_or_404(Item.objects.select_for_update(), pk=event_id)
    return get_object_or_404(Occurrence.objects.select_for_update().select_related('event'), pk=occurrence_id)


def registration_open(occurrence):
    from .services import PUBLIC_STATUSES, archived
    now = timezone.now()
    return (occurrence.event.status in PUBLIC_STATUSES and occurrence.event.published_revision_id
        and not occurrence.cancelled_at and not archived(occurrence, now) and now < occurrence.starts_at
        and (occurrence.registration_deadline is None or now < occurrence.registration_deadline))


def promote(occurrence):
    if not registration_open(occurrence):
        return
    while occupied(occurrence) < occurrence.seat_limit:
        # Ban pauses promotion but preserves the original queue timestamp.
        record = occurrence.registrations.select_related('user', 'occurrence').filter(
            state='waitlisted', user__is_active=True, user__verified_at__isnull=False).order_by('queued_at', 'pk').first()
        if not record:
            return
        transition(record, 'registered', 'waitlist.promotion')


@transaction.atomic
def register(user, occurrence_id):
    from accounts.models import User
    if not User.objects.filter(pk=user.pk, is_active=True, verified_at__isnull=False).exists():
        raise PermissionDenied('A verified email is required to register.')
    occurrence = locked_occurrence(occurrence_id)
    if not registration_open(occurrence):
        raise ValidationError('Registration is closed.')
    previous = occurrence.registrations.filter(user=user).first()
    if previous and previous.state in ACTIVE:
        return previous, overlap(user, occurrence)
    promote(occurrence)
    # New applicants cannot jump ahead of eligible waiting users.
    state = 'registered' if occupied(occurrence) < occurrence.seat_limit else 'waitlisted'
    record = previous or Registration(user=user, occurrence=occurrence, state='')
    record.queued_at = timezone.now()
    transition(record, state, 'user.signup')
    return record, overlap(user, occurrence)


def overlap(user, occurrence):
    return Registration.objects.filter(user=user, state__in=SEATED,
        occurrence__starts_at__lt=occurrence.ends_at, occurrence__ends_at__gt=occurrence.starts_at,
        occurrence__cancelled_at=None).exclude(occurrence=occurrence).exists()


@transaction.atomic
def cancel(user, registration_id, force=False, reason='user.cancel'):
    original = get_object_or_404(Registration, pk=registration_id)
    occurrence = locked_occurrence(original.occurrence_id)
    record = get_object_or_404(Registration.objects.select_for_update().select_related('occurrence', 'user'), pk=registration_id)
    if force:
        from .services import is_reviewer, archived
        from .exports import require_registrant_access
        require_registrant_access(user, occurrence)
        if archived(occurrence) and not is_reviewer(user):
            raise ValidationError('Archived registrations are read-only for organizers.')
        if not reason.strip():
            raise ValidationError('Removal reason is required.')
    elif record.user_id != user.pk:
        raise PermissionDenied('Only your own registration can be cancelled.')
    if record.state == 'cancelled':
        return record
    if not force:
        from .services import archived
        if archived(occurrence):
            raise ValidationError('Archived registrations are read-only.')
        cutoff = occurrence.starts_at-timedelta(minutes=occurrence.cancellation_cutoff_minutes)
        deadline = record.reconfirm_deadline if record.state == 'pending_reconfirm' else cutoff
        if timezone.now() >= deadline:
            raise ValidationError('Cancellation cutoff has passed.')
    transition(record, 'cancelled', reason)
    if force:
        from .services import is_reviewer
        if is_reviewer(user):
            audit(user, 'registration.remove', record)
    promote(occurrence)
    return record


def cancel_occurrence(occurrence, reason):
    if not occurrence.cancelled_at:
        occurrence.cancelled_at = timezone.now()
        occurrence.cancel_reason = reason
        occurrence.save(update_fields=['cancelled_at', 'cancel_reason'])
    for record in occurrence.registrations.select_related('user', 'occurrence').filter(state__in=ACTIVE):
        transition(record, 'cancelled', reason, notice_kind=reason)


@transaction.atomic
def cancel_event(actor, occurrence_id):
    from .services import is_reviewer, archived
    occurrence = locked_occurrence(occurrence_id)
    if not is_reviewer(actor) and not (actor.has_role('organizer') and occurrence.event.owner_id == actor.pk):
        raise PermissionDenied('Only the organizer or a moderator can cancel this occurrence.')
    if archived(occurrence):
        raise ValidationError('Archived occurrences cannot be cancelled.')
    cancel_occurrence(occurrence, 'event.cancelled')
    if is_reviewer(actor):
        audit(actor, 'event.cancel', occurrence)
    return occurrence


@transaction.atomic
def reschedule(actor, occurrence_id, starts_at, duration_minutes, time_zone):
    from .services import is_reviewer, archived
    occurrence = locked_occurrence(occurrence_id)
    if not is_reviewer(actor) and not (actor.has_role('organizer') and occurrence.event.owner_id == actor.pk):
        raise PermissionDenied('Only the organizer or a moderator can reschedule this occurrence.')
    if archived(occurrence) or occurrence.cancelled_at:
        raise ValidationError('Archived or cancelled occurrences cannot be rescheduled.')
    now = timezone.now()
    if starts_at <= now:
        raise ValidationError('New start must be in the future.')
    try:
        ZoneInfo(time_zone)
    except (ValueError, ZoneInfoNotFoundError):
        raise ValidationError({'time_zone': 'Use an IANA time-zone name.'})
    previous_start = occurrence.starts_at
    offset = previous_start-occurrence.registration_deadline if occurrence.registration_deadline else None
    occurrence.starts_at = starts_at
    occurrence.ends_at = starts_at+timedelta(minutes=duration_minutes)
    occurrence.time_zone = time_zone
    occurrence.registration_deadline = starts_at-offset if offset is not None else None
    occurrence.save()
    short_notice = starts_at < now+timedelta(hours=12)
    deadline = max(starts_at-timedelta(minutes=occurrence.cancellation_cutoff_minutes), now+timedelta(hours=12))
    for record in occurrence.registrations.filter(state__in=ACTIVE).select_related('user'):
        record.occurrence = occurrence
        old_state = record.state
        if record.state in SEATED:
            if short_notice:
                transition(record, 'registered', 'reschedule.short_notice', 'event.rescheduled')
            else:
                record.reconfirm_deadline = deadline
                if record.state == 'pending_reconfirm':
                    record.save(update_fields=['reconfirm_deadline'])
                else:
                    transition(record, 'pending_reconfirm', 'event.rescheduled', 'event.rescheduled')
        # Unchanged states also need the new-time notification.
        if record.state == old_state:
            Notice.objects.create(user=record.user, kind='event.rescheduled', metadata={
                'occurrence_id': occurrence.pk, 'starts_at': starts_at.isoformat(), 'optional_reconfirm': short_notice, 'state': record.state,
                'reconfirm_deadline': record.reconfirm_deadline.isoformat() if record.reconfirm_deadline else None})
    if is_reviewer(actor):
        audit(actor, 'event.reschedule', occurrence)
    return occurrence


@transaction.atomic
def reconfirm(user, registration_id):
    original = get_object_or_404(Registration, pk=registration_id)
    occurrence = locked_occurrence(original.occurrence_id)
    record = get_object_or_404(Registration.objects.select_for_update().select_related('occurrence', 'user'), pk=registration_id, user=user)
    if record.state == 'registered':
        return record  # Optional confirmation for a short-notice change.
    if record.state != 'pending_reconfirm' or occurrence.cancelled_at or timezone.now() >= record.reconfirm_deadline:
        raise ValidationError('Reconfirmation is unavailable or expired.')
    return transition(record, 'registered', 'user.reconfirm')


@transaction.atomic
def register_series(user, event_id):
    event = get_object_or_404(Item.objects.select_for_update(), pk=event_id, kind='event')
    rows = list(event.occurrences.filter(starts_at__gt=timezone.now(), cancelled_at=None).order_by('starts_at', 'pk'))
    if not rows:
        raise ValidationError('No future occurrences are available.')
    # Only currently published, still-open occurrences are included; later additions
    # never silently enroll the user. A failed attempt rolls back the whole action.
    rows = [row for row in rows if registration_open(row)]
    if not rows:
        raise ValidationError('Registration is closed for this series.')
    return [register(user, row.pk) for row in rows]
