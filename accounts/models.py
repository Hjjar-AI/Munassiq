"""Account data only. No patient or clinical records."""
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        user = self.model(email=email.strip().lower(), **extra)
        user.set_password(password)
        user.full_clean(exclude=['password'])
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    language = models.CharField(max_length=2, choices=[('ar', 'العربية'), ('en', 'English')], default='ar')
    created_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    ban_reason = models.CharField(max_length=500, blank=True)
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        constraints = [models.UniqueConstraint(Lower('email'), name='account_email_case_unique')]

    def has_role(self, role):
        return self.is_active and self.role_grants.filter(role=role, user__is_active=True).exists()


class RoleGrant(models.Model):
    ROLES = [('organizer', 'Organizer'), ('moderator', 'Moderator'), ('admin', 'Admin')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='role_grants')
    role = models.CharField(max_length=16, choices=ROLES)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'role'], name='one_role_per_account'),
            models.CheckConstraint(condition=models.Q(role__in=['organizer', 'moderator', 'admin']), name='known_account_role')]


class Policy(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    terms_ar = models.TextField()
    terms_en = models.TextField()
    privacy_ar = models.TextField()
    privacy_en = models.TextField()


class Consent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    policy = models.ForeignKey(Policy, on_delete=models.PROTECT)
    accepted_at = models.DateTimeField(default=timezone.now)


class Session(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    access_hash = models.CharField(max_length=64, unique=True)
    refresh_hash = models.CharField(max_length=64, unique=True)
    access_expires_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(default=timezone.now)


class EmailToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    purpose = models.CharField(max_length=16, choices=[('verify', 'Verify'), ('reset', 'Reset'), ('change_email', 'Change email')])
    target_email = models.EmailField(blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)


class EmailMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    recipient = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    next_attempt_at = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True)


class LoginBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField(default=timezone.now)
    locked_until = models.DateTimeField(null=True)


class AuditEntry(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    target_id = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)


class OrganizerRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    workplace = models.CharField(max_length=200)
    reason = models.CharField(max_length=1000)
    credential_name = models.CharField(max_length=80, blank=True)
    credential_type = models.CharField(max_length=40)
    status = models.CharField(max_length=16, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='organizer_reviews')
    locked = models.BooleanField(default=False)
    decision_reason = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user'], condition=models.Q(status='pending'), name='one_open_organizer_request')]


class MaintenanceRun(models.Model):
    name = models.CharField(max_length=80)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True)
    processed = models.PositiveIntegerField(default=0)
