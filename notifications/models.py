"""Private device registrations and user-selected notification subscriptions."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class Preferences(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    time_zone = models.CharField(max_length=80, default='Asia/Damascus')
    country = models.ForeignKey('catalog.Country', null=True, on_delete=models.SET_NULL)
    city = models.ForeignKey('catalog.City', null=True, on_delete=models.SET_NULL)
    reminders = models.BooleanField(default=True)
    announcements = models.BooleanField(default=True)
    followed_events = models.BooleanField(default=True)
    follow_delivery = models.CharField(max_length=8, default='instant',
        choices=[('instant', 'Instant'), ('daily', 'Daily digest')])
    quiet_start = models.TimeField(null=True)
    quiet_end = models.TimeField(null=True)


class Device(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.ForeignKey('accounts.Session', null=True, on_delete=models.CASCADE)
    # Raw token is necessary for FCM; never return it in list/export responses.
    token = models.CharField(max_length=4096)
    token_hash = models.CharField(max_length=64, unique=True)
    installation_id = models.UUIDField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'installation_id'], name='one_device_per_user_installation')]


class OrganizerFollow(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='organizer_follows')
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='organizer_followers')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'organizer'], name='one_organizer_follow')]


class CategoryFollow(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey('catalog.Category', on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'category'], name='one_category_follow')]


class PendingFollow(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey('catalog.Item', on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'event'], name='one_follow_event_per_user')]


class DigestRun(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    day = models.DateField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'day'], name='one_digest_per_local_day')]


class Announcement(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    title_ar = models.CharField(max_length=160)
    title_en = models.CharField(max_length=160)
    body_ar = models.CharField(max_length=1500)
    body_en = models.CharField(max_length=1500)
    audience = models.CharField(max_length=12, choices=[('everyone', 'Everyone'), ('organizers', 'Organizers'), ('location', 'Location')], default='everyone')
    country = models.ForeignKey('catalog.Country', null=True, on_delete=models.PROTECT)
    city = models.ForeignKey('catalog.City', null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()


class AppSettings(models.Model):
    # A singleton; deliberately excludes secrets and server security settings.
    singleton = models.PositiveSmallIntegerField(primary_key=True, default=1)
    support_email = models.EmailField(blank=True)
    apk_download_url = models.URLField(blank=True)
    guide_ar = models.TextField(blank=True)
    guide_en = models.TextField(blank=True)


class Dispatch(models.Model):
    notice = models.OneToOneField('catalog.Notice', on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    expanded_at = models.DateTimeField(null=True)
    suppressed = models.BooleanField(default=False)


class Delivery(models.Model):
    dispatch = models.ForeignKey(Dispatch, on_delete=models.CASCADE)
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True)
    outcome = models.CharField(max_length=24, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['dispatch', 'device'], name='one_notice_delivery_per_device')]
