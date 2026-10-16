"""Professional directory content, reviewed revisions and occurrence registrations."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class Country(models.Model):
    code = models.CharField(max_length=2, unique=True)
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    active = models.BooleanField(default=True)


class City(models.Model):
    country = models.ForeignKey(Country, on_delete=models.PROTECT)
    geonames_id = models.PositiveBigIntegerField(null=True, unique=True)
    region_ar = models.CharField(max_length=100, blank=True)
    region_en = models.CharField(max_length=100, blank=True)
    district_ar = models.CharField(max_length=100, blank=True)
    district_en = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)
    time_zone = models.CharField(max_length=80, blank=True)
    aliases = models.JSONField(default=list)
    search_text = models.TextField(blank=True)
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        from .search import normalize
        self.search_text = normalize(' '.join([self.name_ar, self.name_en, self.region_ar, self.region_en, self.district_ar, self.district_en, *self.aliases]))
        return super().save(*args, **kwargs)


class Category(models.Model):
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    active = models.BooleanField(default=True)


class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True)
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    active = models.BooleanField(default=True)


class Item(models.Model):
    KINDS = [('event', 'Event'), ('service', 'Service point')]
    STATUSES = [(value, value) for value in ('pending', 'approved', 'rejected', 'pending_changes', 'hidden', 'soft_deleted')]
    kind = models.CharField(max_length=10, choices=KINDS)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='directory_items')
    status = models.CharField(max_length=20, choices=STATUSES, default='pending')
    published_revision = models.ForeignKey('Revision', null=True, on_delete=models.SET_NULL, related_name='+')
    proposed_revision = models.ForeignKey('Revision', null=True, on_delete=models.SET_NULL, related_name='+')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='content_reviews')
    locked = models.BooleanField(default=False)
    rejection_reason = models.CharField(max_length=1000, blank=True)
    duplicate_flag = models.BooleanField(default=False)
    previous_status = models.CharField(max_length=20, blank=True)
    hidden_previous_status = models.CharField(max_length=20, blank=True)
    deleted_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(default=timezone.now)
    # Published-only indexes. Pending revisions never change the live catalogue.
    name = models.CharField(max_length=200, blank=True)
    normalized_name = models.CharField(max_length=200, blank=True, db_index=True)
    search_text = models.TextField(blank=True)
    country = models.ForeignKey(Country, null=True, on_delete=models.PROTECT)
    city = models.ForeignKey(City, null=True, on_delete=models.PROTECT)
    categories = models.ManyToManyField(Category)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    currency = models.ForeignKey(Currency, null=True, on_delete=models.PROTECT)
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)


class Revision(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='revisions')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    assets = models.ManyToManyField('Asset', related_name='revisions')
    payload = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)


class Occurrence(models.Model):
    event = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='occurrences')
    revision = models.ForeignKey(Revision, null=True, on_delete=models.SET_NULL)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField()
    time_zone = models.CharField(max_length=80)
    seat_limit = models.PositiveIntegerField()
    registration_deadline = models.DateTimeField(null=True)
    cancellation_cutoff_minutes = models.PositiveIntegerField(default=0)
    cancelled_at = models.DateTimeField(null=True)
    cancel_reason = models.CharField(max_length=80, blank=True)
    archived_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')), name='occurrence_positive_duration')]


class Registration(models.Model):
    STATES = [(value, value) for value in ('registered', 'waitlisted', 'pending_reconfirm', 'cancelled')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='event_registrations')
    occurrence = models.ForeignKey(Occurrence, on_delete=models.CASCADE, related_name='registrations')
    state = models.CharField(max_length=20, choices=STATES)
    queued_at = models.DateTimeField(default=timezone.now)
    reconfirm_deadline = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'occurrence'], name='one_registration_per_occurrence'),
            models.CheckConstraint(condition=models.Q(state__in=['registered', 'waitlisted', 'pending_reconfirm', 'cancelled']), name='known_registration_state')]


class RegistrationTransition(models.Model):
    registration = models.ForeignKey(Registration, null=True, on_delete=models.SET_NULL, related_name='transitions')
    occurrence_key = models.CharField(max_length=80)
    old_state = models.CharField(max_length=20, blank=True)
    new_state = models.CharField(max_length=20)
    reason = models.CharField(max_length=1000)
    created_at = models.DateTimeField(default=timezone.now)


class Notice(models.Model):
    """Durable notification intents. Actual FCM delivery is milestone 4."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=80)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)


class Report(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, null=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=20, choices=[('spam', 'Spam'), ('wrong_info', 'Wrong/fake info'), ('other', 'Other')])
    text = models.CharField(max_length=2000, blank=True)
    resolved_at = models.DateTimeField(null=True)
    resolution = models.CharField(max_length=20, blank=True)


class Feedback(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.CharField(max_length=3000)
    created_at = models.DateTimeField(default=timezone.now)


class Asset(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=80, unique=True)
    kind = models.CharField(max_length=10, choices=[('image', 'Image'), ('pdf', 'PDF')])
    content_type = models.CharField(max_length=50)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(default=timezone.now)


class EventView(models.Model):
    event = models.ForeignKey(Item, on_delete=models.CASCADE)
    day = models.DateField()
    fingerprint = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['event', 'day', 'fingerprint'], name='one_event_view_per_day')]


class EventViewTotal(models.Model):
    event = models.OneToOneField(Item, on_delete=models.CASCADE)
    count = models.PositiveIntegerField(default=0)


class Reminder(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    occurrence = models.ForeignKey(Occurrence, on_delete=models.CASCADE)
    offset_minutes = models.PositiveIntegerField()
    sent_for_start = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'occurrence'], name='one_reminder_per_occurrence')]


class OrganizerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bio = models.CharField(max_length=2000, blank=True)
    photo = models.ForeignKey(Asset, null=True, on_delete=models.SET_NULL)
