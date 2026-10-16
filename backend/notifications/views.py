from hashlib import sha256
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from accounts.models import User
from accounts.permissions import Administrator
from accounts.services import audit
from accounts.views import InputView, limited
from catalog.models import Category, Item, Report
from .models import Announcement, AppSettings, CategoryFollow, Device, OrganizerFollow, Preferences
from .serializers import (DeviceInputSerializer, DeviceSerializer, EmptySerializer,
    AnnouncementSerializer, AppSettingsSerializer, FollowPageSerializer, PreferencesSerializer, StatisticsSerializer)


class PreferenceView(InputView):
    serializer_class = PreferencesSerializer

    def output(self, row, user):
        return {**PreferencesSerializer(row).data, 'language': user.language}

    @extend_schema(responses=PreferencesSerializer)
    def get(self, request):
        row, _ = Preferences.objects.get_or_create(user=request.user)
        return Response(self.output(row, request.user))

    @extend_schema(responses=PreferencesSerializer)
    def patch(self, request):
        with transaction.atomic():
            row, _ = Preferences.objects.select_for_update().get_or_create(user=request.user)
            serializer = self.get_serializer(row, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            language = serializer.validated_data.pop('language', None)
            serializer.save()
            if language:
                User.objects.filter(pk=request.user.pk).update(language=language)
                request.user.language = language
            if request.user.has_role('moderator') or request.user.has_role('admin'):
                audit(request.user, 'notification.preferences_edit')
        return Response(self.output(row, request.user))


class DeviceListView(InputView):
    serializer_class = DeviceInputSerializer

    @extend_schema(responses=DeviceSerializer(many=True))
    def get(self, request):
        return Response(DeviceSerializer(Device.objects.filter(user=request.user).order_by('pk'), many=True).data)

    @extend_schema(responses={200: DeviceSerializer})
    def put(self, request):
        limited(request, 'device-register', 60)
        data = self.input(request)
        digest = sha256(data['token'].encode()).hexdigest()
        with transaction.atomic():
            get_object_or_404(User.objects.select_for_update(), pk=request.user.pk, is_active=True)
            # A token belongs to its most recently authenticated account. This
            # prevents a shared installation receiving its previous user's push.
            matching = Device.objects.select_for_update().filter(token_hash=digest).first()
            if matching and (matching.user_id != request.user.pk or matching.installation_id != data['installation_id']):
                matching.delete()
            if not Device.objects.filter(user=request.user, installation_id=data['installation_id']).exists() and Device.objects.filter(user=request.user).count() >= 20:
                raise ValidationError('Remove an old device before adding another.')
            row, _ = Device.objects.update_or_create(user=request.user,
                installation_id=data['installation_id'], defaults={
                    'token': data['token'], 'token_hash': digest, 'updated_at': timezone.now(), 'session': request.auth})
            if request.user.has_role('moderator') or request.user.has_role('admin'):
                audit(request.user, 'notification.device_register', row)
        return Response(DeviceSerializer(row).data)


class DeviceDetailView(InputView):
    serializer_class = EmptySerializer

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, device_id):
        with transaction.atomic():
            row = get_object_or_404(Device.objects.select_for_update(), user=request.user, pk=device_id)
            if request.user.has_role('moderator') or request.user.has_role('admin'):
                audit(request.user, 'notification.device_remove', row)
            row.delete()
        return Response(status=204)


class FollowListView(InputView):
    serializer_class = FollowPageSerializer

    @extend_schema(responses=FollowPageSerializer)
    def get(self, request):
        return Response({
            'organizer_ids': list(OrganizerFollow.objects.filter(user=request.user).order_by('organizer_id').values_list('organizer_id', flat=True)),
            'category_ids': list(CategoryFollow.objects.filter(user=request.user).order_by('category_id').values_list('category_id', flat=True)),
        })


class OrganizerFollowView(InputView):
    serializer_class = EmptySerializer

    @extend_schema(request=None, responses={204: None})
    def put(self, request, organizer_id):
        limited(request, 'follow', 120)
        with transaction.atomic():
            organizer = get_object_or_404(User, pk=organizer_id, is_active=True, role_grants__role='organizer')
            OrganizerFollow.objects.get_or_create(user=request.user, organizer=organizer)
            self.audit_change(request, organizer_id, 'organizer', 'follow')
        return Response(status=204)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, organizer_id):
        with transaction.atomic():
            OrganizerFollow.objects.filter(user=request.user, organizer_id=organizer_id).delete()
            self.audit_change(request, organizer_id, 'organizer', 'unfollow')
        return Response(status=204)

    def audit_change(self, request, target_id, kind, action):
        if request.user.has_role('moderator') or request.user.has_role('admin'):
            audit(request.user, f'notification.{kind}.{action}', target_id=target_id)


class CategoryFollowView(OrganizerFollowView):
    @extend_schema(request=None, responses={204: None})
    def put(self, request, category_id):
        limited(request, 'follow', 120)
        with transaction.atomic():
            category = get_object_or_404(Category, pk=category_id, active=True)
            CategoryFollow.objects.get_or_create(user=request.user, category=category)
            self.audit_change(request, category_id, 'category', 'follow')
        return Response(status=204)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, category_id):
        with transaction.atomic():
            CategoryFollow.objects.filter(user=request.user, category_id=category_id).delete()
            self.audit_change(request, category_id, 'category', 'unfollow')
        return Response(status=204)


class AdminStatisticsView(InputView):
    serializer_class = StatisticsSerializer
    permission_classes = [Administrator]

    @extend_schema(responses=StatisticsSerializer)
    def get(self, request):
        audit(request.user, 'statistics.read')
        return Response({
            'users': User.objects.count(), 'active_users': User.objects.filter(is_active=True).count(),
            'banned_users': User.objects.filter(is_active=False).count(),
            'events': Item.objects.filter(kind='event').exclude(status='soft_deleted').count(),
            'services': Item.objects.filter(kind='service').exclude(status='soft_deleted').count(),
            'unresolved_reports': Report.objects.filter(resolved_at=None).count(),
        })


class AdminAnnouncementView(InputView):
    permission_classes = [Administrator]
    serializer_class = AnnouncementSerializer

    @extend_schema(responses=AnnouncementSerializer(many=True))
    def get(self, request):
        audit(request.user, 'announcements.read')
        return Response(AnnouncementSerializer(Announcement.objects.order_by('-pk')[:100], many=True).data)

    @extend_schema(responses={201: AnnouncementSerializer})
    def post(self, request):
        from .services import announce
        data = self.input(request)
        with transaction.atomic():
            # Lock the author as well as the SQLite writer transaction so this
            # per-admin limit also remains atomic with PostgreSQL.
            author = User.objects.select_for_update().get(pk=request.user.pk)
            now = timezone.now()
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if Announcement.objects.filter(author=author, created_at__gte=midnight).count() >= settings.ANNOUNCEMENTS_PER_ADMIN_PER_DAY:
                raise ValidationError('Daily announcement limit reached (UTC day).')
            row = Announcement.objects.create(author=author, **data)
            announce(row)
            audit(request.user, 'announcement.create', row, audience=row.audience)
        return Response(AnnouncementSerializer(row).data, status=201)


class BannerView(InputView):
    permission_classes = [AllowAny]
    serializer_class = AnnouncementSerializer

    @extend_schema(responses=AnnouncementSerializer(many=True))
    def get(self, request):
        from .services import announcement_matches
        rows = Announcement.objects.filter(expires_at__gt=timezone.now()).order_by('-pk')
        if request.user and request.user.is_authenticated:
            pref = Preferences.objects.filter(user=request.user).first()
            if pref and not pref.announcements:
                return Response([])
            rows = [row for row in rows if announcement_matches(row, request.user, pref)]
        else:
            rows = rows.filter(audience='everyone')
        return Response(AnnouncementSerializer(list(rows)[:100], many=True).data)


class PublicSettingsView(InputView):
    permission_classes = [AllowAny]
    serializer_class = AppSettingsSerializer

    @extend_schema(responses=AppSettingsSerializer)
    def get(self, request):
        row = AppSettings.objects.filter(pk=1).first() or AppSettings()
        return Response(AppSettingsSerializer(row).data)


class AdminSettingsView(InputView):
    permission_classes = [Administrator]
    serializer_class = AppSettingsSerializer

    @extend_schema(responses=AppSettingsSerializer)
    def get(self, request):
        audit(request.user, 'app_settings.read')
        row = AppSettings.objects.filter(pk=1).first() or AppSettings()
        return Response(AppSettingsSerializer(row).data)

    @extend_schema(responses=AppSettingsSerializer)
    def patch(self, request):
        with transaction.atomic():
            row, _ = AppSettings.objects.select_for_update().get_or_create(pk=1)
            serializer = self.get_serializer(row, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            audit(request.user, 'app_settings.edit', row)
        return Response(serializer.data)
