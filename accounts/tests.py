"""Account integration and security regression tests; all data is temporary."""
import io
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit
from django.conf import settings
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient
from .maintenance import cleanup_accounts
from .models import AuditEntry, Consent, EmailMessage, EmailToken, OrganizerRequest, Policy, RoleGrant, Session, User
from .services import consume_token, digest, issue_session, queue_token


class AccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.policy = Policy.objects.create(terms_ar='شروط', terms_en='Terms', privacy_ar='خصوصية', privacy_en='Privacy')
        self.user = User.objects.create_user('user@example.org', 'secret123', name='User', verified_at=timezone.now())
        self.admin = User.objects.create_user('admin@example.org', 'secret123', name='Admin', verified_at=timezone.now())
        self.mod = User.objects.create_user('mod@example.org', 'secret123', name='Moderator', verified_at=timezone.now())
        RoleGrant.objects.create(user=self.admin, role='admin')
        RoleGrant.objects.create(user=self.mod, role='moderator')
        self.private = TemporaryDirectory()
        self.override = override_settings(PRIVATE_CREDENTIAL_ROOT=Path(self.private.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.private.cleanup)

    def signin(self, user=None):
        result = issue_session(user or self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + result['access_token'])
        return result

    def post(self, path, data=None):
        return self.client.post('/api/v1/' + path + '/', data or {}, format='json')

    def token(self, user, purpose):
        message = EmailMessage.objects.filter(user=user).latest('pk')
        return parse_qs(urlsplit(message.body.splitlines()[-1]).fragment)['token'][0]

    def image(self):
        stream = io.BytesIO()
        Image.new('RGB', (20, 20)).save(stream, format='PNG')
        return SimpleUploadedFile('credential.png', stream.getvalue(), content_type='image/png')

    def apply(self):
        return self.client.post('/api/v1/organizer-requests/', {'name': 'Doctor', 'workplace': 'Office',
            'reason': 'Teach professionals', 'credential': self.image()}, format='multipart')

    def test_signup_requires_current_consent_and_strong_enough_password(self):
        data = {'email': 'new@example.org', 'password': 'abcdef', 'name': 'New', 'policy_id': self.policy.pk, 'consent': False}
        self.assertEqual(self.post('auth/signup', data).status_code, 400)
        data['consent'] = True
        data['password'] = 'short'
        self.assertEqual(self.post('auth/signup', data).status_code, 400)
        data['password'] = 'abcdef'
        response = self.post('auth/signup', data)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email=data['email'])
        self.assertIsNone(user.verified_at)
        self.assertTrue(user.password.startswith('argon2'))
        self.assertEqual(Consent.objects.filter(user=user).count(), 1)
        self.assertNotIn(response.data['access_token'], Session.objects.get(user=user).access_hash)
        self.assertEqual(self.post('auth/signup', data).status_code, 400)

    def test_verification_requires_single_use_unexpired_token(self):
        self.user.verified_at = None
        self.user.save()
        response = self.post('auth/verification/request', {'email': self.user.email})
        self.assertEqual(response.status_code, 200)
        token = self.token(self.user, 'verify')
        self.assertEqual(self.post('auth/verification/confirm', {'token': token}).status_code, 200)
        self.assertEqual(self.post('auth/verification/confirm', {'token': token}).status_code, 400)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.verified_at)

    def test_expired_link_does_not_verify(self):
        queue_token(self.user, 'verify')
        token = self.token(self.user, 'verify')
        EmailToken.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.post('auth/verification/confirm', {'token': token}).status_code, 400)

    def test_unknown_email_recovery_has_same_response(self):
        first = self.post('auth/password/forgot', {'email': self.user.email})
        second = self.post('auth/password/forgot', {'email': 'missing@example.org'})
        self.assertEqual(first.data, second.data)
        self.assertEqual(second.status_code, 200)

    def test_login_rotation_rejects_previous_refresh_and_access(self):
        response = self.post('auth/login', {'email': 'USER@example.org', 'password': 'secret123'})
        self.assertEqual(response.status_code, 200)
        old = response.data
        new = self.post('auth/refresh', {'refresh_token': old['refresh_token']})
        self.assertEqual(new.status_code, 200)
        self.assertEqual(self.post('auth/refresh', {'refresh_token': old['refresh_token']}).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + old['access_token'])
        self.assertEqual(self.client.get('/api/v1/me/').status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + new.data['access_token'])
        self.assertEqual(self.client.get('/api/v1/me/').status_code, 200)

    @override_settings(LOGIN_LIMIT=2)
    def test_failed_attempts_commit_and_lock_out(self):
        data = {'email': self.user.email, 'password': 'wrong'}
        self.assertEqual(self.post('auth/login', data).status_code, 401)
        self.assertEqual(self.post('auth/login', data).status_code, 401)
        self.assertEqual(self.post('auth/login', {'email': self.user.email, 'password': 'secret123'}).status_code, 429)

    def test_logout_revokes_only_current_device(self):
        current = self.signin()
        other = issue_session(self.user)
        self.assertEqual(self.post('auth/logout').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/me/').status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+other['access_token'])
        self.assertEqual(self.client.get('/api/v1/me/').status_code, 200)

    def test_logout_all_revokes_refresh_on_every_device(self):
        self.signin()
        other = issue_session(self.user)
        self.assertEqual(self.post('auth/logout-all').status_code, 200)
        self.client.credentials()
        self.assertEqual(self.post('auth/refresh', {'refresh_token': other['refresh_token']}).status_code, 401)

    def test_password_reset_revokes_existing_sessions(self):
        self.signin()
        self.client.credentials()
        self.post('auth/password/forgot', {'email': self.user.email})
        token = self.token(self.user, 'reset')
        self.assertEqual(self.post('auth/password/reset', {'token': token, 'password': 'replacement'}).status_code, 200)
        self.assertFalse(Session.objects.filter(user=self.user, revoked_at=None).exists())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('replacement'))

    def test_password_change_requires_current_password_and_revokes_all(self):
        self.signin()
        data = {'current_password': 'wrong', 'password': 'replacement'}
        self.assertEqual(self.post('me/password/change', data).status_code, 400)
        data['current_password'] = 'secret123'
        self.assertEqual(self.post('me/password/change', data).status_code, 200)
        self.assertEqual(self.client.get('/api/v1/me/').status_code, 401)

    def test_email_change_keeps_old_email_until_confirmation(self):
        self.signin()
        self.assertEqual(self.post('me/email/change', {'email': 'changed@example.org', 'password': 'secret123'}).status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'user@example.org')
        token = self.token(self.user, 'change_email')
        self.client.credentials()
        self.assertEqual(self.post('me/email/confirm', {'token': token}).status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'changed@example.org')
        self.assertFalse(Session.objects.filter(user=self.user, revoked_at=None).exists())

    def test_profile_update_cannot_assign_roles_or_verify_email(self):
        self.signin()
        response = self.client.patch('/api/v1/me/', {'name': 'Changed', 'roles': ['admin'], 'verified_at': 'now'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, 'Changed')
        self.assertFalse(self.user.has_role('admin'))

    def test_export_excludes_password_and_token_secrets(self):
        tokens = self.signin()
        response = self.client.get('/api/v1/me/data-export/')
        self.assertEqual(response.status_code, 200)
        text = response.content.decode()
        self.assertNotIn(tokens['access_token'], text)
        self.assertNotIn(self.user.password, text)
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_delete_account_requires_password_and_deletes_related_data(self):
        self.signin()
        Consent.objects.create(user=self.user, policy=self.policy)
        self.assertEqual(self.client.delete('/api/v1/me/', {'password': 'wrong'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete('/api/v1/me/', {'password': 'secret123'}, format='json').status_code, 204)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Session.objects.filter(user_id=self.user.pk).exists())
        self.assertFalse(Consent.objects.filter(user_id=self.user.pk).exists())

    def test_last_admin_cannot_self_delete(self):
        self.signin(self.admin)
        self.assertEqual(self.client.delete('/api/v1/me/', {'password': 'secret123'}, format='json').status_code, 400)

    def test_admin_grants_multiple_roles_and_audits(self):
        self.signin(self.admin)
        for role in ['organizer', 'moderator']:
            self.assertEqual(self.post(f'admin/users/{self.user.pk}/roles', {'role': role, 'enabled': True}).status_code, 200)
        self.assertTrue(self.user.has_role('organizer'))
        self.assertTrue(self.user.has_role('moderator'))
        self.assertEqual(AuditEntry.objects.filter(action='role.grant').count(), 2)

    def test_moderator_and_guests_cannot_manage_roles_audit_or_users(self):
        self.assertEqual(self.client.get('/api/v1/admin/audit/').status_code, 401)
        self.signin(self.mod)
        self.assertEqual(self.post(f'admin/users/{self.user.pk}/roles', {'role': 'admin', 'enabled': True}).status_code, 403)
        self.assertEqual(self.client.get('/api/v1/admin/audit/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/admin/users/').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/v1/admin/users/{self.user.pk}/').status_code, 403)
        self.assertEqual(self.post('admin/policies', {'terms_ar': 'x', 'terms_en': 'x', 'privacy_ar': 'x', 'privacy_en': 'x'}).status_code, 403)

    def test_admin_ban_revokes_sessions_and_login_shows_reason(self):
        tokens = issue_session(self.user)
        self.signin(self.admin)
        self.assertEqual(self.post(f'admin/users/{self.user.pk}/ban', {'banned': True, 'reason': 'Spam'}).status_code, 200)
        self.client.credentials()
        response = self.post('auth/login', {'email': self.user.email, 'password': 'secret123'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(str(response.data['reason']), 'Spam')
        self.assertEqual(self.post('auth/refresh', {'refresh_token': tokens['refresh_token']}).status_code, 401)
        self.signin(self.admin)
        self.assertEqual(self.post(f'admin/users/{self.user.pk}/ban', {'banned': False}).status_code, 200)
        self.assertTrue(AuditEntry.objects.filter(action='user.ban').exists())

    def test_admin_audit_and_users_listing_are_paginated(self):
        self.signin(self.admin)
        self.assertEqual(self.client.get('/api/v1/admin/audit/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/admin/users/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/admin/audit/?before=bad').status_code, 400)

    def test_admin_delete_preserves_audit_metadata(self):
        self.signin(self.admin)
        target = self.user.pk
        self.assertEqual(self.client.delete(f'/api/v1/admin/users/{target}/').status_code, 204)
        self.assertTrue(AuditEntry.objects.filter(action='user.delete', target_id=str(target)).exists())

    @override_settings(ADMIN_IP_RESTRICTION=True, ADMIN_ALLOWED_NETWORKS=['192.0.2.0/24'])
    def test_admin_allowlist_ignores_forged_forwarding_headers(self):
        self.signin(self.admin)
        response = self.client.get('/api/v1/admin/audit/', REMOTE_ADDR='198.51.100.1', HTTP_X_FORWARDED_FOR='192.0.2.1')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get('/api/v1/admin/audit/', REMOTE_ADDR='192.0.2.1').status_code, 200)

    def test_policies_are_public_and_admin_updates_create_new_version(self):
        self.assertEqual(self.client.get('/api/v1/policies/current/').status_code, 200)
        self.signin(self.admin)
        response = self.post('admin/policies', {'terms_ar': 'جديد', 'terms_en': 'New', 'privacy_ar': 'جديد', 'privacy_en': 'New'})
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.data['id'], self.policy.pk)
        self.assertTrue(AuditEntry.objects.filter(action='policy.publish').exists())

    def test_account_link_is_no_store_and_does_not_consume_tokens(self):
        queue_token(self.user, 'verify')
        response = self.client.get('/account-link/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertFalse(EmailToken.objects.filter(used_at__isnull=False).exists())

    def test_unverified_users_cannot_apply(self):
        self.user.verified_at = None
        self.user.save()
        self.signin()
        self.assertEqual(self.apply().status_code, 403)
        self.assertFalse(list(Path(self.private.name).iterdir()))

    def test_one_open_request_and_private_credential_access(self):
        self.signin()
        response = self.apply()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.apply().status_code, 400)
        request_id = response.data['id']
        record = OrganizerRequest.objects.get(pk=request_id)
        self.assertTrue((Path(self.private.name)/record.credential_name).exists())
        self.assertEqual(self.client.get('/api/v1/me/organizer-requests/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/v1/moderation/organizer-requests/{request_id}/credential/').status_code, 403)
        self.signin(self.mod)
        self.assertEqual(self.client.get('/api/v1/moderation/organizer-requests/').status_code, 200)
        download = self.client.get(f'/api/v1/moderation/organizer-requests/{request_id}/credential/')
        self.assertEqual(download.status_code, 200)
        list(download.streaming_content)
        self.assertEqual(download['Cache-Control'], 'no-store')

    def test_review_lock_approval_deletes_document_and_grants_role(self):
        self.signin()
        request_id = self.apply().data['id']
        path = Path(self.private.name)/OrganizerRequest.objects.get(pk=request_id).credential_name
        self.signin(self.mod)
        base = f'moderation/organizer-requests/{request_id}'
        self.assertEqual(self.post(base+'/decide', {'approved': True}).status_code, 403)
        self.assertEqual(self.post(base+'/claim').status_code, 200)
        self.signin(self.admin)
        self.assertEqual(self.post(base+'/claim').status_code, 400)
        self.assertEqual(self.post(base+'/decide', {'approved': True}).status_code, 403)
        self.assertEqual(self.post(f'admin/organizer-requests/{request_id}/unlock').status_code, 200)
        self.signin(self.mod)
        self.post(base+'/claim')
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post(base+'/decide', {'approved': True}).status_code, 200)
        self.assertFalse(path.exists())
        self.assertTrue(self.user.has_role('organizer'))
        self.assertEqual(self.client.get('/api/v1/'+base+'/credential/').status_code, 404)

    def test_rejected_applicant_can_reapply_immediately(self):
        self.signin()
        request_id = self.apply().data['id']
        self.signin(self.mod)
        self.post(f'moderation/organizer-requests/{request_id}/claim')
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post(f'moderation/organizer-requests/{request_id}/decide', {'approved': False, 'reason': 'Unreadable'}).status_code, 200)
        self.signin()
        self.assertEqual(self.apply().status_code, 201)

    def test_invalid_or_oversized_credentials_are_rejected(self):
        self.signin()
        for file in [SimpleUploadedFile('fake.jpg', b'not an image'), SimpleUploadedFile('large.pdf', b'x'*(5*1024*1024+1))]:
            response = self.client.post('/api/v1/organizer-requests/', {'name': 'Name', 'workplace': 'Office', 'reason': 'Reason', 'credential': file}, format='multipart')
            self.assertEqual(response.status_code, 400)
            self.assertTrue(response['Content-Type'].startswith('application/json'))
        self.assertFalse(list(Path(self.private.name).iterdir()))

    def test_cleanup_deletes_only_overdue_unverified_accounts_and_is_repeatable(self):
        old = User.objects.create_user('old@example.org', 'secret123', name='Old', created_at=timezone.now()-timedelta(days=7, seconds=1))
        recent = User.objects.create_user('recent@example.org', 'secret123', name='Recent')
        self.assertEqual(cleanup_accounts(), 1)
        self.assertEqual(cleanup_accounts(), 0)
        self.assertFalse(User.objects.filter(pk=old.pk).exists())
        self.assertTrue(User.objects.filter(pk=recent.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', EMAIL_HOST='smtp.example.org', DEFAULT_FROM_EMAIL='noreply@example.org')
    def test_email_queue_sends_once_then_removes_body_secrets(self):
        queue_token(self.user, 'verify')
        call_command('send_account_emails', stdout=io.StringIO())
        call_command('send_account_emails', stdout=io.StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Verify email', mail.outbox[0].body)
        self.assertIn('تأكيد', mail.outbox[0].body)
        self.assertEqual(EmailMessage.objects.get().body, '')

    @override_settings(TRUST_LOCAL_PROXY=True)
    def test_local_proxy_supplies_validated_client_ip_only(self):
        self.signin(self.admin)
        with override_settings(ADMIN_IP_RESTRICTION=True, ADMIN_ALLOWED_NETWORKS=['192.0.2.0/24']):
            self.assertEqual(self.client.get('/api/v1/admin/audit/', REMOTE_ADDR='127.0.0.1', HTTP_X_REAL_IP='192.0.2.1').status_code, 200)
            self.assertEqual(self.client.get('/api/v1/admin/audit/', REMOTE_ADDR='198.51.100.1', HTTP_X_REAL_IP='192.0.2.1').status_code, 400)
            self.assertEqual(self.client.get('/api/v1/admin/audit/', REMOTE_ADDR='127.0.0.1', HTTP_X_REAL_IP='bad').status_code, 400)

    def test_new_link_invalidates_old_and_replaces_unsent_email(self):
        queue_token(self.user, 'reset')
        old = self.token(self.user, 'reset')
        queue_token(self.user, 'reset')
        self.assertEqual(EmailMessage.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.post('auth/password/reset', {'token': old, 'password': 'replacement'}).status_code, 400)

    def test_deleting_applicant_removes_private_document_after_commit(self):
        self.signin()
        record = OrganizerRequest.objects.get(pk=self.apply().data['id'])
        path = Path(self.private.name)/record.credential_name
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.delete('/api/v1/me/', {'password': 'secret123'}, format='json').status_code, 204)
        self.assertFalse(path.exists())

    def test_moderator_cannot_unlock_or_ban_and_last_admin_is_protected(self):
        self.signin()
        request_id = self.apply().data['id']
        self.signin(self.mod)
        self.assertEqual(self.post(f'admin/organizer-requests/{request_id}/unlock').status_code, 403)
        self.assertEqual(self.post(f'admin/users/{self.user.pk}/ban', {'banned': True, 'reason': 'Reason'}).status_code, 403)
        self.signin(self.admin)
        self.assertEqual(self.post(f'admin/users/{self.admin.pk}/roles', {'role': 'admin', 'enabled': False}).status_code, 400)
        self.assertEqual(self.post(f'admin/users/{self.admin.pk}/ban', {'banned': True, 'reason': 'Reason'}).status_code, 400)

    def test_staff_login_has_stricter_failure_limit(self):
        for _ in range(settings.STAFF_LOGIN_LIMIT):
            self.assertEqual(self.post('auth/login', {'email': self.admin.email, 'password': 'wrong'}).status_code, 401)
        self.assertEqual(self.post('auth/login', {'email': self.admin.email, 'password': 'secret123'}).status_code, 429)

    def test_pdf_credential_validation_accepts_document_and_rejects_encrypted_pdf(self):
        from pypdf import PdfWriter
        self.signin()
        for encrypted in (True, False):
            writer = PdfWriter()
            writer.add_blank_page(width=200, height=200)
            if encrypted:
                writer.encrypt('password')
            output = io.BytesIO()
            writer.write(output)
            file = SimpleUploadedFile('license.pdf', output.getvalue(), content_type='application/pdf')
            response = self.client.post('/api/v1/organizer-requests/', {'name': 'Name', 'workplace': 'Office', 'reason': 'Reason', 'credential': file}, format='multipart')
            self.assertEqual(response.status_code, 400 if encrypted else 201)

    @override_settings(EMAIL_HOST='smtp.example.org', DEFAULT_FROM_EMAIL='noreply@example.org')
    def test_smtp_failure_retains_email_and_schedules_retry(self):
        from unittest.mock import patch
        queue_token(self.user, 'verify')
        with patch('accounts.management.commands.send_account_emails.send_mail', side_effect=OSError('Unavailable')):
            call_command('send_account_emails', stdout=io.StringIO(), stderr=io.StringIO())
        message = EmailMessage.objects.get()
        self.assertIsNone(message.sent_at)
        self.assertEqual(message.attempts, 1)
        self.assertGreater(message.next_attempt_at, timezone.now())
        self.assertTrue(message.body)


class BootstrapTests(TestCase):
    def test_bootstrap_creates_only_admin_and_refuses_second_run(self):
        from unittest.mock import patch
        from django.core.management.base import CommandError
        with patch('builtins.input', side_effect=['first@example.org', 'First']), patch(
            'accounts.management.commands.bootstrap_admin.getpass', return_value='secret123'):
            call_command('bootstrap_admin', stdout=io.StringIO())
        user = User.objects.get(email='first@example.org')
        self.assertTrue(user.verified_at)
        self.assertTrue(user.has_role('admin'))
        self.assertFalse(user.has_role('organizer'))
        self.assertEqual(Policy.objects.count(), 1)
        self.assertTrue(AuditEntry.objects.filter(action='admin.bootstrap').exists())
        with self.assertRaises(CommandError):
            call_command('bootstrap_admin', stdout=io.StringIO())
