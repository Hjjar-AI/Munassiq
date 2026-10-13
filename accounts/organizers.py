from datetime import timedelta
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from .credentials import credential_path, save_credential, validate_credential
from .models import EmailMessage, OrganizerRequest, RoleGrant
from .maintenance import remove_private_file
from .permissions import Administrator, Reviewer, VerifiedUser
from .serializers import MessageSerializer, OrganizerApplySerializer, OrganizerDecisionSerializer, OrganizerResultSerializer
from .services import audit
from .views import InputView, limited


def request_data(record):
    return {'id': record.pk, 'name': record.name, 'workplace': record.workplace,
        'reason': record.reason, 'status': record.status, 'locked': record.locked,
        'reviewer_name': record.reviewer.name if record.reviewer else None,
        'decision_reason': record.decision_reason, 'created_at': record.created_at}


class ApplyView(InputView):
    permission_classes = [VerifiedUser]
    serializer_class = OrganizerApplySerializer
    parser_classes = [MultiPartParser]

    @extend_schema(responses={201: OrganizerResultSerializer})
    def post(self, request):
        limited(request, 'credential-upload', 5)
        if request.user.has_role('organizer'):
            raise ValidationError('Organizer role already approved.')
        data = self.input(request)
        content, kind, extension = validate_credential(data.pop('credential'))
        name = ''
        try:
            with transaction.atomic():
                # Lock the account for both SQLite and a future PostgreSQL backend.
                user = type(request.user).objects.select_for_update().get(pk=request.user.pk)
                if OrganizerRequest.objects.filter(user=user, status='pending').exists():
                    raise ValidationError('An application is already open.')
                name = save_credential(content, extension)
                record = OrganizerRequest.objects.create(user=user, credential_name=name, credential_type=kind, **data)
        except Exception:
            if name:
                credential_path(name).unlink(missing_ok=True)
            raise
        return Response(request_data(record), status=201)


class MyRequestsView(InputView):
    serializer_class = OrganizerResultSerializer

    @extend_schema(responses=OrganizerResultSerializer(many=True))
    def get(self, request):
        records = OrganizerRequest.objects.filter(user=request.user).select_related('reviewer').order_by('-pk')[:50]
        return Response([request_data(record) for record in records])


class ReviewQueueView(InputView):
    permission_classes = [Reviewer]
    serializer_class = OrganizerResultSerializer

    @extend_schema(responses=OrganizerResultSerializer(many=True))
    def get(self, request):
        audit(request.user, 'organizer_request.queue_read')
        records = OrganizerRequest.objects.filter(status='pending').select_related('reviewer').order_by('pk')[:50]
        return Response([request_data(record) for record in records])


class ClaimView(InputView):
    permission_classes = [Reviewer]
    serializer_class = MessageSerializer

    @extend_schema(request=None, responses=MessageSerializer)
    def post(self, request, request_id):
        with transaction.atomic():
            record = get_object_or_404(OrganizerRequest.objects.select_for_update(), pk=request_id, status='pending')
            if record.locked and record.reviewer_id != request.user.pk:
                raise ValidationError('Another reviewer holds the lock.')
            record.locked, record.reviewer = True, request.user
            record.save(update_fields=['locked', 'reviewer'])
            audit(request.user, 'organizer_request.claim', record)
        return Response({'detail': 'Review claimed.'})


class UnlockView(InputView):
    permission_classes = [Administrator]
    serializer_class = MessageSerializer

    @extend_schema(request=None, responses=MessageSerializer)
    def post(self, request, request_id):
        with transaction.atomic():
            record = get_object_or_404(OrganizerRequest.objects.select_for_update(), pk=request_id, status='pending')
            record.locked, record.reviewer = False, None
            record.save(update_fields=['locked', 'reviewer'])
            audit(request.user, 'organizer_request.unlock', record)
        return Response({'detail': 'Review unlocked.'})


class CredentialView(InputView):
    permission_classes = [Reviewer]
    serializer_class = MessageSerializer

    @extend_schema(responses={(200, 'application/pdf'): bytes, (200, 'image/jpeg'): bytes})
    def get(self, request, request_id):
        record = get_object_or_404(OrganizerRequest, pk=request_id, status='pending')
        if not record.credential_name:
            raise ValidationError('Credential was deleted.')
        path = credential_path(record.credential_name)
        if not path.is_file():
            raise ValidationError('Credential unavailable.')
        audit(request.user, 'organizer_request.credential_read', record)
        response = FileResponse(path.open('rb'), content_type=record.credential_type, as_attachment=True,
            filename='credential.pdf' if record.credential_type == 'application/pdf' else 'credential.jpg')
        response['Cache-Control'] = 'no-store'
        return response


class DecideView(InputView):
    permission_classes = [Reviewer]
    serializer_class = OrganizerDecisionSerializer

    @extend_schema(responses=MessageSerializer)
    def post(self, request, request_id):
        data = self.input(request)
        with transaction.atomic():
            record = get_object_or_404(OrganizerRequest.objects.select_for_update().select_related('user'), pk=request_id, status='pending')
            if not record.locked or record.reviewer_id != request.user.pk:
                raise PermissionDenied('Claim this review before deciding.')
            record.status = 'approved' if data['approved'] else 'rejected'
            record.decision_reason = data['reason']
            record.decided_at = timezone.now()
            record.locked = False
            if data['approved']:
                RoleGrant.objects.get_or_create(user=record.user, role='organizer')
            name = record.credential_name
            transaction.on_commit(lambda: remove_private_file(name))
            record.credential_name = ''
            record.save()
            audit(request.user, 'organizer_request.' + record.status, record)
            EmailMessage.objects.create(user=record.user, recipient=record.user.email,
                subject='قرار طلب المنظّم / Organizer application decision',
                body=f'حالة الطلب / Application status: {record.status}\n{record.decision_reason}',
                expires_at=timezone.now()+timedelta(days=7))
        return Response({'detail': 'Decision saved; private credential deletion requested.'})
