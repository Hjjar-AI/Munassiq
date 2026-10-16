"""Queue creation. No network calls; safe to invoke inside content transactions."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.db import transaction
from django.utils import timezone
from accounts.models import User
from catalog.models import Item, Notice, Occurrence, Reminder
from .models import Announcement, CategoryFollow, DigestRun, Dispatch, OrganizerFollow, PendingFollow, Preferences


def announcement_matches(row, user, pref=None):
    if row.audience == 'everyone':
        return True
    if row.audience == 'organizers':
        return user.has_role('organizer')
    return bool(pref and pref.country_id == row.country_id and (not row.city_id or pref.city_id == row.city_id))


def announce(row):
    for user in User.objects.filter(is_active=True).iterator():
        pref = Preferences.objects.filter(user=user).first()
        if (not pref or pref.announcements) and announcement_matches(row, user, pref):
            Notice.objects.create(user=user, kind='announcement', metadata={'announcement_id': row.pk})


def published_event(item):
    """Call exactly once on first publication, never on revisions or restores."""
    if item.kind != 'event':
        return
    organizers = OrganizerFollow.objects.filter(organizer_id=item.owner_id).values_list('user_id', flat=True)
    categories = CategoryFollow.objects.filter(category__in=item.categories.all()).values_list('user_id', flat=True)
    for user_id in set(organizers) | set(categories):
        if user_id != item.owner_id and User.objects.filter(pk=user_id, is_active=True).exists():
            PendingFollow.objects.get_or_create(user_id=user_id, event=item)


def event_still_followed(user_id, event):
    return (OrganizerFollow.objects.filter(user_id=user_id, organizer_id=event.owner_id).exists()
        or CategoryFollow.objects.filter(user_id=user_id, category__in=event.categories.all()).exists())


def public_upcoming(event, now):
    return (event.published_revision_id and event.status in ('approved', 'pending_changes')
        and event.occurrences.filter(starts_at__gt=now, cancelled_at=None).exists())


@transaction.atomic
def generate_follow_notices(now=None):
    now = now or timezone.now()
    generated = 0
    for user_id in PendingFollow.objects.values_list('user_id', flat=True).distinct():
        user = User.objects.select_for_update().filter(pk=user_id).first()
        if not user:
            continue
        pref, _ = Preferences.objects.get_or_create(user=user)
        rows = PendingFollow.objects.select_for_update().filter(user=user).select_related('event')
        if not user.is_active or not pref.followed_events:
            rows.delete()
            continue
        if pref.follow_delivery == 'daily':
            local = now.astimezone(ZoneInfo(pref.time_zone))
            scheduled = datetime.combine(local.date(), time(9), tzinfo=local.tzinfo)
            if local < scheduled or DigestRun.objects.filter(user=user, day=local.date()).exists():
                continue
            rows = rows.filter(created_at__lte=scheduled)
        selected = list(rows)
        events = [row.event_id for row in selected if public_upcoming(row.event, now) and event_still_followed(user_id, row.event)]
        if events:
            if pref.follow_delivery == 'daily':
                DigestRun.objects.create(user=user, day=local.date())
                Notice.objects.create(user=user, kind='event.digest', metadata={'item_ids': events})
                generated += 1
            else:
                for event_id in events:
                    Notice.objects.create(user=user, kind='event.followed', metadata={'item_id': event_id})
                    generated += 1
        PendingFollow.objects.filter(pk__in=[row.pk for row in selected]).delete()
    return generated


@transaction.atomic
def generate_reminders(now=None):
    now = now or timezone.now()
    count = 0
    for reminder in Reminder.objects.select_for_update().select_related('occurrence__event', 'user').filter(user__is_active=True):
        occurrence = reminder.occurrence
        if reminder.sent_for_start == occurrence.starts_at or occurrence.cancelled_at or occurrence.starts_at <= now:
            continue
        if occurrence.event.status not in ('approved', 'pending_changes'):
            continue
        due = occurrence.starts_at-timedelta(minutes=reminder.offset_minutes)
        if due > now:
            continue
        # Mark even expired reminders as handled for this start, avoiding a
        # repeated scan from creating new work after an extended outage.
        reminder.sent_for_start = occurrence.starts_at
        reminder.save(update_fields=['sent_for_start'])
        if due+timedelta(hours=1) <= now:
            continue
        Notice.objects.create(user=reminder.user, kind='reminder', metadata={
            'occurrence_id': occurrence.pk, 'starts_at': occurrence.starts_at.isoformat(),
            'reminder_id': reminder.pk, 'due_at': due.isoformat(), 'offset_minutes': reminder.offset_minutes})
        count += 1
    return count


def expiry(notice):
    until = notice.created_at+timedelta(hours=24)
    occurrence = Occurrence.objects.filter(pk=notice.metadata.get('occurrence_id')).first()
    if occurrence:
        until = min(until, occurrence.starts_at)
    if notice.kind == 'event.followed':
        event = Item.objects.filter(pk=notice.metadata.get('item_id')).first()
        upcoming = event.occurrences.filter(starts_at__gt=notice.created_at, cancelled_at=None).order_by('starts_at').first() if event else None
        if upcoming:
            until = min(until, upcoming.starts_at)
    if notice.kind == 'reminder':
        try:
            until = min(until, datetime.fromisoformat(notice.metadata['due_at'])+timedelta(hours=1))
        except (KeyError, ValueError, TypeError):
            return notice.created_at
    if notice.kind == 'announcement':
        row = Announcement.objects.filter(pk=notice.metadata.get('announcement_id')).first()
        if row:
            until = min(until, row.expires_at)
    return until


def eligible(notice, pref, now):
    """Recheck mutable facts immediately before each attempt, including retries."""
    if not notice.user.is_active:
        return False
    data = notice.metadata
    if notice.kind == 'event.rescheduled':
        occurrence = Occurrence.objects.filter(pk=data.get('occurrence_id')).first()
        if not occurrence or occurrence.cancelled_at or occurrence.starts_at.isoformat() != data.get('starts_at'):
            return False
    if notice.kind == 'reminder':
        row = Reminder.objects.select_related('occurrence__event').filter(pk=data.get('reminder_id'), user_id=notice.user_id).first()
        return bool(pref.reminders and row and not row.occurrence.cancelled_at
            and row.occurrence.starts_at.isoformat() == data.get('starts_at')
            and row.offset_minutes == data.get('offset_minutes')
            and row.occurrence.event.status in ('approved', 'pending_changes'))
    if notice.kind in ('event.followed', 'event.digest'):
        if not pref.followed_events:
            return False
        ids = data.get('item_ids', [data.get('item_id')])
        return any(public_upcoming(event, now) and event_still_followed(notice.user_id, event)
            for event in Item.objects.filter(pk__in=ids))
    if notice.kind == 'announcement':
        row = Announcement.objects.filter(pk=data.get('announcement_id'), expires_at__gt=now).first()
        return bool(pref.announcements and row and announcement_matches(row, notice.user, pref))
    # Essential decisions and lifecycle messages deliberately have no mute toggle.
    return True


def quiet_now(pref, now):
    if pref.quiet_start is None:
        return False
    local = now.astimezone(ZoneInfo(pref.time_zone)).time().replace(tzinfo=None)
    if pref.quiet_start < pref.quiet_end:
        return pref.quiet_start <= local < pref.quiet_end
    return local >= pref.quiet_start or local < pref.quiet_end


def suppress_user(user):
    """Called atomically with ban; unban must not replay old messages."""
    from .models import Device
    for notice in Notice.objects.filter(user=user).exclude(dispatch__suppressed=True):
        Dispatch.objects.update_or_create(notice=notice, defaults={
            'expires_at': timezone.now(), 'expanded_at': timezone.now(), 'suppressed': True})
    PendingFollow.objects.filter(user=user).delete()
    Device.objects.filter(user=user).delete()
