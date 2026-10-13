from datetime import timedelta
from django.db import transaction
from django.core.exceptions import RequestDataTooBig
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from . import services as svc
from .models import AuditEntry, Consent, LoginBucket, Policy, Session, User
from .permissions import Administrator
from .maintenance import delete_user
from .serializers import (BanSerializer, ChangeEmailSerializer, DeleteSerializer, EmailSerializer,
    LoginSerializer, MessageSerializer, PasswordSerializer, PolicySerializer, ProfileSerializer,
    RefreshSerializer, ResetSerializer, RoleSerializer, SessionSerializer, SignupSerializer,
    TokenSerializer, UserSerializer, CurrentPolicySerializer, AuditPageSerializer, UserPageSerializer, ExportSerializer)
from django.utils.crypto import salted_hmac


def limited(request, action, limit=10):
    """Persistent per-route/IP limit; do not trust caller-supplied forwarded headers."""
    key = salted_hmac('request-limit', action + ':' + request.META.get('REMOTE_ADDR', '')).hexdigest()
    now = timezone.now()
    with transaction.atomic():
        bucket, _ = LoginBucket.objects.select_for_update().get_or_create(key=key)
        if now - bucket.window_start >= timedelta(minutes=15):
            bucket.window_start, bucket.count = now, 0
        if bucket.count >= limit:
            raise Throttled(wait=max(1, int((bucket.window_start + timedelta(minutes=15)-now).total_seconds())))
        bucket.count += 1
        bucket.save()


class InputView(GenericAPIView):
    def handle_exception(self, exc):
        if isinstance(exc, RequestDataTooBig):
            exc = ValidationError({'detail': 'Upload exceeds the allowed size.'})
        return super().handle_exception(exc)

    def input(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class PublicInputView(InputView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_authenticate_header(self, request):
        # Public credential endpoints still return 401 for invalid credentials.
        return 'Bearer'


class SignupView(PublicInputView):
    serializer_class = SignupSerializer

    @extend_schema(responses={201: SessionSerializer})
    def post(self, request):
        limited(request, 'signup')
        return Response(svc.signup(self.input(request)), status=201)


class LoginView(PublicInputView):
    serializer_class = LoginSerializer

    @extend_schema(responses=SessionSerializer)
    def post(self, request):
        limited(request, 'login', 30)
        data = self.input(request)
        return Response(svc.login(data['email'], data['password'], request.META.get('REMOTE_ADDR', '')))


class RefreshView(PublicInputView):
    serializer_class = RefreshSerializer

    @extend_schema(responses=SessionSerializer)
    def post(self, request):
        limited(request, 'refresh', 120)
        return Response(svc.refresh(self.input(request)['refresh_token']))


class VerificationRequestView(PublicInputView):
    serializer_class = EmailSerializer
    purpose = 'verify'

    @extend_schema(responses=MessageSerializer)
    def post(self, request):
        limited(request, 'email-request')
        email = self.input(request)['email']
        with transaction.atomic():
            user = User.objects.select_for_update().filter(email__iexact=email, is_active=True).first()
            if user and (self.purpose != 'verify' or not user.verified_at):
                svc.queue_token(user, self.purpose)
        return Response({'detail': 'If eligible, an email will be sent. / إذا كان الحساب مؤهلاً، ستُرسل رسالة.'})


class ForgotPasswordView(VerificationRequestView):
    purpose = 'reset'


class VerifyView(PublicInputView):
    serializer_class = TokenSerializer
    purpose = 'verify'

    @extend_schema(responses=MessageSerializer)
    def post(self, request):
        limited(request, 'email-confirm', 30)
        data = self.input(request)
        svc.consume_token(data['token'], self.purpose, data.get('password'))
        return Response({'detail': 'Completed. / تم.'})


class ResetView(VerifyView):
    serializer_class = ResetSerializer
    purpose = 'reset'


class ConfirmEmailView(VerifyView):
    purpose = 'change_email'


class LogoutView(InputView):
    serializer_class = MessageSerializer
    all_devices = False

    @extend_schema(request=None, responses=MessageSerializer)
    def post(self, request):
        sessions = Session.objects.filter(user=request.user, revoked_at=None)
        if not self.all_devices:
            sessions = sessions.filter(pk=request.auth.pk)
        sessions.update(revoked_at=timezone.now())
        return Response({'detail': 'Logged out. / تم تسجيل الخروج.'})


class LogoutAllView(LogoutView):
    all_devices = True


class MeView(InputView):
    serializer_class = ProfileSerializer

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(svc.user_data(request.user))

    @extend_schema(responses=UserSerializer)
    def patch(self, request):
        for key, value in self.input(request).items():
            setattr(request.user, key, value)
        request.user.save(update_fields=['name', 'language'])
        return Response(svc.user_data(request.user))

    @extend_schema(request=DeleteSerializer, responses={204: None})
    def delete(self, request):
        serializer = DeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if not user.check_password(serializer.validated_data['password']):
                raise ValidationError({'password': 'Incorrect password.'})
            if user.has_role('admin') and not User.objects.filter(is_active=True, role_grants__role='admin').exclude(pk=user.pk).exists():
                raise ValidationError('Cannot delete the last active administrator.')
            if user.role_grants.filter(role__in=['admin', 'moderator']).exists():
                svc.audit(user, 'account.self_delete', user)
            delete_user(user)
        return Response(status=204)


class ChangePasswordView(InputView):
    serializer_class = PasswordSerializer

    @extend_schema(responses=MessageSerializer)
    def post(self, request):
        limited(request, 'password-change')
        data = self.input(request)
        svc.change_password(request.user, data['current_password'], data['password'])
        return Response({'detail': 'Password changed; all sessions revoked.'})


class ChangeEmailView(InputView):
    serializer_class = ChangeEmailSerializer

    @extend_schema(responses=MessageSerializer)
    def post(self, request):
        limited(request, 'email-change')
        data = self.input(request)
        svc.change_email(request.user, data['password'], data['email'])
        return Response({'detail': 'Confirmation sent to the new address.'})


class ExportView(InputView):
    serializer_class = UserSerializer

    @extend_schema(responses=ExportSerializer)
    def get(self, request):
        data = svc.user_data(request.user)
        data['created_at'] = request.user.created_at
        data['consents'] = list(Consent.objects.filter(user=request.user).values('policy_id', 'accepted_at'))
        from .models import OrganizerRequest
        data['organizer_requests'] = list(OrganizerRequest.objects.filter(user=request.user).values(
            'id', 'name', 'workplace', 'reason', 'status', 'decision_reason', 'created_at', 'decided_at'))
        data['sessions'] = list(Session.objects.filter(user=request.user).values('created_at', 'expires_at', 'revoked_at'))
        from catalog.models import Item, Registration, Report, Feedback, Reminder, OrganizerProfile
        data['items'] = [{'id': item.pk, 'kind': item.kind, 'status': item.status,
            'revisions': list(item.revisions.values('id', 'payload', 'created_at'))}
            for item in Item.objects.filter(owner=request.user)]
        data['registrations'] = list(Registration.objects.filter(user=request.user).values('id', 'occurrence_id', 'state', 'reconfirm_deadline'))
        data['reports'] = list(Report.objects.filter(user=request.user).values('item_id', 'reason', 'text', 'resolution'))
        from catalog.models import Asset
        data['uploads'] = list(Asset.objects.filter(owner=request.user).values('id', 'kind', 'size', 'created_at'))
        data['reminders'] = list(Reminder.objects.filter(user=request.user).values('occurrence_id', 'offset_minutes'))
        data['organizer_profile'] = list(OrganizerProfile.objects.filter(user=request.user).values('bio', 'photo_id'))
        data['feedback'] = list(Feedback.objects.filter(user=request.user).values('text', 'created_at'))
        response = Response(data)
        response['Content-Disposition'] = 'attachment; filename="munassiq-account.json"'
        response['Cache-Control'] = 'no-store'
        return response


class PolicyView(PublicInputView):
    serializer_class = PolicySerializer

    @extend_schema(responses=CurrentPolicySerializer)
    def get(self, request):
        policy = get_object_or_404(Policy.objects.order_by('-pk'))
        return Response({'id': policy.pk, 'created_at': policy.created_at, **PolicySerializer(policy).data})


class AdminRoleView(InputView):
    permission_classes = [Administrator]
    serializer_class = RoleSerializer

    @extend_schema(responses=MessageSerializer)
    def post(self, request, user_id):
        data = self.input(request)
        svc.set_role(request.user, get_object_or_404(User, pk=user_id), data['role'], data['enabled'])
        return Response({'detail': 'Role updated.'})


class AdminBanView(InputView):
    permission_classes = [Administrator]
    serializer_class = BanSerializer

    @extend_schema(responses=MessageSerializer)
    def post(self, request, user_id):
        data = self.input(request)
        svc.set_ban(request.user, get_object_or_404(User, pk=user_id), data['banned'], data['reason'])
        return Response({'detail': 'Ban status updated.'})


class AdminPolicyView(InputView):
    permission_classes = [Administrator]
    serializer_class = PolicySerializer

    @extend_schema(responses={201: CurrentPolicySerializer})
    def post(self, request):
        with transaction.atomic():
            policy = Policy.objects.create(**self.input(request))
            svc.audit(request.user, 'policy.publish', policy)
        return Response({'id': policy.pk, **PolicySerializer(policy).data}, status=201)


class AdminAuditView(InputView):
    permission_classes = [Administrator]
    serializer_class = MessageSerializer

    @extend_schema(responses=AuditPageSerializer)
    def get(self, request):
        svc.audit(request.user, 'audit.read')
        try:
            before = int(request.query_params.get('before', '0'))
        except ValueError:
            raise ValidationError({'before': 'Use an integer cursor.'})
        entries = AuditEntry.objects.order_by('-pk')
        if before:
            entries = entries.filter(pk__lt=before)
        rows = list(entries.values('id', 'actor_id', 'action', 'target_id', 'metadata', 'created_at')[:50])
        return Response({'results': rows, 'next_before': rows[-1]['id'] if len(rows) == 50 else None})


def account_link(request):
    response = render(request, 'accounts/account_link.html')
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response


class AdminUsersView(InputView):
    permission_classes = [Administrator]
    serializer_class = UserSerializer

    @extend_schema(responses=UserPageSerializer)
    def get(self, request):
        svc.audit(request.user, 'users.list')
        try:
            after = int(request.query_params.get('after', '0'))
        except ValueError:
            raise ValidationError({'after': 'Use an integer cursor.'})
        users = list(User.objects.filter(pk__gt=after).order_by('pk').prefetch_related('role_grants')[:50])
        return Response({'results': [svc.user_data(user) for user in users],
            'next_after': users[-1].pk if len(users) == 50 else None})


class AdminDeleteUserView(InputView):
    permission_classes = [Administrator]
    serializer_class = MessageSerializer

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, user_id):
        with transaction.atomic():
            user = get_object_or_404(User.objects.select_for_update(), pk=user_id)
            if user.has_role('admin') and not User.objects.filter(is_active=True, role_grants__role='admin').exclude(pk=user.pk).exists():
                raise ValidationError('Cannot delete the last active administrator.')
            svc.audit(request.user, 'user.delete', user)
            delete_user(user)
        return Response(status=204)
