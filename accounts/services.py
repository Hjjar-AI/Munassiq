"""Shared operations used by the API and future dashboard."""
import hashlib
from functools import lru_cache
import secrets
from datetime import timedelta
from urllib.parse import urlencode
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, Throttled, ValidationError
from .models import AuditEntry, Consent, EmailMessage, EmailToken, LoginBucket, Policy, RoleGrant, Session, User


@lru_cache(maxsize=1)
def dummy_password_hash():
    return make_password(secrets.token_urlsafe(48))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def validate_password(value):
    if len(value) < settings.PASSWORD_MIN_LENGTH:
        raise ValidationError({'password': f'Minimum length is {settings.PASSWORD_MIN_LENGTH}.'})
    if len(value) > 256:
        raise ValidationError({'password': 'Maximum length is 256.'})


def audit(actor, action, target=None, **metadata):
    return AuditEntry.objects.create(actor=actor, action=action,
        target_id=str(target.pk) if target else '', metadata=metadata)


def require_admin(actor):
    if not actor or not actor.has_role('admin'):
        raise PermissionDenied('Administrator role required.')


def user_data(user):
    return {'id': user.pk, 'email': user.email, 'name': user.name, 'language': user.language,
        'email_verified': bool(user.verified_at), 'roles': ['regular', *sorted(user.role_grants.values_list('role', flat=True))]}


def issue_session(user, session=None):
    now = timezone.now()
    access, refresh = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    if session is None:
        session = Session(user=user, expires_at=now + timedelta(days=settings.SESSION_DAYS))
    session.access_hash = digest(access)
    session.refresh_hash = digest(refresh)
    session.access_expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    session.save()
    return {'access_token': access, 'refresh_token': refresh, 'token_type': 'Bearer',
        'expires_in': settings.ACCESS_TOKEN_MINUTES * 60, 'user': user_data(user)}


def queue_token(user, purpose, target_email=''):
    now = timezone.now()
    # Superseded email links stop working; queued email retains no delivered tokens.
    EmailToken.objects.filter(user=user, purpose=purpose, used_at=None).update(used_at=now)
    token = secrets.token_urlsafe(48)
    lifetime = timedelta(hours=24) if purpose == 'verify' else timedelta(hours=1)
    record = EmailToken.objects.create(user=user, token_hash=digest(token), purpose=purpose,
        target_email=target_email, expires_at=now + lifetime)
    link = settings.APP_PUBLIC_URL.rstrip('/') + '/account-link/#' + urlencode({'purpose': purpose, 'token': token})
    labels = {'verify': ('تأكيد البريد الإلكتروني', 'Verify email'),
        'reset': ('إعادة تعيين كلمة المرور', 'Reset password'),
        'change_email': ('تأكيد تغيير البريد الإلكتروني', 'Confirm email change')}
    ar, en = labels[purpose]
    EmailMessage.objects.filter(user=user, subject=f'{ar} / {en}', sent_at=None).delete()
    EmailMessage.objects.create(user=user, recipient=target_email or user.email,
        subject=f'{ar} / {en}', expires_at=record.expires_at,
        body=f'{ar}\nاستخدم الرابط التالي. لا تشاركه مع أحد.\n\n{en}\nUse this link. Do not share it.\n\n{link}')


@transaction.atomic
def signup(data):
    policy = Policy.objects.order_by('-pk').first()
    if not policy or data['policy_id'] != policy.pk or not data['consent']:
        raise ValidationError({'consent': 'Accept the current terms and privacy policy.'})
    email = data['email'].strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({'email': 'Unable to create this account. Try account recovery.'})
    validate_password(data['password'])
    user = User.objects.create_user(email, data['password'], name=data['name'], language=data['language'])
    Consent.objects.create(user=user, policy=policy)
    queue_token(user, 'verify')
    return issue_session(user)


def rate_keys(email, address):
    return [salted_hmac('login-bucket', value).hexdigest() for value in ('email:' + email, 'ip:' + address)]


def login(email, password, address):
    email = email.strip().lower()
    now = timezone.now()
    # SQLite IMMEDIATE transactions serialize bucket updates. No failure exception
    # is raised until after commit, so failed attempts cannot roll back their count.
    with transaction.atomic():
        buckets = []
        for key in rate_keys(email, address):
            bucket, _ = LoginBucket.objects.select_for_update().get_or_create(key=key)
            if bucket.locked_until and bucket.locked_until > now:
                raise Throttled(wait=max(1, int((bucket.locked_until-now).total_seconds())))
            if now - bucket.window_start >= timedelta(minutes=settings.LOGIN_WINDOW_MINUTES):
                bucket.count = 0
                bucket.window_start = now
                bucket.locked_until = None
            buckets.append(bucket)
        user = User.objects.filter(email__iexact=email).first()
        valid = user.check_password(password) if user else check_password(password, dummy_password_hash())
        staff = bool(user and user.role_grants.filter(role__in=['admin', 'moderator']).exists())
        for bucket in buckets:
            bucket.count += 1
            limit = settings.STAFF_LOGIN_LIMIT if staff else settings.LOGIN_LIMIT
            # Count attempts even when credentials are correct to rate-limit the endpoint.
            if bucket.count >= limit:
                bucket.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            bucket.save()
        if valid and user.is_active:
            result = issue_session(user)
        else:
            result = None
    if not valid:
        raise AuthenticationFailed('Invalid email or password.')
    if not user.is_active:
        raise PermissionDenied({'detail': 'Account banned.', 'reason': user.ban_reason})
    return result


@transaction.atomic
def refresh(token):
    session = Session.objects.select_for_update().select_related('user').filter(
        refresh_hash=digest(token), revoked_at=None, expires_at__gt=timezone.now()).first()
    if not session or not session.user.is_active:
        raise AuthenticationFailed('Session expired or revoked.')
    return issue_session(session.user, session)


@transaction.atomic
def consume_token(token, purpose, password=None):
    record = EmailToken.objects.select_for_update().select_related('user').filter(
        token_hash=digest(token), purpose=purpose, used_at=None, expires_at__gt=timezone.now()).first()
    if not record or not record.user.is_active:
        raise ValidationError({'token': 'Expired or invalid link.'})
    user = User.objects.select_for_update().get(pk=record.user_id)
    if purpose == 'verify':
        user.verified_at = timezone.now()
    elif purpose == 'reset':
        validate_password(password)
        user.set_password(password)
        Session.objects.filter(user=user, revoked_at=None).update(revoked_at=timezone.now())
    else:
        if User.objects.exclude(pk=user.pk).filter(email__iexact=record.target_email).exists():
            raise ValidationError({'email': 'Email unavailable.'})
        user.email = record.target_email.lower()
        user.verified_at = timezone.now()
        Session.objects.filter(user=user, revoked_at=None).update(revoked_at=timezone.now())
    user.save()
    record.used_at = timezone.now()
    record.save(update_fields=['used_at'])


@transaction.atomic
def change_password(user, current, replacement):
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.check_password(current):
        raise ValidationError({'current_password': 'Incorrect password.'})
    validate_password(replacement)
    user.set_password(replacement)
    user.save(update_fields=['password'])
    Session.objects.filter(user=user, revoked_at=None).update(revoked_at=timezone.now())
    EmailToken.objects.filter(user=user, used_at=None).update(used_at=timezone.now())


@transaction.atomic
def change_email(user, password, email):
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.check_password(password):
        raise ValidationError({'password': 'Incorrect password.'})
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({'email': 'Email unavailable.'})
    queue_token(user, 'change_email', email.strip().lower())


@transaction.atomic
def set_role(actor, user, role, enabled):
    require_admin(actor)
    user = User.objects.select_for_update().get(pk=user.pk)
    if role == 'admin' and not enabled and user.role_grants.filter(role='admin').exists():
        if not RoleGrant.objects.filter(role='admin', user__is_active=True).exclude(user=user).exists():
            raise ValidationError('Cannot remove the last active administrator.')
    if enabled:
        RoleGrant.objects.get_or_create(user=user, role=role)
    else:
        RoleGrant.objects.filter(user=user, role=role).delete()
    audit(actor, 'role.grant' if enabled else 'role.remove', user, role=role)


@transaction.atomic
def set_ban(actor, user, banned, reason):
    require_admin(actor)
    user = User.objects.select_for_update().get(pk=user.pk)
    if banned and user.has_role('admin') and not RoleGrant.objects.filter(role='admin', user__is_active=True).exclude(user=user).exists():
        raise ValidationError('Cannot ban the last active administrator.')
    user.is_active = not banned
    user.ban_reason = reason if banned else ''
    user.save(update_fields=['is_active', 'ban_reason'])
    if banned:
        Session.objects.filter(user=user, revoked_at=None).update(revoked_at=timezone.now())
        EmailMessage.objects.filter(user=user, sent_at=None).delete()
    audit(actor, 'user.ban' if banned else 'user.unban', user)
