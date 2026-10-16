"""Small durable queue: atomic fanout and per-device bounded delivery attempts."""
import json
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from accounts.models import MaintenanceRun, User
from catalog.models import Item, Notice
from .fcm import PushError
from .models import Announcement, Delivery, Device, Dispatch, Preferences
from .services import eligible, expiry, generate_follow_notices, generate_reminders, quiet_now, public_upcoming, event_still_followed

TEXT = {
    'reminder': ('تذكير بموعد فعالية', 'Event reminder'),
    'event.cancelled': ('أُلغيت الفعالية', 'Event cancelled'),
    'event.deleted': ('حُذفت الفعالية', 'Event removed'),
    'event.rescheduled': ('تغيّر موعد الفعالية', 'Event rescheduled'),
    'waitlist.promoted': ('أصبح لك مقعد في الفعالية', 'Your waitlist place is confirmed'),
    'registration.registered': ('تأكيد التسجيل', 'Registration confirmed'),
    'registration.waitlisted': ('أُضيف اسمك إلى قائمة الانتظار', 'You are on the waitlist'),
    'registration.pending_reconfirm': ('يرجى إعادة تأكيد التسجيل', 'Please reconfirm your registration'),
    'registration.cancelled': ('أُلغي التسجيل', 'Registration cancelled'),
    'item.approved': ('تمت الموافقة على المحتوى', 'Submission approved'),
    'item.rejected': ('لم تتم الموافقة على المحتوى', 'Submission rejected'),
    'organizer_request.approved': ('تمت الموافقة على طلب المنظّم', 'Organizer application approved'),
    'organizer_request.rejected': ('لم تتم الموافقة على طلب المنظّم', 'Organizer application rejected'),
    'organizer.warning': ('تنبيه بخصوص المحتوى', 'Notice about your content'),
    'event.followed': ('فعالية جديدة من متابعاتك', 'New event from your follows'),
    'event.digest': ('ملخص فعاليات متابعاتك', 'Your followed events digest'),
}


def payload(notice, device, pref, now, expires_at):
    arabic = notice.user.language == 'ar'
    title = TEXT.get(notice.kind, ('مُنسِّق', 'Munassiq'))[0 if arabic else 1]
    body = 'افتح التطبيق للاطلاع على التفاصيل.' if arabic else 'Open the app for details.'
    if notice.kind == 'announcement':
        row = Announcement.objects.get(pk=notice.metadata['announcement_id'])
        title = row.title_ar if arabic else row.title_en
        body = (row.body_ar if arabic else row.body_en)[:600]
    silent = quiet_now(pref, now)
    data = {'notice_id': str(notice.pk), 'kind': notice.kind, 'silent': str(silent).lower(),
        'time_zone': pref.time_zone, 'quiet_start': str(pref.quiet_start or ''),
        'quiet_end': str(pref.quiet_end or ''), 'title': title, 'body': body,
        'expires_at': expires_at.isoformat()}
    for key in ('item_id', 'occurrence_id', 'registration_id', 'announcement_id'):
        if notice.metadata.get(key) is not None:
            data[key] = str(notice.metadata[key])
    if data.get('item_id'):
        item = Item.objects.filter(pk=data['item_id']).first()
        if item:
            data['item_kind'] = item.kind
    if notice.kind == 'event.digest':
        events = [row.pk for row in Item.objects.filter(pk__in=notice.metadata.get('item_ids', []))
            if public_upcoming(row, now) and event_still_followed(notice.user_id, row)]
        data['item_ids'] = json.dumps(events[:20])
        data['count'] = str(len(events))
    # Data-only messages let Android enforce quiet hours at receipt, rather than
    # letting FCM auto-display a channel chosen before a delayed delivery.
    return {'token': device.token, 'data': data,
        'android': {'priority': 'high', 'ttl': f'{max(0, int((expires_at-now).total_seconds()))}s'}}


def expand_notices(limit=200):
    count = 0
    ids = list(Notice.objects.filter(dispatch__isnull=True).order_by('pk').values_list('pk', flat=True)[:limit])
    for notice_id in ids:
        with transaction.atomic():
            notice = Notice.objects.select_for_update().select_related('user').filter(pk=notice_id).first()
            if not notice or Dispatch.objects.filter(notice=notice).exists():
                continue
            now = timezone.now()
            pref, _ = Preferences.objects.get_or_create(user=notice.user)
            until = expiry(notice)
            suppressed = until <= now or not eligible(notice, pref, now)
            dispatch = Dispatch.objects.create(notice=notice, expires_at=until,
                expanded_at=now, suppressed=suppressed)
            if not suppressed:
                Delivery.objects.bulk_create([Delivery(dispatch=dispatch, device=device)
                    for device in Device.objects.filter(user=notice.user,
                        session__revoked_at=None, session__expires_at__gt=now)])
            count += 1
    return count


def send_due(sender, limit=20):
    completed = 0
    candidates = list(Delivery.objects.filter(completed_at=None, next_attempt_at__lte=timezone.now())
        .order_by('next_attempt_at', 'pk').values_list('pk', 'dispatch__notice__user_id')[:limit])
    for delivery_id, user_id in candidates:
        # Serialize this user with bans. The bounded network call holds the row
        # lock so no attempt starts after a committed ban. SQLite also serializes
        # writers; appropriate for the expected small first-year audience.
        with transaction.atomic():
            user = User.objects.select_for_update().filter(pk=user_id).first()
            row = Delivery.objects.select_for_update().select_related('dispatch__notice', 'device').filter(pk=delivery_id, completed_at=None).first()
            now = timezone.now()
            if not user or not row or row.next_attempt_at > now:
                continue
            notice = row.dispatch.notice
            notice.user = user
            pref, _ = Preferences.objects.get_or_create(user=user)
            # Start time/registration/reminder may have changed since fanout.
            until = min(row.dispatch.expires_at, expiry(notice))
            session = row.device.session
            if (row.dispatch.suppressed or row.device.user_id != user_id or not session
                or session.user_id != user_id or session.revoked_at or session.expires_at <= now
                or until <= now or not eligible(notice, pref, now)):
                row.completed_at, row.outcome = now, 'suppressed'
                row.save(update_fields=['completed_at', 'outcome'])
                completed += 1
                continue
            row.attempts += 1
            try:
                sender.send(payload(notice, row.device, pref, now, until))
            except PushError as exc:
                if exc.code == 'unregistered':
                    row.device.delete()
                    completed += 1
                    continue
                row.outcome = exc.code
                if exc.retryable and row.attempts < 6:
                    row.next_attempt_at = now+timedelta(seconds=max(exc.retry_after, min(3600, 60*2**(row.attempts-1))))
                else:
                    row.completed_at = now
                    completed += 1
            else:
                row.completed_at, row.outcome = now, 'accepted'
                completed += 1
            row.save()
    return completed


def run(sender):
    record = MaintenanceRun.objects.create(name='notifications.delivery')
    processed = 0
    try:
        processed += generate_reminders()
        processed += generate_follow_notices()
        processed += expand_notices()
        processed += send_due(sender)
        # Keep bounded queue history. No message text or raw token is copied to
        # audit/job logs; deleting the intent cascades its dispatch/deliveries.
        Notice.objects.filter(created_at__lt=timezone.now()-timedelta(days=30)).delete()
        from .models import DigestRun
        DigestRun.objects.filter(day__lt=(timezone.now()-timedelta(days=30)).date()).delete()
    finally:
        record.processed, record.finished_at = processed, timezone.now()
        record.save(update_fields=['processed', 'finished_at'])
    return processed
