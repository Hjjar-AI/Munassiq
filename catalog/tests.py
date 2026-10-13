"""Content/permission integration tests and real database registration races."""
import io
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as utc
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.conf import settings
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from PIL import Image
from pypdf import PdfReader, PdfWriter
from rest_framework.test import APIClient
from accounts.maintenance import delete_user
from accounts.models import AuditEntry, RoleGrant, User
from accounts.services import issue_session
from . import registration as reg, services as svc
from .maintenance import run_jobs
from .models import (Asset, Category, City, Country, Currency, EventViewTotal, Item, Notice,
    Occurrence, Registration, RegistrationTransition, Reminder, Report)
from .search import normalize


class FixtureMixin:
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user('owner@example.org', 'secret123', name='Organizer', verified_at=timezone.now())
        self.mod = User.objects.create_user('moderator@example.org', 'secret123', name='Moderator', verified_at=timezone.now())
        self.admin = User.objects.create_user('admin@example.org', 'secret123', name='Admin', verified_at=timezone.now())
        self.user = User.objects.create_user('user@example.org', 'secret123', name='محمد أحمد', verified_at=timezone.now())
        self.other = User.objects.create_user('other@example.org', 'secret123', name='Other', verified_at=timezone.now())
        RoleGrant.objects.create(user=self.owner, role='organizer')
        RoleGrant.objects.create(user=self.mod, role='moderator')
        RoleGrant.objects.create(user=self.admin, role='admin')
        self.country = Country.objects.create(code='SY', name_ar='سوريا', name_en='Syria')
        self.city = City.objects.create(country=self.country, name_ar='دمشق', name_en='Damascus')
        self.category = Category.objects.create(name_ar='طب نفسي', name_en='Psychiatry')
        self.currency = Currency.objects.create(code='USD', name_ar='دولار', name_en='US dollar')
        self.media = TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=Path(self.media.name), EXPORT_FONT_PATH='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.media.cleanup)

    def signin(self, user=None):
        result = issue_session(user or self.owner)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+result['access_token'])

    def post(self, path, data=None):
        return self.client.post('/api/v1/'+path+'/', data or {}, format='json')

    def common(self):
        return {'description': 'Professional directory information', 'country_id': self.country.pk,
            'city_id': self.city.pk, 'category_ids': [self.category.pk], 'time_zone': 'Asia/Damascus',
            'phone': '+442083661177', 'contact_person': 'Office contact', 'contact_scope': 'personal'}

    def event_payload(self, **extra):
        data = {**self.common(), 'title': 'محاضرة الطب النفسي', 'speaker_name': 'Speaker', 'topic': 'Psychiatry',
            'mode': 'online', 'online_url': 'https://example.org/meeting',
            'starts_at': (timezone.now()+timedelta(days=3)).isoformat(), 'duration_minutes': 60, 'seat_limit': 1,
            'cancellation_cutoff_minutes': 60, 'recurrence': 'none', 'occurrence_count': 1}
        data.update(extra)
        return data

    def service_payload(self, **extra):
        data = {**self.common(), 'name': 'مركز أمل', 'type': 'center', 'address': 'Example address',
            'latitude': 33.5, 'longitude': 36.3, 'hours': [{'day': 0, 'start': '22:00', 'end': '02:00'}],
            'price': '10.00', 'currency_id': self.currency.pk}
        data.update(extra)
        return data

    def approved(self, kind='event', **extra):
        payload = self.event_payload(**extra) if kind == 'event' else self.service_payload(**extra)
        item = svc.create_item(self.owner, kind, payload)
        svc.claim_review(self.mod, item.pk)
        return svc.decide(self.mod, item.pk, True, '')

    def upload_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        image = io.BytesIO()
        Image.new('RGB', (30, 30), 'blue').save(image, 'PNG')
        return SimpleUploadedFile('photo.png', image.getvalue(), content_type='image/png')


class CatalogueTests(FixtureMixin, TestCase):
    def test_only_organizers_create_even_admin_and_moderator(self):
        for user in [self.user, self.mod, self.admin]:
            self.signin(user)
            self.assertEqual(self.post('events', self.event_payload()).status_code, 403)
            self.assertEqual(self.post('services', self.service_payload()).status_code, 403)
        self.signin()
        response = self.post('events', self.event_payload())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'pending')
        self.client.credentials()
        self.assertEqual(self.client.get('/api/v1/events/').data['results'], [])

    def test_guest_contacts_are_redacted_and_search_cannot_match_phone(self):
        item = self.approved('service')
        response = self.client.get(f'/api/v1/services/{item.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('phone', response.data['payload'])
        self.assertNotIn('contact_person', response.data['payload'])
        self.assertEqual(self.client.get('/api/v1/services/?q=442083661177').data['results'], [])
        self.signin(self.user)
        self.assertEqual(self.client.get(f'/api/v1/services/{item.pk}/').data['payload']['phone'], '+442083661177')

    def test_arabic_normalization_and_duplicate_warning(self):
        self.approved('service', name='مَرْكَز أَمَل')
        self.signin()
        self.assertEqual(self.post('services/duplicate-check', {'name': 'مركز امل'}).data, {'similar_name_exists': True})
        response = self.post('services', self.service_payload(name='مركز امل'))
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['duplicate_flag'])
        self.client.credentials()
        self.assertEqual(len(self.client.get('/api/v1/services/?q=مركز امل').data['results']), 1)
        self.assertEqual(normalize('إِضَاءَة'), normalize('اضاءه'))

    def test_pending_change_keeps_published_version_live_and_rejection_can_resubmit(self):
        item = self.approved('service')
        self.signin()
        data = self.service_payload(name='New title')
        response = self.client.patch(f'/api/v1/services/{item.pk}/', data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'pending_changes')
        self.client.credentials()
        self.assertEqual(self.client.get(f'/api/v1/services/{item.pk}/').data['payload']['name'], 'مركز أمل')
        svc.claim_review(self.mod, item.pk)
        svc.decide(self.mod, item.pk, False, 'Correct address')
        self.signin()
        self.assertEqual(self.client.patch(f'/api/v1/services/{item.pk}/', data, format='json').status_code, 200)
        svc.claim_review(self.mod, item.pk)
        svc.decide(self.mod, item.pk, True, '')
        self.client.credentials()
        self.assertEqual(self.client.get(f'/api/v1/services/{item.pk}/').data['payload']['name'], 'New title')

    def test_review_locks_queue_decisions_and_admin_unlock_are_enforced(self):
        item = svc.create_item(self.owner, 'event', self.event_payload())
        self.signin(self.mod)
        self.assertEqual(self.client.get('/api/v1/moderation/items/').status_code, 200)
        self.assertEqual(self.post(f'moderation/items/{item.pk}/decision', {'approved': True}).status_code, 403)
        self.assertEqual(self.post(f'moderation/items/{item.pk}/claim').status_code, 200)
        self.signin(self.admin)
        self.assertEqual(self.post(f'moderation/items/{item.pk}/claim').status_code, 400)
        self.assertEqual(self.post(f'admin/items/{item.pk}/unlock').status_code, 200)
        self.assertEqual(self.post(f'moderation/items/{item.pk}/claim').status_code, 200)
        self.assertEqual(self.post(f'moderation/items/{item.pk}/decision', {'approved': True}).status_code, 200)
        self.assertTrue(AuditEntry.objects.filter(action='item.approve').exists())

    def test_organizer_cannot_delete_and_moderator_edit_is_audited(self):
        item = self.approved('service')
        self.signin()
        self.assertEqual(self.client.delete(f'/api/v1/services/{item.pk}/').status_code, 405)
        self.signin(self.mod)
        self.assertEqual(self.client.get(f'/api/v1/moderation/items/{item.pk}/').status_code, 200)
        response = self.client.patch(f'/api/v1/moderation/items/{item.pk}/', self.service_payload(name='Moderated'), format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AuditEntry.objects.filter(action='item.edit', target_id=str(item.pk)).exists())

    def test_hide_unhide_delete_restore_keep_registrations_cancelled(self):
        item = self.approved()
        occurrence = item.occurrences.get()
        record, _ = reg.register(self.user, occurrence.pk)
        self.signin(self.mod)
        self.assertEqual(self.post(f'moderation/items/{item.pk}/hide').status_code, 200)
        self.client.credentials()
        self.assertEqual(self.client.get('/api/v1/events/').data['results'], [])
        self.signin(self.mod)
        self.assertEqual(self.post(f'moderation/items/{item.pk}/unhide').status_code, 200)
        self.assertEqual(self.client.delete(f'/api/v1/moderation/items/{item.pk}/').status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.state, 'cancelled')
        self.assertEqual(self.post(f'moderation/items/{item.pk}/restore').status_code, 200)
        record.refresh_from_db()
        occurrence.refresh_from_db()
        self.assertEqual(record.state, 'cancelled')
        self.assertIsNone(occurrence.cancelled_at)

    def test_reports_never_auto_hide_and_reporter_gets_no_decision_notice(self):
        item = self.approved('service')
        self.signin(self.user)
        response = self.post('reports', {'item_id': item.pk, 'reason': 'other', 'text': 'Check address'})
        self.assertEqual(response.status_code, 201)
        item.refresh_from_db()
        self.assertEqual(item.status, 'approved')
        self.assertEqual(self.post('feedback', {'text': 'Helpful app'}).status_code, 201)
        report = Report.objects.get()
        self.signin(self.mod)
        self.assertEqual(self.client.get('/api/v1/moderation/reports/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/moderation/feedback/').status_code, 200)
        self.assertEqual(self.post(f'moderation/reports/{report.pk}/resolve', {'action': 'warn', 'reason': 'Verify address'}).status_code, 200)
        self.assertFalse(Notice.objects.filter(user=self.user).exists())
        self.assertTrue(Notice.objects.filter(user=self.owner, kind='organizer.warning').exists())

    def test_reference_lists_public_but_mutation_requires_correct_role(self):
        for path in ['countries', 'cities', 'currencies', 'categories']:
            self.assertEqual(self.client.get('/api/v1/'+path+'/').status_code, 200)
        self.signin(self.user)
        self.assertEqual(self.post('categories', {'name_ar': 'جديد', 'name_en': 'New'}).status_code, 403)
        self.signin(self.mod)
        self.assertEqual(self.post('categories', {'name_ar': 'جديد', 'name_en': 'New'}).status_code, 201)
        self.assertEqual(self.client.patch(f'/api/v1/categories/{self.category.pk}/', {'name_en': 'Updated'}, format='json').status_code, 200)
        self.assertEqual(self.client.get(f'/api/v1/categories/{self.category.pk}/').status_code, 200)
        self.assertEqual(self.post('countries', {'code': 'GB', 'name_ar': 'بريطانيا', 'name_en': 'UK'}).status_code, 403)
        self.signin(self.admin)
        response = self.post('countries', {'code': 'GB', 'name_ar': 'بريطانيا', 'name_en': 'UK'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.post('cities', {'country': response.data['id'], 'name_ar': 'لندن', 'name_en': 'London'}).status_code, 201)
        self.assertEqual(self.post('currencies', {'code': 'GBP', 'name_ar': 'جنيه', 'name_en': 'Pound'}).status_code, 201)

    def test_invalid_phone_timezone_datetime_and_hours_are_rejected(self):
        self.signin()
        for change in [{'phone': '+123456789'}, {'time_zone': 'Bad/Zone'}, {'starts_at': '2026-02-31T12:00:00Z'}, {'starts_at': '2026-12-01T12:00:00'}]:
            self.assertEqual(self.post('events', self.event_payload(**change)).status_code, 400)
        self.assertEqual(self.post('services', self.service_payload(hours=[{'day': 0, 'start': '10:00', 'end': '14:00'}, {'day': 0, 'start': '12:00', 'end': '16:00'}])).status_code, 400)

    def test_open_now_uses_local_zone_and_previous_day_overnight_hours(self):
        payload = self.service_payload(time_zone='UTC')
        self.assertTrue(svc.is_open(payload, datetime(2026, 10, 13, 1, 0, tzinfo=utc.utc)))
        self.assertFalse(svc.is_open(payload, datetime(2026, 10, 13, 3, 0, tzinfo=utc.utc)))

    def test_service_filter_price_sort_requires_currency_and_map_is_public(self):
        self.approved('service')
        self.approved('service', name='Another', price='5.00')
        self.assertEqual(self.client.get('/api/v1/services/?sort=price').status_code, 400)
        response = self.client.get(f'/api/v1/services/?sort=price&currency={self.currency.pk}')
        self.assertEqual(response.data['results'][0]['payload']['name'], 'Another')
        self.assertEqual(len(self.client.get('/api/v1/map/services/').data['results']), 2)
        self.assertEqual(self.client.get('/api/v1/search/?q=مركز').status_code, 200)

    def test_venue_snapshot_and_upcoming_service_events(self):
        service = self.approved('service')
        event = self.approved(service_id=service.pk)
        self.assertEqual(event.published_revision.payload['venue_snapshot']['name'], 'مركز أمل')
        self.assertEqual(len(self.client.get(f'/api/v1/services/{service.pk}/events/').data['results']), 1)
        svc.change_visibility(self.mod, service.pk, 'delete')
        self.assertEqual(self.client.get(f'/api/v1/events/{event.pk}/').data['payload']['venue_snapshot']['address'], 'Example address')

    def test_archive_filter_and_past_creation_permissions(self):
        self.signin()
        past = self.event_payload(starts_at=(timezone.now()-timedelta(days=3)).isoformat())
        self.assertEqual(self.post('events', past).status_code, 400)
        RoleGrant.objects.create(user=self.mod, role='organizer')
        item = svc.create_item(self.mod, 'event', past)
        svc.claim_review(self.mod, item.pk)
        svc.decide(self.mod, item.pk, True, '')
        self.client.credentials()
        self.assertEqual(self.client.get('/api/v1/events/').data['results'], [])
        self.assertEqual(len(self.client.get('/api/v1/events/?archive=true').data['results']), 1)
        self.assertEqual(self.client.get(f'/api/v1/occurrences/{item.occurrences.get().pk}/').status_code, 200)
        self.signin(self.user)
        self.assertEqual(self.post(f'occurrences/{item.occurrences.get().pk}/registration').status_code, 400)

    def test_monthly_recurrence_skips_missing_day_and_weekly_range_is_present(self):
        payload = self.event_payload(starts_at='2027-01-31T12:00:00Z', time_zone='UTC', recurrence='monthly', occurrence_count=3)
        dates = svc.schedule(payload)
        self.assertEqual([row.month for row in dates], [1, 3, 5])
        item = self.approved(recurrence='weekly', occurrence_count=3)
        response = self.client.get(f'/api/v1/events/{item.pk}/')
        self.assertEqual(len(response.data['occurrences']), 3)
        self.assertGreater(response.data['date_range']['end'], response.data['date_range']['start'])

    def test_duplicate_requires_new_date_and_my_items_shows_status(self):
        item = self.approved()
        self.signin()
        response = self.post(f'events/{item.pk}/duplicate', {'starts_at': (timezone.now()+timedelta(days=7)).isoformat(), 'title': 'Duplicate'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(len(self.client.get('/api/v1/me/items/').data['results']), 2)

    def test_image_and_pdf_validation_attachment_privacy_and_limits(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.signin()
        response = self.client.post('/api/v1/uploads/images/', {'file': self.upload_image()}, format='multipart')
        self.assertEqual(response.status_code, 201)
        asset_id = response.data['id']
        self.assertLessEqual(response.data['size'], 1024*1024)
        self.client.credentials()
        self.assertEqual(self.client.get(f'/api/v1/files/{asset_id}/').status_code, 403)
        self.signin()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        stream = io.BytesIO()
        writer.write(stream)
        pdf = self.client.post('/api/v1/uploads/event-pdfs/', {'file': SimpleUploadedFile('event.pdf', stream.getvalue(), content_type='application/pdf')}, format='multipart')
        self.assertEqual(pdf.status_code, 201)
        item = self.approved(image_ids=[asset_id], pdf_id=pdf.data['id'])
        self.client.credentials()
        download = self.client.get(f'/api/v1/files/{asset_id}/')
        self.assertEqual(download.status_code, 200)
        list(download.streaming_content)
        download = self.client.get(f'/api/v1/files/{pdf.data["id"]}/')
        self.assertEqual(download.status_code, 200)
        self.assertIn('attachment', download['Content-Disposition'])
        list(download.streaming_content)
        self.signin()
        self.assertEqual(self.post('events', self.event_payload(image_ids=[asset_id]*4)).status_code, 400)

    def test_view_count_is_daily_deduplicated_and_staff_are_excluded(self):
        item = self.approved()
        self.assertTrue(self.post(f'events/{item.pk}/views').data['counted'])
        self.assertFalse(self.post(f'events/{item.pk}/views').data['counted'])
        self.signin(self.mod)
        self.assertFalse(self.post(f'events/{item.pk}/views').data['counted'])
        self.assertEqual(EventViewTotal.objects.get(event=item).count, 1)

    def test_profile_and_calendar_reminders_survive_reschedule_by_offset(self):
        item = self.approved()
        occurrence = item.occurrences.get()
        self.signin()
        self.assertEqual(self.client.patch('/api/v1/me/organizer-profile/', {'bio': 'Professional bio'}, format='json').status_code, 200)
        self.client.credentials()
        self.assertTrue(self.client.get(f'/api/v1/organizers/{self.owner.pk}/').data['verified'])
        self.assertEqual(self.client.get(f'/api/v1/organizers/{self.owner.pk}/events/').status_code, 200)
        calendar = self.client.get(f'/api/v1/occurrences/{occurrence.pk}/calendar.ics')
        self.assertEqual(calendar.status_code, 200)
        self.assertIn(b'BEGIN:VCALENDAR', calendar.content)
        self.signin(self.user)
        self.assertEqual(self.client.put(f'/api/v1/occurrences/{occurrence.pk}/reminder/', {'offset_minutes': 60}, format='json').status_code, 200)
        reg.reschedule(self.owner, occurrence.pk, timezone.now()+timedelta(days=5), 60, 'UTC')
        self.assertEqual(Reminder.objects.get().offset_minutes, 60)
        self.assertEqual(self.client.delete(f'/api/v1/occurrences/{occurrence.pk}/reminder/').status_code, 204)

    def test_account_deletion_keeps_published_items_and_removes_personal_attribution(self):
        item = self.approved('service')
        with self.captureOnCommitCallbacks(execute=True):
            delete_user(self.owner)
        item.refresh_from_db()
        self.assertIsNone(item.owner_id)
        self.assertEqual(item.status, 'approved')
        item.published_revision.refresh_from_db()
        self.assertEqual(item.published_revision.payload['phone'], '')
        self.assertIsNone(item.published_revision.author_id)

    def test_jobs_hard_delete_after_three_days_and_are_idempotent(self):
        item = self.approved()
        occurrence = item.occurrences.get()
        record, _ = reg.register(self.user, occurrence.pk)
        svc.change_visibility(self.mod, item.pk, 'delete')
        Item.objects.filter(pk=item.pk).update(deleted_at=timezone.now()-timedelta(days=3, seconds=1))
        with self.captureOnCommitCallbacks(execute=True):
            run_jobs()
            run_jobs()
        self.assertFalse(Item.objects.filter(pk=item.pk).exists())
        self.assertTrue(AuditEntry.objects.filter(action='item.hard_delete', target_id=str(item.pk)).exists())
        self.assertTrue(RegistrationTransition.objects.filter(new_state='cancelled', registration=None).exists())


class RegistrationTests(FixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = self.approved()
        self.occurrence = self.item.occurrences.get()

    def test_last_seat_waitlist_then_cancel_promotes_once(self):
        first, _ = reg.register(self.user, self.occurrence.pk)
        second, _ = reg.register(self.other, self.occurrence.pk)
        self.assertEqual(first.state, 'registered')
        self.assertEqual(second.state, 'waitlisted')
        self.signin(self.user)
        self.assertEqual(self.post(f'registrations/{first.pk}/cancel').status_code, 200)
        second.refresh_from_db()
        self.assertEqual(second.state, 'registered')
        self.post(f'registrations/{first.pk}/cancel')
        self.assertEqual(RegistrationTransition.objects.filter(registration=second, reason='waitlist.promotion').count(), 1)

    def test_registration_endpoint_verification_uniqueness_and_my_registrations(self):
        self.user.verified_at = None
        self.user.save()
        self.signin(self.user)
        self.assertEqual(self.post(f'occurrences/{self.occurrence.pk}/registration').status_code, 403)
        self.user.verified_at = timezone.now()
        self.user.save()
        self.assertEqual(self.post(f'occurrences/{self.occurrence.pk}/registration').status_code, 201)
        self.assertEqual(self.post(f'occurrences/{self.occurrence.pk}/registration').status_code, 201)
        self.assertEqual(Registration.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.client.get('/api/v1/me/registrations/').status_code, 200)

    def test_normal_reschedule_holds_seat_until_reconfirm_and_waitlist_stays(self):
        first, _ = reg.register(self.user, self.occurrence.pk)
        second, _ = reg.register(self.other, self.occurrence.pk)
        self.signin()
        self.assertEqual(self.post(f'occurrences/{self.occurrence.pk}/reschedule', {'starts_at': (timezone.now()+timedelta(days=5)).isoformat(), 'duration_minutes': 60, 'time_zone': 'UTC'}).status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.state, 'pending_reconfirm')
        self.assertEqual(second.state, 'waitlisted')
        self.assertEqual(reg.occupied(self.occurrence), 1)
        self.signin(self.user)
        self.assertEqual(self.post(f'registrations/{first.pk}/reconfirm').status_code, 200)
        first.refresh_from_db()
        self.assertEqual(first.state, 'registered')

    def test_short_notice_reschedule_keeps_confirmed_seat_and_optional_reconfirm(self):
        first, _ = reg.register(self.user, self.occurrence.pk)
        self.signin()
        response = self.post(f'occurrences/{self.occurrence.pk}/reschedule', {'starts_at': (timezone.now()+timedelta(hours=2)).isoformat(), 'duration_minutes': 60, 'time_zone': 'UTC'})
        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        self.assertEqual(first.state, 'registered')
        self.assertIsNone(first.reconfirm_deadline)
        self.signin(self.user)
        self.assertEqual(self.post(f'registrations/{first.pk}/reconfirm').status_code, 200)

    def test_reconfirm_timeout_releases_seat_and_job_promotes_waitlist(self):
        first, _ = reg.register(self.user, self.occurrence.pk)
        second, _ = reg.register(self.other, self.occurrence.pk)
        reg.reschedule(self.owner, self.occurrence.pk, timezone.now()+timedelta(days=4), 60, 'UTC')
        Registration.objects.filter(pk=first.pk).update(reconfirm_deadline=timezone.now()-timedelta(seconds=1))
        run_jobs()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.state, 'cancelled')
        self.assertEqual(second.state, 'registered')
        before = RegistrationTransition.objects.count()
        run_jobs()
        self.assertEqual(RegistrationTransition.objects.count(), before)

    def test_banned_waitlisted_user_is_skipped_without_losing_position(self):
        first, _ = reg.register(self.user, self.occurrence.pk)
        banned, _ = reg.register(self.other, self.occurrence.pk)
        third = User.objects.create_user('third@example.org', 'secret123', name='Third', verified_at=timezone.now())
        next_user, _ = reg.register(third, self.occurrence.pk)
        original = banned.queued_at
        self.other.is_active = False
        self.other.save()
        reg.cancel(self.user, first.pk)
        banned.refresh_from_db()
        next_user.refresh_from_db()
        self.assertEqual(banned.state, 'waitlisted')
        self.assertEqual(banned.queued_at, original)
        self.assertEqual(next_user.state, 'registered')

    def test_cancellation_cutoff_and_capacity_floor_are_enforced(self):
        record, _ = reg.register(self.user, self.occurrence.pk)
        Occurrence.objects.filter(pk=self.occurrence.pk).update(cancellation_cutoff_minutes=10000)
        self.signin(self.user)
        self.assertEqual(self.post(f'registrations/{record.pk}/cancel').status_code, 400)
        self.signin()
        self.assertEqual(self.post(f'organizer/registrations/{record.pk}/remove', {'reason': 'Duplicate request'}).status_code, 200)
        self.assertEqual(reg.occupied(self.occurrence), 0)

    def test_pending_reconfirm_counts_against_capacity_and_overlap_only_warns(self):
        reg.register(self.user, self.occurrence.pk)
        other_event = self.approved(starts_at=self.occurrence.starts_at.isoformat(), seat_limit=3)
        second, warning = reg.register(self.user, other_event.occurrences.get().pk)
        self.assertTrue(warning)
        self.assertEqual(second.state, 'registered')
        reg.reschedule(self.owner, self.occurrence.pk, timezone.now()+timedelta(days=5), 60, 'UTC')
        self.assertEqual(reg.occupied(self.occurrence), 1)

    def test_cancelled_rejoin_retains_one_row_and_new_queue_position(self):
        first, _ = reg.register(self.user, self.occurrence.pk)
        reg.cancel(self.user, first.pk)
        other, _ = reg.register(self.other, self.occurrence.pk)
        again, _ = reg.register(self.user, self.occurrence.pk)
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(again.state, 'waitlisted')
        self.assertEqual(Registration.objects.filter(user=self.user).count(), 1)

    def test_event_cancel_ends_all_states_and_unauthorized_cancel_is_denied(self):
        first, _ = reg.register(self.user, self.occurrence.pk)
        second, _ = reg.register(self.other, self.occurrence.pk)
        self.signin(self.user)
        self.assertEqual(self.post(f'occurrences/{self.occurrence.pk}/cancel').status_code, 403)
        self.signin()
        self.assertEqual(self.post(f'occurrences/{self.occurrence.pk}/cancel').status_code, 200)
        self.assertFalse(Registration.objects.filter(occurrence=self.occurrence, state__in=reg.ACTIVE).exists())
        self.assertEqual(Notice.objects.filter(kind='event.cancelled').count(), 2)

    def test_series_signup_includes_current_occurrences_and_mixed_seat_outcomes(self):
        item = self.approved(recurrence='weekly', occurrence_count=3)
        reg.register(self.other, item.occurrences.order_by('starts_at').first().pk)
        self.signin(self.user)
        response = self.post(f'series/{item.pk}/registrations')
        self.assertEqual(response.status_code, 201)
        self.assertEqual([row['state'] for row in response.data], ['waitlisted', 'registered', 'registered'])

    def test_account_deletion_releases_seat_and_promotes_next_user(self):
        first, _ = reg.register(self.user, self.occurrence.pk)
        second, _ = reg.register(self.other, self.occurrence.pk)
        delete_user(self.user)
        second.refresh_from_db()
        self.assertEqual(second.state, 'registered')
        self.assertFalse(Registration.objects.filter(pk=first.pk).exists())

    def test_stats_exports_and_steward_permissions(self):
        reg.register(self.user, self.occurrence.pk)
        self.signin(self.mod)
        path = f'/api/v1/organizer/occurrences/{self.occurrence.pk}'
        self.assertEqual(self.client.get(path+'/stats/').status_code, 403)
        self.assertEqual(self.client.get(path+'/registrants/').status_code, 403)
        self.signin()
        self.assertEqual(self.client.get(path+'/stats/').data['registered'], 1)
        self.assertEqual(self.client.get(path+'/registrants/').status_code, 200)
        csv = self.client.get(path+'/registrants/export/?format=csv')
        self.assertEqual(csv.status_code, 200)
        self.assertIn(self.user.email, csv.content.decode('utf-8-sig'))
        pdf = self.client.get(path+'/registrants/export/?format=pdf')
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        self.assertIn(self.user.email, PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text())
        RoleGrant.objects.filter(user=self.owner, role='organizer').delete()
        self.signin(self.mod)
        self.assertEqual(self.client.get(path+'/registrants/').status_code, 200)
        self.assertEqual(self.client.get(path+'/stats/').status_code, 403)

    def test_registration_deadline_closes_signup_and_promotion(self):
        Occurrence.objects.filter(pk=self.occurrence.pk).update(registration_deadline=timezone.now()-timedelta(seconds=1))
        self.signin(self.user)
        self.assertEqual(self.post(f'occurrences/{self.occurrence.pk}/registration').status_code, 400)


class RegistrationRaceTests(FixtureMixin, TransactionTestCase):
    def test_two_users_take_last_seat_without_overbooking(self):
        item = self.approved()
        occurrence_id = item.occurrences.get().pk
        barrier = threading.Barrier(2)
        def take_seat(user_id):
            close_old_connections()
            try:
                user = User.objects.get(pk=user_id)
                barrier.wait(timeout=10)
                return reg.register(user, occurrence_id)[0].state
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(take_seat, [self.user.pk, self.other.pk]))
        self.assertCountEqual(results, ['registered', 'waitlisted'])
        self.assertEqual(Registration.objects.filter(occurrence_id=occurrence_id, state='registered').count(), 1)

    def test_competing_promotions_allocate_released_seat_once(self):
        item = self.approved()
        occurrence_id = item.occurrences.get().pk
        seated, _ = reg.register(self.user, occurrence_id)
        waiting, _ = reg.register(self.other, occurrence_id)
        third = User.objects.create_user('third@example.org', 'secret123', name='Third', verified_at=timezone.now())
        later, _ = reg.register(third, occurrence_id)
        User.objects.filter(pk__in=[self.other.pk, third.pk]).update(is_active=False)
        reg.cancel(self.user, seated.pk)
        User.objects.filter(pk__in=[self.other.pk, third.pk]).update(is_active=True)
        barrier = threading.Barrier(2)
        def promotion(_):
            from django.db import transaction
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                with transaction.atomic():
                    row = reg.locked_occurrence(occurrence_id)
                    reg.promote(row)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(promotion, [1, 2]))
        waiting.refresh_from_db()
        later.refresh_from_db()
        self.assertEqual(waiting.state, 'registered')
        self.assertEqual(later.state, 'waitlisted')
        self.assertEqual(RegistrationTransition.objects.filter(reason='waitlist.promotion').count(), 1)

    def test_signup_racing_with_cancellation_ends_with_one_seated_user(self):
        item = self.approved()
        occurrence_id = item.occurrences.get().pk
        seated, _ = reg.register(self.user, occurrence_id)
        barrier = threading.Barrier(2)
        def action(cancel):
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.user.pk if cancel else self.other.pk)
                barrier.wait(timeout=10)
                if cancel:
                    reg.cancel(actor, seated.pk)
                else:
                    reg.register(actor, occurrence_id)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(action, [True, False]))
        seated.refresh_from_db()
        self.assertEqual(seated.state, 'cancelled')
        self.assertEqual(Registration.objects.get(user=self.other, occurrence_id=occurrence_id).state, 'registered')
        self.assertEqual(Registration.objects.filter(occurrence_id=occurrence_id, state='registered').count(), 1)


class AdditionalLifecycleTests(FixtureMixin, TestCase):
    def test_archived_snapshot_stays_read_only_for_owner_and_staff_correction_is_audited(self):
        RoleGrant.objects.create(user=self.mod, role='organizer')
        payload = self.event_payload(starts_at=(timezone.now()-timedelta(days=3)).isoformat())
        item = svc.create_item(self.mod, 'event', payload)
        svc.claim_review(self.mod, item.pk)
        item = svc.decide(self.mod, item.pk, True, '')
        owner_data = dict(item.published_revision.payload)
        owner_data['title'] = 'Corrected title'
        # Staff corrections go through their explicit moderator endpoint.
        self.signin(self.mod)
        self.assertEqual(self.client.patch(f'/api/v1/events/{item.pk}/', owner_data, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/v1/moderation/items/{item.pk}/', owner_data, format='json').status_code, 200)
        occurrence = item.occurrences.get()
        self.assertEqual(occurrence.revision.payload['title'], 'Corrected title')
        self.assertTrue(AuditEntry.objects.filter(action='item.edit', target_id=str(item.pk)).exists())

    def test_rejoin_free_seat_is_cancelled_to_registered_and_waitlist_user_can_cancel(self):
        item = self.approved()
        occurrence = item.occurrences.get()
        first, _ = reg.register(self.user, occurrence.pk)
        reg.cancel(self.user, first.pk)
        again, _ = reg.register(self.user, occurrence.pk)
        self.assertEqual(again.state, 'registered')
        waiting, _ = reg.register(self.other, occurrence.pk)
        cancelled = reg.cancel(self.other, waiting.pk)
        self.assertEqual(cancelled.state, 'cancelled')
        self.assertTrue(RegistrationTransition.objects.filter(old_state='cancelled', new_state='registered').exists())
        self.assertTrue(RegistrationTransition.objects.filter(old_state='waitlisted', new_state='cancelled').exists())

    def test_minimum_reconfirm_window_and_pending_cancellation_after_old_cutoff(self):
        item = self.approved(cancellation_cutoff_minutes=10000)
        occurrence = item.occurrences.get()
        record, _ = reg.register(self.user, occurrence.pk)
        before = timezone.now()
        reg.reschedule(self.owner, occurrence.pk, before+timedelta(hours=24), 60, 'UTC')
        record.refresh_from_db()
        self.assertGreaterEqual(record.reconfirm_deadline, before+timedelta(hours=12))
        self.assertEqual(reg.cancel(self.user, record.pk).state, 'cancelled')

    def test_capacity_proposal_is_rechecked_when_approved(self):
        item = self.approved(seat_limit=2)
        occurrence = item.occurrences.get()
        proposal = dict(item.published_revision.payload)
        proposal['seat_limit'] = 1
        svc.edit_item(self.owner, item.pk, proposal)
        reg.register(self.user, occurrence.pk)
        reg.register(self.other, occurrence.pk)
        svc.claim_review(self.mod, item.pk)
        self.signin(self.mod)
        self.assertEqual(self.post(f'moderation/items/{item.pk}/decision', {'approved': True}).status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.published_revision.payload['seat_limit'], 2)
        self.assertEqual(item.status, 'pending_changes')

    def test_short_notice_after_pending_reconfirm_restores_seat_once(self):
        item = self.approved()
        record, _ = reg.register(self.user, item.occurrences.get().pk)
        reg.reschedule(self.owner, record.occurrence_id, timezone.now()+timedelta(days=5), 60, 'UTC')
        notices = Notice.objects.filter(user=self.user, kind='event.rescheduled').count()
        reg.reschedule(self.owner, record.occurrence_id, timezone.now()+timedelta(hours=3), 60, 'UTC')
        record.refresh_from_db()
        self.assertEqual(record.state, 'registered')
        self.assertEqual(Notice.objects.filter(user=self.user, kind='event.rescheduled').count(), notices+1)

    def test_csv_formula_protection_pdf_missing_font_and_view_stats_permissions(self):
        item = self.approved()
        occurrence = item.occurrences.get()
        self.user.name = '=1+1'
        self.user.save()
        reg.register(self.user, occurrence.pk)
        self.signin()
        path = f'/api/v1/organizer/occurrences/{occurrence.pk}/registrants/export/'
        self.assertIn("'=1+1", self.client.get(path+'?format=csv').content.decode('utf-8-sig'))
        with override_settings(EXPORT_FONT_PATH=''):
            self.assertEqual(self.client.get(path+'?format=pdf').status_code, 503)

    def test_account_deletion_preserves_organization_contact_and_removes_unpublished_items(self):
        published = self.approved('service', contact_scope='organization')
        unpublished = svc.create_item(self.owner, 'service', self.service_payload(name='Unpublished'))
        delete_user(self.owner)
        self.assertFalse(Item.objects.filter(pk=unpublished.pk).exists())
        published.refresh_from_db()
        self.assertEqual(published.published_revision.payload['phone'], '+442083661177')
        self.assertIsNone(published.owner_id)

    def test_calendar_escapes_user_text_and_archive_search_uses_occurrence_snapshot(self):
        item = self.approved(title='Title,semicolon;\nNew line')
        occurrence = item.occurrences.get()
        response = self.client.get(f'/api/v1/occurrences/{occurrence.pk}/calendar.ics')
        self.assertIn(b'Title\\,semicolon\\;\\nNew line', response.content)
        self.assertEqual(self.client.get('/api/v1/search/?q=Title').data['results'][0]['id'], item.pk)

    def test_reference_uniqueness_is_validated_and_city_filter_is_applied(self):
        self.signin(self.admin)
        self.assertEqual(self.post('countries', {'code': 'SY', 'name_ar': 'سوريا', 'name_en': 'Syria'}).status_code, 400)
        self.assertEqual(self.post('currencies', {'code': 'USD', 'name_ar': 'دولار', 'name_en': 'Dollar'}).status_code, 400)
        self.client.credentials()
        self.assertEqual(len(self.client.get(f'/api/v1/cities/?country={self.country.pk}').data), 1)

    def test_banned_actor_cannot_create_using_a_stale_user_object(self):
        User.objects.filter(pk=self.owner.pk).update(is_active=False)
        from rest_framework.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            svc.create_item(self.owner, 'event', self.event_payload())

    def test_hidden_deleted_restored_item_preserves_rejected_proposal_status(self):
        item = self.approved('service')
        proposal = dict(item.published_revision.payload)
        proposal['name'] = 'Rejected change'
        svc.edit_item(self.owner, item.pk, proposal)
        svc.claim_review(self.mod, item.pk)
        svc.decide(self.mod, item.pk, False, 'Not approved')
        svc.change_visibility(self.mod, item.pk, 'hide')
        svc.change_visibility(self.mod, item.pk, 'delete')
        svc.change_visibility(self.mod, item.pk, 'restore')
        item = svc.change_visibility(self.mod, item.pk, 'unhide')
        self.assertEqual(item.status, 'approved')
        self.assertEqual(item.published_revision.payload['name'], 'مركز أمل')

    def test_future_series_edit_does_not_rewrite_archived_occurrence(self):
        RoleGrant.objects.create(user=self.owner, role='moderator')
        item = self.approved(starts_at=(timezone.now()-timedelta(days=9)).isoformat(), recurrence='weekly', occurrence_count=3)
        RoleGrant.objects.filter(user=self.owner, role='moderator').delete()
        payload = dict(item.published_revision.payload)
        old_title = payload['title']
        payload['title'] = 'Future title'
        svc.edit_item(self.owner, item.pk, payload)
        svc.claim_review(self.mod, item.pk)
        svc.decide(self.mod, item.pk, True, '')
        rows = list(item.occurrences.order_by('starts_at'))
        self.assertEqual(rows[0].revision.payload['title'], old_title)
        self.assertEqual(rows[-1].revision.payload['title'], 'Future title')
        self.assertEqual(self.client.get('/api/v1/events/?q=Future&archived_only=true').data['results'], [])
        self.assertEqual(self.client.get('/api/v1/events/?q=Future').data['results'][0]['payload']['title'], 'Future title')

    def test_moderator_cannot_remove_active_organizers_registrants_blindly(self):
        item = self.approved()
        record, _ = reg.register(self.user, item.occurrences.get().pk)
        self.signin(self.mod)
        self.assertEqual(self.post(f'organizer/registrations/{record.pk}/remove', {'reason': 'Removal'}).status_code, 403)
        self.owner.is_active = False
        self.owner.save()
        self.assertEqual(self.post(f'organizer/registrations/{record.pk}/remove', {'reason': 'Steward removal'}).status_code, 200)

    def test_location_seed_is_repeatable_and_preserves_existing_entries(self):
        from django.core.management import call_command
        original = self.country.name_en
        with patch('catalog.management.commands.seed_locations.load_locations', return_value=[{'code': 'SY', 'name_ar': 'سوريا', 'name_en': 'Syria', 'cities': []}]):
            call_command('seed_locations', stdout=io.StringIO())
            call_command('seed_locations', stdout=io.StringIO())
        self.country.refresh_from_db()
        self.assertEqual(self.country.name_en, original)
        self.assertEqual(Country.objects.filter(code='SY').count(), 1)

    def test_partial_patch_preserves_other_fields_and_deleted_venue_snapshot(self):
        venue = self.approved('service')
        item = self.approved(service_id=venue.pk)
        svc.change_visibility(self.mod, venue.pk, 'delete')
        self.signin()
        response = self.client.patch(f'/api/v1/events/{item.pk}/', {'title': 'Edited title'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['payload']['title'], 'Edited title')
        self.assertEqual(response.data['payload']['speaker_name'], 'Speaker')
        self.assertEqual(response.data['payload']['venue_snapshot']['name'], 'مركز أمل')
        self.assertIsNone(response.data['payload']['service_id'])

    def test_hard_delete_removes_files_only_after_last_reference_is_gone(self):
        from .files import store, path_for
        asset = store(self.owner, self.upload_image(), 'image')
        Asset.objects.filter(pk=asset.pk).update(created_at=timezone.now()-timedelta(days=4))
        first = self.approved(image_ids=[asset.pk])
        second = self.approved(image_ids=[asset.pk])
        path = path_for(asset)
        svc.change_visibility(self.mod, first.pk, 'delete')
        Item.objects.filter(pk=first.pk).update(deleted_at=timezone.now()-timedelta(days=3, seconds=1))
        with self.captureOnCommitCallbacks(execute=True):
            run_jobs()
        self.assertTrue(path.exists())
        svc.change_visibility(self.mod, second.pk, 'delete')
        Item.objects.filter(pk=second.pk).update(deleted_at=timezone.now()-timedelta(days=3, seconds=1))
        with self.captureOnCommitCallbacks(execute=True):
            run_jobs()
        self.assertFalse(path.exists())
        self.assertFalse(Asset.objects.filter(pk=asset.pk).exists())

    def test_photo_orientation_is_applied_before_metadata_is_removed(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .files import store, path_for
        stream = io.BytesIO()
        photo = Image.new('RGB', (10, 20), 'blue')
        exif = Image.Exif()
        exif[274] = 6
        photo.save(stream, 'JPEG', exif=exif)
        asset = store(self.owner, SimpleUploadedFile('rotated.jpg', stream.getvalue()), 'image')
        with Image.open(path_for(asset)) as stored:
            self.assertEqual(stored.size, (20, 10))
            self.assertNotIn(274, stored.getexif())

    def test_same_named_places_are_distinct_and_city_search_is_paginated(self):
        for index in range(55):
            City.objects.create(country=self.country, name_ar='قرية', name_en='Same name', region_en=f'Region {index}', geonames_id=100000000+index)
        response = self.client.get(f'/api/v1/cities/?country={self.country.pk}&q=Same')
        self.assertEqual(len(response.data), 50)
        self.assertEqual(response['X-Next-Page'], '2')
        self.assertEqual(len(self.client.get(f'/api/v1/cities/?country={self.country.pk}&q=Same&page=2').data), 5)
        self.signin(self.mod)
        self.assertEqual(self.client.patch(f'/api/v1/admin/cities/{self.city.pk}/', {'name_ar': 'تعديل'}, format='json').status_code, 403)
        self.signin(self.admin)
        self.assertEqual(self.client.get(f'/api/v1/admin/cities/{self.city.pk}/').status_code, 200)
        self.assertEqual(self.client.patch(f'/api/v1/admin/cities/{self.city.pk}/', {'name_ar': 'تعديل'}, format='json').status_code, 200)
        self.client.credentials()
        self.assertEqual(self.client.get('/api/v1/cities/?q=تعديل').data[0]['id'], self.city.pk)

    def test_source_location_dataset_includes_major_cities_and_unique_source_ids(self):
        from .management.commands.seed_locations import load_locations
        data = load_locations()
        self.assertEqual(data[0]['code'], 'SY')
        cities = data[0]['cities']
        self.assertGreater(len(cities), 10000)
        self.assertEqual(len(cities), len({row['geonames_id'] for row in cities}))
        self.assertIn('Damascus', [row['name_en'] for row in cities])
        self.assertIn('دمشق', [row['name_ar'] for row in cities])

    def test_international_phone_accepts_arabic_digits_and_stores_e164(self):
        self.signin()
        response = self.post('services', self.service_payload(phone='+٤٤٢٠٨٣٦٦١١٧٧'))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['payload']['phone'], '+442083661177')

    def test_profile_partial_patch_preserves_existing_photo(self):
        from .files import store
        asset = store(self.owner, self.upload_image(), 'image')
        self.signin()
        self.assertEqual(self.client.patch('/api/v1/me/organizer-profile/', {'photo_id': asset.pk}, format='json').status_code, 200)
        response = self.client.patch('/api/v1/me/organizer-profile/', {'bio': 'Updated bio'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['photo_id'], asset.pk)
