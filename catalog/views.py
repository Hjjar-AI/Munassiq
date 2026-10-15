import secrets
from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import F, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.crypto import salted_hmac
from drf_spectacular.utils import extend_schema, extend_schema_view, PolymorphicProxySerializer
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from accounts.permissions import Administrator, Reviewer, VerifiedUser
from accounts.serializers import MessageSerializer
from accounts.services import audit
from accounts.views import InputView, limited
from . import registration as reg, services as svc
from .files import path_for, store
from .models import (Asset, Category, City, Country, Currency, EventView, EventViewTotal, Feedback,
    Item, Notice, Occurrence, Registration, Report)
from .presentation import display_zone, item_data, occurrence_data, registration_data
from .search import normalize
from .serializers import (AssetSerializer, CategorySerializer, CitySerializer, CountrySerializer,
    CurrencySerializer, DecisionSerializer, DuplicateCheckSerializer, DuplicateResultSerializer,
    DuplicateSerializer, EventSerializer, FeedbackResultSerializer, FeedbackSerializer,
    ItemPageSerializer, ItemResultSerializer, OccurrenceSerializer, OccurrenceDetailSerializer, QuerySerializer,
    RegistrationResultSerializer, RegistrantSerializer, RemoveRegistrationSerializer,
    ReportResolutionSerializer, ReportResultSerializer, ReportSerializer,
    RescheduleSerializer, ServiceSerializer, StatsSerializer, UploadSerializer, ViewResultSerializer)


def paged(values, page):
    offset = (page-1)*30
    return {'results': values[offset:offset+30], 'next_page': page+1 if len(values) > offset+30 else None}


def query_input(request):
    serializer = QuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    result = serializer.validated_data
    display_zone(result['time_zone'])
    if result['sort'] == 'price' and 'currency' not in result:
        raise ValidationError({'currency': 'Choose one currency for price sorting.'})
    return result


def matches(payload, options):
    for parameter, field in [('country', 'country_id'), ('city', 'city_id'), ('currency', 'currency_id')]:
        if parameter in options and payload.get(field) != options[parameter]:
            return False
    if 'category' in options and options['category'] not in payload['category_ids']:
        return False
    text = normalize(' '.join(str(payload.get(key, '')) for key in ('name', 'title', 'description', 'speaker_name', 'topic', 'address')))
    return all(word in text for word in normalize(options['q']).split())


def catalog_values(request, options, kind=None):
    values = []
    for item in svc.public_items(kind).select_related('published_revision').order_by('pk'):
        selected = None
        if item.kind == 'event':
            selected = []
            for occurrence in item.occurrences.select_related('revision').order_by('starts_at', 'pk'):
                old = svc.archived(occurrence)
                if (options['archived_only'] and not old) or (not options['archive'] and not options['archived_only'] and old):
                    continue
                payload = (occurrence.revision or item.published_revision).payload
                if matches(payload, options):
                    selected.append(occurrence.pk)
            if not selected:
                continue
        elif not matches(item.published_revision.payload, options):
            continue
        data = item_data(item, request.user, include_archive=options['archive'] or options['archived_only'],
            archived_only=options['archived_only'], user_zone=options['time_zone'], occurrence_ids=selected)
        if item.kind == 'service' and options['open_now'] and not data['open_now']:
            continue
        if options['sort'] == 'price' and data['payload'].get('price') is None:
            continue
        values.append(data)
    if options['sort'] == 'price':
        from decimal import Decimal
        values.sort(key=lambda row: (Decimal(row['payload']['price']), row['id']))
    elif kind == 'event' or options['sort'] == 'date':
        values.sort(key=lambda row: (row.get('date_range', {}).get('start', datetime.max.replace(tzinfo=timezone.now().tzinfo)), row['id']))
    else:
        query = normalize(options['q'])
        values.sort(key=lambda row: (0 if query and normalize(row['payload'].get('name', row['payload'].get('title', ''))) == query else 1,
            normalize(row['payload'].get('name', row['payload'].get('title', ''))), row['id']))
    return values


class ReferenceListView(InputView):
    model = Category
    serializer_class = CategorySerializer
    write_permission = Reviewer

    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else [self.write_permission()]

    def get(self, request):
        rows = self.model.objects.filter(active=True).order_by('pk')
        if self.model is City:
            rows = rows.filter(country__active=True)
            if 'country' in request.query_params:
                try:
                    country = int(request.query_params['country'])
                except ValueError:
                    raise ValidationError({'country': 'Choose a country ID.'})
                rows = rows.filter(country_id=country)
            for word in normalize(request.query_params.get('q', '')[:200]).split():
                rows = rows.filter(search_text__contains=word)
            try:
                page = int(request.query_params.get('page', '1'))
            except ValueError:
                raise ValidationError({'page': 'Use a positive page number.'})
            if page < 1:
                raise ValidationError({'page': 'Use a positive page number.'})
            values = list(rows[(page-1)*50:page*50+1])
            response = Response(self.get_serializer(values[:50], many=True).data)
            if len(values) > 50:
                response['X-Next-Page'] = str(page+1)
            response['X-Location-Attribution'] = 'GeoNames, CC BY 4.0'
            return response
        return Response(self.get_serializer(rows, many=True).data)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            record = serializer.save()
            audit(request.user, self.model.__name__.lower()+'.create', record)
        return Response(serializer.data, status=201)


@extend_schema_view(get=extend_schema(operation_id='categories_list', responses=CategorySerializer(many=True)), post=extend_schema(responses={201: CategorySerializer}))
class CategoryListView(ReferenceListView):
    pass


@extend_schema_view(get=extend_schema(operation_id='countries_list', responses=CountrySerializer(many=True)), post=extend_schema(responses={201: CountrySerializer}))
class CountryListView(ReferenceListView):
    model, serializer_class, write_permission = Country, CountrySerializer, Administrator


@extend_schema_view(get=extend_schema(operation_id='cities_list', responses=CitySerializer(many=True)), post=extend_schema(responses={201: CitySerializer}))
class CityListView(ReferenceListView):
    model, serializer_class, write_permission = City, CitySerializer, Administrator


@extend_schema_view(get=extend_schema(operation_id='currencies_list', responses=CurrencySerializer(many=True)), post=extend_schema(responses={201: CurrencySerializer}))
class CurrencyListView(ReferenceListView):
    model, serializer_class, write_permission = Currency, CurrencySerializer, Administrator


class CategoryDetailView(InputView):
    serializer_class = CategorySerializer

    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else [Reviewer()]

    def get(self, request, category_id):
        return Response(self.get_serializer(get_object_or_404(Category, pk=category_id)).data)

    def patch(self, request, category_id):
        with transaction.atomic():
            record = get_object_or_404(Category.objects.select_for_update(), pk=category_id)
            serializer = self.get_serializer(record, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            audit(request.user, 'category.edit', record)
        return Response(serializer.data)


class ItemListView(InputView):
    kind = 'event'
    serializer_class = EventSerializer

    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else super().get_permissions()

    @extend_schema(operation_id='events_list', parameters=[QuerySerializer], responses=ItemPageSerializer)
    def get(self, request):
        options = query_input(request)
        return Response(paged(catalog_values(request, options, self.kind), options['page']))

    @extend_schema(responses={201: ItemResultSerializer})
    def post(self, request):
        item = svc.create_item(request.user, self.kind, request.data)
        return Response(item_data(item, request.user, private=True), status=201)


@extend_schema_view(get=extend_schema(operation_id='services_list'))
class ServiceListView(ItemListView):
    kind, serializer_class = 'service', ServiceSerializer


class ItemDetailView(InputView):
    kind = 'event'
    serializer_class = EventSerializer

    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else super().get_permissions()

    @extend_schema(responses=ItemResultSerializer)
    def get(self, request, item_id):
        item = get_object_or_404(Item.objects.select_related('published_revision', 'proposed_revision', 'reviewer'), pk=item_id, kind=self.kind)
        if item.status not in svc.PUBLIC_STATUSES or not item.published_revision_id:
            if not request.user or item.owner_id != request.user.pk:
                raise PermissionDenied('This item is not public.')
            return Response(item_data(item, request.user, private=True))
        return Response(item_data(item, request.user, include_archive=True, user_zone=request.query_params.get('time_zone', 'UTC')))

    @extend_schema(responses=ItemResultSerializer)
    def patch(self, request, item_id):
        get_object_or_404(Item, pk=item_id, kind=self.kind)
        item = svc.edit_item(request.user, item_id, request.data)
        return Response(item_data(item, request.user, private=True))


class ServiceDetailView(ItemDetailView):
    kind, serializer_class = 'service', ServiceSerializer


class MyItemsView(InputView):
    serializer_class = ItemResultSerializer

    @extend_schema(responses=ItemPageSerializer)
    def get(self, request):
        options = query_input(request)
        values = [item_data(row, request.user, private=True) for row in Item.objects.filter(owner=request.user).select_related('published_revision', 'proposed_revision', 'reviewer').order_by('-pk')]
        return Response(paged(values, options['page']))


class ReviewQueueView(InputView):
    permission_classes = [Reviewer]
    serializer_class = ItemResultSerializer

    @extend_schema(operation_id='moderation_items_list', responses=ItemPageSerializer)
    def get(self, request):
        audit(request.user, 'item.review_queue_read')
        options = query_input(request)
        values = [item_data(row, request.user, private=True) for row in Item.objects.filter(status__in=['pending', 'pending_changes']).select_related('published_revision', 'proposed_revision', 'reviewer').order_by('pk')]
        return Response(paged(values, options['page']))


class ClaimView(InputView):
    permission_classes = [Reviewer]
    serializer_class = MessageSerializer

    @extend_schema(request=None, responses=ItemResultSerializer)
    def post(self, request, item_id):
        return Response(item_data(svc.claim_review(request.user, item_id), request.user, private=True))


class DecisionView(InputView):
    permission_classes = [Reviewer]
    serializer_class = DecisionSerializer

    @extend_schema(responses=ItemResultSerializer)
    def post(self, request, item_id):
        data = self.input(request)
        return Response(item_data(svc.decide(request.user, item_id, data['approved'], data['reason']), request.user, private=True))


class UnlockView(InputView):
    permission_classes = [Administrator]
    serializer_class = MessageSerializer

    @extend_schema(request=None, responses=ItemResultSerializer)
    def post(self, request, item_id):
        return Response(item_data(svc.unlock(request.user, item_id), request.user, private=True))


class ModerateItemView(InputView):
    permission_classes = [Reviewer]
    serializer_class = ItemResultSerializer

    def get(self, request, item_id):
        item = get_object_or_404(Item.objects.select_related('published_revision', 'proposed_revision', 'reviewer'), pk=item_id)
        audit(request.user, 'item.review_read', item)
        return Response(item_data(item, request.user, private=True))

    @extend_schema(request=PolymorphicProxySerializer(component_name='ModeratedContent', serializers=[EventSerializer, ServiceSerializer], resource_type_field_name=None), responses=ItemResultSerializer)
    def patch(self, request, item_id):
        return Response(item_data(svc.edit_item(request.user, item_id, request.data, moderator=True), request.user, private=True))

    @extend_schema(request=None, responses=ItemResultSerializer)
    def delete(self, request, item_id):
        return Response(item_data(svc.change_visibility(request.user, item_id, 'delete'), request.user, private=True))


class VisibilityView(InputView):
    permission_classes = [Reviewer]
    serializer_class = MessageSerializer
    action = 'hide'

    @extend_schema(request=None, responses=ItemResultSerializer)
    def post(self, request, item_id):
        return Response(item_data(svc.change_visibility(request.user, item_id, self.action), request.user, private=True))


class RestoreView(VisibilityView):
    action = 'restore'


class UnhideView(VisibilityView):
    action = 'unhide'


class DuplicateCheckView(InputView):
    serializer_class = DuplicateCheckSerializer

    @extend_schema(responses=DuplicateResultSerializer)
    def post(self, request):
        svc.require_creator(request.user)
        return Response({'similar_name_exists': bool(svc.duplicate_services(self.input(request)['name']))})


class DuplicateView(InputView):
    serializer_class = DuplicateSerializer

    @extend_schema(responses={201: ItemResultSerializer})
    def post(self, request, item_id):
        svc.require_creator(request.user)
        item = get_object_or_404(Item.objects.select_related('published_revision', 'proposed_revision'), pk=item_id, kind='event')
        if item.owner_id != request.user.pk and (item.status not in svc.PUBLIC_STATUSES or not item.published_revision_id):
            raise PermissionDenied('Only public templates or your own items can be duplicated.')
        revision = item.published_revision or item.proposed_revision
        payload = dict(revision.payload)
        data = self.input(request)
        old_start = datetime.fromisoformat(payload['starts_at'].replace('Z', '+00:00'))
        if payload['registration_deadline']:
            deadline = datetime.fromisoformat(payload['registration_deadline'].replace('Z', '+00:00'))
            payload['registration_deadline'] = (data['starts_at']-(old_start-deadline)).isoformat()
        payload.update({key: value.isoformat() if isinstance(value, datetime) else value for key, value in data.items()})
        new = svc.create_item(request.user, 'event', payload)
        return Response(item_data(new, request.user, private=True), status=201)


class OccurrenceView(InputView):
    permission_classes = [AllowAny]
    serializer_class = OccurrenceDetailSerializer

    def get(self, request, occurrence_id):
        row = get_object_or_404(Occurrence.objects.select_related('event'), pk=occurrence_id, event__in=svc.public_items('event'))
        result = occurrence_data(row, request.query_params.get('time_zone', 'UTC'))
        result['payload'] = dict((row.revision or row.event.published_revision).payload)
        if not request.user:
            from .presentation import PROTECTED_FIELDS
            for key in PROTECTED_FIELDS:
                result['payload'].pop(key, None)
        return Response(result)


class RegisterView(InputView):
    permission_classes = [VerifiedUser]
    serializer_class = MessageSerializer

    @extend_schema(request=None, responses={201: RegistrationResultSerializer})
    def post(self, request, occurrence_id):
        record, warning = reg.register(request.user, occurrence_id)
        return Response(registration_data(record, warning), status=201)


class CancelRegistrationView(InputView):
    serializer_class = MessageSerializer

    @extend_schema(request=None, responses=RegistrationResultSerializer)
    def post(self, request, registration_id):
        return Response(registration_data(reg.cancel(request.user, registration_id)))


class ReconfirmView(CancelRegistrationView):
    @extend_schema(request=None, responses=RegistrationResultSerializer)
    def post(self, request, registration_id):
        return Response(registration_data(reg.reconfirm(request.user, registration_id)))


class MyRegistrationsView(InputView):
    serializer_class = RegistrationResultSerializer

    @extend_schema(responses=RegistrationResultSerializer(many=True))
    def get(self, request):
        rows = Registration.objects.filter(user=request.user).order_by('-pk')
        return Response([registration_data(row) for row in rows])


class SeriesRegistrationView(InputView):
    permission_classes = [VerifiedUser]
    serializer_class = MessageSerializer

    @extend_schema(request=None, responses=RegistrationResultSerializer(many=True))
    def post(self, request, item_id):
        return Response([registration_data(row, warning) for row, warning in reg.register_series(request.user, item_id)], status=201)


class CancelEventView(InputView):
    serializer_class = MessageSerializer

    @extend_schema(request=None, responses=OccurrenceSerializer)
    def post(self, request, occurrence_id):
        return Response(occurrence_data(reg.cancel_event(request.user, occurrence_id)))


class RescheduleView(InputView):
    serializer_class = RescheduleSerializer

    @extend_schema(responses=OccurrenceSerializer)
    def post(self, request, occurrence_id):
        return Response(occurrence_data(reg.reschedule(request.user, occurrence_id, **self.input(request))))


class RemoveRegistrationView(InputView):
    serializer_class = RemoveRegistrationSerializer

    @extend_schema(responses=RegistrationResultSerializer)
    def post(self, request, registration_id):
        return Response(registration_data(reg.cancel(request.user, registration_id, force=True, reason=self.input(request)['reason'])))


class UploadView(InputView):
    serializer_class = UploadSerializer
    parser_classes = [MultiPartParser]
    kind = 'image'

    @extend_schema(responses={201: AssetSerializer})
    def post(self, request):
        svc.require_creator(request.user)
        limited(request, 'directory-upload', 15)
        asset = store(request.user, self.input(request)['file'], self.kind)
        return Response({'id': asset.pk, 'kind': asset.kind, 'size': asset.size}, status=201)


class PdfUploadView(UploadView):
    kind = 'pdf'


class FileView(InputView):
    permission_classes = [AllowAny]
    serializer_class = MessageSerializer

    @extend_schema(responses={(200, 'application/pdf'): bytes, (200, 'image/jpeg'): bytes})
    def get(self, request, asset_id):
        asset = get_object_or_404(Asset, pk=asset_id)
        public = svc.public_items().filter(published_revision__assets=asset).exists() or asset.organizerprofile_set.filter(Q(user__role_grants__role='organizer') | Q(user__directory_items__status__in=svc.PUBLIC_STATUSES)).exists()
        owner = bool(request.user and (asset.owner_id == request.user.pk or
            Item.objects.filter(owner=request.user, revisions__assets=asset).exists()))
        reviewer = svc.is_reviewer(request.user)
        if not public and not owner and not reviewer:
            raise PermissionDenied('This attachment is private.')
        if reviewer and not public:
            audit(request.user, 'item.attachment_read', asset)
        path = path_for(asset)
        if not path.is_file():
            raise ValidationError('Attachment is unavailable.')
        response = FileResponse(path.open('rb'), content_type=asset.content_type,
            as_attachment=asset.kind == 'pdf', filename='event.pdf' if asset.kind == 'pdf' else 'photo.jpg')
        response['Cache-Control'] = 'no-store' if not public else 'public, max-age=300'
        return response


class ReportView(InputView):
    serializer_class = ReportSerializer

    @extend_schema(responses={201: MessageSerializer})
    def post(self, request):
        data = self.input(request)
        get_object_or_404(svc.public_items(), pk=data['item_id'])
        Report.objects.create(user=request.user, **data)
        return Response({'detail': 'Report received.'}, status=201)


class FeedbackView(InputView):
    serializer_class = FeedbackSerializer

    @extend_schema(responses={201: MessageSerializer})
    def post(self, request):
        Feedback.objects.create(user=request.user, **self.input(request))
        return Response({'detail': 'Feedback received.'}, status=201)


class ReportListView(InputView):
    permission_classes = [Reviewer]
    serializer_class = ReportResultSerializer

    @extend_schema(responses=ReportResultSerializer(many=True))
    def get(self, request):
        audit(request.user, 'reports.read')
        return Response(list(Report.objects.filter(resolved_at=None).values('id', 'item_id', 'reason', 'text', 'resolution')[:100]))


class FeedbackListView(InputView):
    permission_classes = [Reviewer]
    serializer_class = FeedbackResultSerializer

    @extend_schema(responses=FeedbackResultSerializer(many=True))
    def get(self, request):
        audit(request.user, 'feedback.read')
        return Response(list(Feedback.objects.order_by('-pk').values('id', 'text', 'created_at')[:100]))


class ResolveReportView(InputView):
    permission_classes = [Reviewer]
    serializer_class = ReportResolutionSerializer

    @extend_schema(responses=MessageSerializer)
    def post(self, request, report_id):
        data = self.input(request)
        with transaction.atomic():
            record = get_object_or_404(Report.objects.select_for_update(), pk=report_id, resolved_at=None)
            if data['action'] == 'hide' and record.item_id:
                svc.change_visibility(request.user, record.item_id, 'hide')
            elif data['action'] == 'warn' and record.item and record.item.owner_id:
                svc.notify_owner(record.item, 'organizer.warning', reason=data['reason'])
            record.resolution, record.resolved_at = data['action'], timezone.now()
            record.save(update_fields=['resolution', 'resolved_at'])
            audit(request.user, 'report.'+data['action'], record)
        return Response({'detail': 'Report resolved.'})


class EventViewCount(InputView):
    permission_classes = [AllowAny]
    serializer_class = MessageSerializer

    @extend_schema(request=None, responses=ViewResultSerializer)
    def post(self, request, item_id):
        item = get_object_or_404(svc.public_items('event'), pk=item_id)
        cookie = request.COOKIES.get('munassiq_viewer', '')
        if len(cookie) != 64:
            cookie = secrets.token_hex(32)
        user = request.user
        counted = False
        if not svc.is_reviewer(user) and not (user and item.owner_id == user.pk):
            key = f'user:{user.pk}' if user else 'guest:'+cookie
            fingerprint = salted_hmac('event-view', f'{timezone.now().date()}:{key}').hexdigest()
            with transaction.atomic():
                _, counted = EventView.objects.get_or_create(event=item, day=timezone.now().date(), fingerprint=fingerprint)
                if counted:
                    total, _ = EventViewTotal.objects.get_or_create(event=item)
                    EventViewTotal.objects.filter(pk=total.pk).update(count=F('count')+1)
        response = Response({'counted': counted})
        if not user:
            response.set_cookie('munassiq_viewer', cookie, max_age=86400, httponly=True, secure=request.is_secure(), samesite='Lax')
        return response


class StatsView(InputView):
    serializer_class = StatsSerializer

    def get(self, request, occurrence_id):
        row = get_object_or_404(Occurrence.objects.select_related('event'), pk=occurrence_id)
        if not request.user.has_role('admin') and not (request.user.has_role('organizer') and row.event.owner_id == request.user.pk):
            raise PermissionDenied('Statistics require admin authority or organizer ownership.')
        if request.user.has_role('admin'):
            audit(request.user, 'event.stats_read', row)
        total = EventViewTotal.objects.filter(event=row.event).first()
        return Response({'views': total.count if total else 0,
            **{state: row.registrations.filter(state=state).count() for state in reg.SEATED+['waitlisted']}})


class RegistrantsView(InputView):
    serializer_class = RegistrantSerializer

    @extend_schema(responses=RegistrantSerializer(many=True))
    def get(self, request, occurrence_id):
        from .exports import registrants, require_registrant_access
        row = get_object_or_404(Occurrence.objects.select_related('event__owner'), pk=occurrence_id)
        require_registrant_access(request.user, row)
        if svc.is_reviewer(request.user):
            audit(request.user, 'event.registrants_read', row)
        response = Response([{'id': value.pk, 'name': value.user.name, 'email': value.user.email, 'state': value.state}
            for value in registrants(row, request.query_params.get('state'))])
        response['Cache-Control'] = 'no-store'
        return response


class ExportNegotiation(DefaultContentNegotiation):
    def select_renderer(self, request, renderers, format_suffix=None):
        # File responses set their own MIME type. API errors remain JSON, while
        # the export's format=csv/pdf parameter does not select a DRF renderer.
        return renderers[0], renderers[0].media_type


class RegistrantExportView(InputView):
    content_negotiation_class = ExportNegotiation
    serializer_class = MessageSerializer

    @extend_schema(responses={(200, 'application/pdf'): bytes, (200, 'text/csv'): str})
    def get(self, request, occurrence_id):
        from .exports import export_csv, export_pdf, registrants, require_registrant_access
        row = get_object_or_404(Occurrence.objects.select_related('event__owner'), pk=occurrence_id)
        require_registrant_access(request.user, row)
        kind = request.query_params.get('format', 'csv')
        if kind not in ['csv', 'pdf']:
            raise ValidationError({'format': 'Choose csv or pdf.'})
        if svc.is_reviewer(request.user):
            audit(request.user, 'event.registrants_export', row, format=kind)
        rows = registrants(row, request.query_params.get('state'))
        return export_csv(rows) if kind == 'csv' else export_pdf(rows)


class MapView(InputView):
    permission_classes = [AllowAny]
    serializer_class = ItemResultSerializer

    @extend_schema(responses=ItemPageSerializer)
    def get(self, request):
        # Bounded marker data; clustering is done by map clients in dashboard/Android.
        options = query_input(request)
        query = svc.public_items('service').order_by('pk')
        for parameter, field in [('country', 'country_id'), ('city', 'city_id'), ('category', 'categories__pk')]:
            if parameter in options:
                query = query.filter(**{field: options[parameter]})
        values = [{'id': row.pk, 'kind': row.kind, 'status': 'approved', 'owner_id': row.owner_id,
            'payload': {'name': row.name, 'latitude': row.latitude, 'longitude': row.longitude}}
            for row in query.distinct()]
        return Response(paged(values, options['page']))


class ServiceEventsView(ItemListView):
    @extend_schema(responses=ItemPageSerializer)
    def get(self, request, item_id):
        get_object_or_404(svc.public_items('service'), pk=item_id)
        options = query_input(request)
        values = []
        for item in svc.public_items('event').select_related('published_revision'):
            if item.published_revision.payload.get('service_id') != item_id:
                continue
            data = item_data(item, request.user, user_zone=options['time_zone'])
            data['occurrences'] = [row for row in data['occurrences'] if row['ends_at'] > timezone.now() and not row['cancelled']]
            if data['occurrences']:
                values.append(data)
        return Response(paged(values, options['page']))


class SearchView(InputView):
    permission_classes = [AllowAny]
    serializer_class = ItemPageSerializer

    @extend_schema(parameters=[QuerySerializer], responses=ItemPageSerializer)
    def get(self, request):
        options = query_input(request)
        return Response(paged(catalog_values(request, options), options['page']))


class ReminderView(InputView):
    from .serializers import ReminderSerializer
    serializer_class = ReminderSerializer

    @extend_schema(responses=MessageSerializer)
    def put(self, request, occurrence_id):
        from .models import Reminder
        row = get_object_or_404(Occurrence, pk=occurrence_id, event__in=svc.public_items('event'))
        if svc.archived(row) or row.cancelled_at or row.starts_at <= timezone.now():
            raise ValidationError('Reminders require an upcoming occurrence.')
        data = self.input(request)
        if row.starts_at-timedelta(minutes=data['offset_minutes']) < timezone.now():
            raise ValidationError('Choose a reminder time that has not already passed.')
        Reminder.objects.update_or_create(user=request.user, occurrence=row,
            defaults={**data, 'sent_for_start': None})
        return Response({'detail': 'Reminder saved. / تم حفظ التذكير.'})

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, occurrence_id):
        from .models import Reminder
        Reminder.objects.filter(user=request.user, occurrence_id=occurrence_id).delete()
        return Response(status=204)


class CalendarView(InputView):
    permission_classes = [AllowAny]
    serializer_class = MessageSerializer

    @extend_schema(responses={(200, 'text/calendar'): str})
    def get(self, request, occurrence_id):
        from django.http import HttpResponse
        row = get_object_or_404(Occurrence.objects.select_related('event__published_revision', 'revision'), pk=occurrence_id, event__in=svc.public_items('event'))
        payload = (row.revision or row.event.published_revision).payload
        def escape(value):
            return value.replace('\\', '\\\\').replace('\r', '').replace('\n', '\\n').replace(',', '\\,').replace(';', '\\;')
        # UTC calendar times work across zones; phone insertion is a client action.
        lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Munassiq//Events//EN', 'BEGIN:VEVENT',
            f'UID:occurrence-{row.pk}@munassiq', 'DTSTAMP:'+timezone.now().strftime('%Y%m%dT%H%M%SZ'),
            'DTSTART:'+row.starts_at.strftime('%Y%m%dT%H%M%SZ'), 'DTEND:'+row.ends_at.strftime('%Y%m%dT%H%M%SZ'),
            'SUMMARY:'+escape(payload['title']), 'LOCATION:'+escape(payload.get('address', '')),
            'STATUS:' + ('CANCELLED' if row.cancelled_at else 'CONFIRMED'), 'END:VEVENT', 'END:VCALENDAR', '']
        # Fold by UTF-8 bytes, never split a Unicode character.
        folded = []
        for line in lines:
            part = ''
            for char in line:
                if len((part+char).encode()) > 73:
                    folded.append(part)
                    part = ' '+char
                else:
                    part += char
            folded.append(part)
        response = HttpResponse('\r\n'.join(folded), content_type='text/calendar; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="event.ics"'
        return response


class OrganizerProfileView(InputView):
    permission_classes = [AllowAny]
    from .serializers import OrganizerSerializer
    serializer_class = OrganizerSerializer

    def get(self, request, organizer_id):
        from accounts.models import User
        from .models import OrganizerProfile
        user = get_object_or_404(User, pk=organizer_id)
        profile = OrganizerProfile.objects.filter(user=user).first()
        if not user.role_grants.filter(role='organizer').exists() and not svc.public_items().filter(owner=user).exists():
            raise ValidationError('No public organizer profile exists.')
        return Response({'id': user.pk, 'name': user.name, 'bio': profile.bio if profile else '',
            'photo_id': profile.photo_id if profile else None, 'verified': user.has_role('organizer')})


class EditOrganizerProfileView(InputView):
    from .serializers import OrganizerProfileInputSerializer
    serializer_class = OrganizerProfileInputSerializer

    def patch(self, request):
        from .models import OrganizerProfile
        svc.require_creator(request.user)
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data.get('photo_id'):
            get_object_or_404(Asset, pk=data['photo_id'], owner=request.user, kind='image')
        with transaction.atomic():
            profile, _ = OrganizerProfile.objects.get_or_create(user=request.user)
            for key, value in data.items():
                setattr(profile, key, value)
            profile.save()
            if svc.is_reviewer(request.user):
                audit(request.user, 'organizer.profile_edit', profile)
        return Response({'bio': profile.bio, 'photo_id': profile.photo_id})


class OrganizerEventsView(ItemListView):
    @extend_schema(responses=ItemPageSerializer)
    def get(self, request, organizer_id):
        options = query_input(request)
        values = []
        for item in svc.public_items('event').filter(owner_id=organizer_id).select_related('published_revision'):
            data = item_data(item, request.user, include_archive=options['archive'], archived_only=options['archived_only'], user_zone=options['time_zone'])
            if data['occurrences']:
                values.append(data)
        return Response(paged(values, options['page']))


class CityAdminDetailView(InputView):
    permission_classes = [Administrator]
    serializer_class = CitySerializer

    def get(self, request, city_id):
        record = get_object_or_404(City, pk=city_id)
        audit(request.user, 'city.read', record)
        return Response(self.get_serializer(record).data)

    def patch(self, request, city_id):
        with transaction.atomic():
            record = get_object_or_404(City.objects.select_for_update(), pk=city_id)
            serializer = self.get_serializer(record, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            audit(request.user, 'city.edit', record)
        return Response(serializer.data)
