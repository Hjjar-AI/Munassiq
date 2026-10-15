"""Browser-facing integration checks; no external browser, maps or real mail."""
from datetime import timedelta
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import Policy, Session
from accounts.services import issue_session, digest
from catalog.tests import FixtureMixin
from catalog.models import Item
from .operations import OPERATIONS
from .middleware import ACCESS,REFRESH


class DashboardTests(FixtureMixin,TestCase):
    def setUp(self):
        super().setUp()
        self.browser=Client()
        self.policy=Policy.objects.create(terms_ar='شروط',terms_en='Terms',privacy_ar='خصوصية',privacy_en='Privacy')

    def browser_signin(self,user=None):
        tokens=issue_session(user or self.user)
        self.browser.cookies[ACCESS]=tokens['access_token']
        self.browser.cookies[REFRESH]=tokens['refresh_token']
        return tokens

    def test_public_pages_render_both_languages_and_hide_staff_navigation(self):
        for path in ['/','/dashboard/','/dashboard/section/events/','/dashboard/section/services/','/dashboard/section/categories/','/dashboard/section/map/','/dashboard/login/']:
            response=self.browser.get(path)
            self.assertEqual(response.status_code,200,path)
            self.assertContains(response,'dir="rtl"')
            self.assertNotContains(response,'/dashboard/section/audit/')
        self.browser.post('/dashboard/language/',{'language':'en'})
        self.assertContains(self.browser.get('/dashboard/'),'dir="ltr"')

    def test_login_cookies_no_tokens_in_html_and_browser_logout(self):
        response=self.browser.post('/dashboard/login/',{'email':self.user.email,'password':'secret123'})
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.cookies[ACCESS]['httponly'])
        self.assertEqual(response.cookies[REFRESH]['samesite'],'Lax')
        account=self.browser.get('/dashboard/section/account/')
        self.assertEqual(account.status_code,200)
        self.assertNotContains(account,response.cookies[ACCESS].value)
        self.assertEqual(self.browser.get('/api/v1/me/').status_code,401)
        self.assertEqual(self.browser.get('/dashboard/logout/').status_code,405)
        self.assertEqual(self.browser.post('/dashboard/logout/').status_code,302)
        self.assertEqual(self.browser.get('/dashboard/section/account/').status_code,302)

    def test_csrf_required_for_login_and_actions(self):
        browser=Client(enforce_csrf_checks=True)
        self.assertEqual(browser.post('/dashboard/login/',{'email':self.user.email,'password':'secret123'}).status_code,403)
        browser.get('/dashboard/login/')
        csrf=browser.cookies['csrftoken'].value
        self.assertEqual(browser.post('/dashboard/login/',{'email':self.user.email,'password':'secret123','csrfmiddlewaretoken':csrf}).status_code,302)
        self.assertEqual(browser.post('/dashboard/action/logout-all/0/',{'confirm':'on'}).status_code,403)

    def test_expired_access_refresh_rotates_and_revoked_session_stays_blocked(self):
        tokens=self.browser_signin()
        Session.objects.filter(access_hash=digest(tokens['access_token'])).update(access_expires_at=timezone.now()-timedelta(minutes=1))
        response=self.browser.get('/dashboard/section/account/')
        self.assertEqual(response.status_code,200)
        self.assertNotEqual(response.cookies[REFRESH].value,tokens['refresh_token'])
        Session.objects.filter(user=self.user).update(revoked_at=timezone.now())
        self.assertEqual(self.browser.get('/dashboard/section/account/').status_code,302)

    def test_guest_staff_pages_hidden_and_nonstaff_cannot_use_staff_forms(self):
        for path in ['/dashboard/section/users/','/dashboard/section/reviews/','/dashboard/form/announcement/0/','/dashboard/review/1/']:
            self.assertEqual(self.browser.get(path).status_code,404,path)
        self.browser_signin(self.user)
        for path in ['/dashboard/section/users/','/dashboard/form/roles/1/','/dashboard/action/delete-user/1/']:
            self.assertEqual(self.browser.get(path).status_code,404,path)

    def test_all_authorized_form_pages_render_without_exposing_credentials(self):
        self.browser_signin(self.admin)
        self.approved()
        for operation,spec in OPERATIONS.items():
            if operation in ('organizer-profile','duplicate','reminder','reschedule','remove-registration','decision','organizer-decision','resolve','edit-category','edit-city'):continue
            response=self.browser.get(f'/dashboard/form/{operation}/0/')
            if spec[5]=='organizer':self.assertEqual(response.status_code,404)
            else:self.assertEqual(response.status_code,200,(operation,response.content[:300]))

    def test_guest_contacts_redacted_and_public_event_fallback_exists(self):
        item=self.approved()
        response=self.browser.get(f'/events/{item.pk}/')
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,item.published_revision.payload['phone'])
        self.browser_signin()
        self.assertContains(self.browser.get(f'/events/{item.pk}/'),item.published_revision.payload['phone'])

    def test_organizer_create_edit_keeps_live_revision_until_review(self):
        self.browser_signin(self.owner)
        data=self.event_payload()
        data.update(starts_at=(timezone.now()+timedelta(days=3)).strftime('%Y-%m-%dT%H:%M'),
            category_ids=[str(self.category.pk)],image_ids='')
        response=self.browser.post('/dashboard/new/event/',data)
        self.assertEqual(response.status_code,200,response.content[:500])
        item=Item.objects.get(owner=self.owner)
        self.assertEqual(item.status,'pending')
        from catalog.services import claim_review,decide
        claim_review(self.mod,item.pk);decide(self.mod,item.pk,True,'')
        item.refresh_from_db()
        self.assertEqual(self.browser.get(f'/dashboard/edit/event/{item.pk}/').status_code,200)
        original=item.published_revision_id
        data['title']='Updated title'
        self.browser.post(f'/dashboard/edit/event/{item.pk}/',data)
        item.refresh_from_db()
        self.assertEqual(item.status,'pending_changes')
        self.assertEqual(item.published_revision_id,original)

    def test_confirmation_is_required_and_review_lock_enforced(self):
        item=self.approved()
        self.browser_signin(self.user)
        response=self.browser.post(f'/dashboard/action/register/{item.occurrences.get().pk}/',{})
        self.assertEqual(response.status_code,200)
        self.assertFalse(item.occurrences.get().registrations.exists())
        self.browser.post(f'/dashboard/action/register/{item.occurrences.get().pk}/',{'confirm':'on'})
        self.assertEqual(item.occurrences.get().registrations.get().state,'registered')

    def test_staff_pages_and_role_tools_render(self):
        self.browser_signin(self.admin)
        item=self.approved()
        for slug in ['mine','reviews','manage','applications','reports','feedback','users','statistics','audit','announcements','locations','devices','requests','registrations']:
            response=self.browser.get('/dashboard/section/'+slug+'/')
            self.assertEqual(response.status_code,200,slug)
        self.assertEqual(self.browser.get(f'/dashboard/review/{item.pk}/').status_code,200)
        self.assertEqual(self.browser.get(f'/dashboard/correct/event/{item.pk}/').status_code,200)

    def test_download_privacy_and_export_routes(self):
        item=self.approved()
        occurrence=item.occurrences.get()
        self.browser_signin(self.owner)
        self.assertEqual(self.browser.get(f'/dashboard/occurrences/{occurrence.pk}/').status_code,200)
        response=self.browser.get(f'/dashboard/download/csv/{occurrence.pk}/')
        self.assertEqual(response.status_code,200)
        self.assertIn('attachment',response['Content-Disposition'])
        self.browser_signin(self.other)
        self.assertEqual(self.browser.get(f'/dashboard/download/csv/{occurrence.pk}/').status_code,403)
        self.assertEqual(self.browser.get('/dashboard/download/data/0/').status_code,200)
        calendar=self.browser.get(f'/dashboard/download/calendar/{occurrence.pk}/')
        self.assertEqual(calendar.status_code,200)

    def test_location_and_marker_endpoints_and_blank_filter_values(self):
        for path in ['/dashboard/locations/?country='+str(self.country.pk),'/dashboard/markers/','/dashboard/section/events/?country=&city=&category=']:
            self.assertEqual(self.browser.get(path).status_code,200,path)

    def test_profile_feedback_and_signup_use_real_api_validation(self):
        self.browser_signin()
        response=self.browser.post('/dashboard/form/profile/0/',{'name':'New name','language':'en'})
        self.assertEqual(response.status_code,200)
        self.user.refresh_from_db();self.assertEqual(self.user.name,'New name')
        self.assertEqual(self.browser.post('/dashboard/form/feedback/0/',{'text':'Directory feedback'}).status_code,200)
        self.browser.cookies.clear()
        response=self.browser.post('/dashboard/form/signup/0/',{'email':'new@example.org','name':'New','password':'secret123','language':'ar','consent':'on','displayed_policy_id':self.policy.pk})
        self.assertEqual(response.status_code,302,response.content[:500])

    @override_settings(ADMIN_IP_RESTRICTION=True,ADMIN_ALLOWED_NETWORKS=['192.0.2.0/24'])
    def test_admin_ip_restriction_applies_to_dashboard(self):
        self.browser_signin(self.admin)
        self.assertEqual(self.browser.get('/dashboard/section/users/').status_code,404)

    def test_script_content_is_escaped(self):
        item=self.approved(title='<script>alert(1)</script>')
        response=self.browser.get(f'/events/{item.pk}/')
        self.assertNotContains(response,'<script>alert(1)</script>')
        self.assertContains(response,'&lt;script&gt;')

    def test_stale_policy_cannot_be_accepted_silently(self):
        previous=self.policy.pk
        Policy.objects.create(terms_ar='جديد',terms_en='New',privacy_ar='جديد',privacy_en='New')
        response=self.browser.post('/dashboard/form/signup/0/',{'email':'not-created@example.org','name':'New','password':'secret123','language':'ar','consent':'on','displayed_policy_id':previous})
        self.assertEqual(response.status_code,200)
        from accounts.models import User
        self.assertFalse(User.objects.filter(email='not-created@example.org').exists())

    def test_multipart_credential_stays_private_and_reviewer_can_download(self):
        self.browser_signin()
        response=self.browser.post('/dashboard/form/apply/0/',{'name':'Applicant','workplace':'Clinic','reason':'Directory organizer','credential':self.upload_image()})
        self.assertEqual(response.status_code,200)
        from accounts.models import OrganizerRequest
        application=OrganizerRequest.objects.get(user=self.user)
        self.assertEqual(self.browser.get(f'/dashboard/download/credential/{application.pk}/').status_code,403)
        self.browser_signin(self.mod)
        response=self.browser.get(f'/dashboard/download/credential/{application.pk}/')
        self.assertEqual(response.status_code,200)
        list(response.streaming_content)

    def test_service_duplicate_requires_explicit_confirmation(self):
        self.approved('service')
        self.browser_signin(self.owner)
        data=self.service_payload()
        data.update(category_ids=[str(self.category.pk)],image_ids='')
        response=self.browser.post('/dashboard/new/service/',data)
        self.assertEqual(response.status_code,200)
        self.assertEqual(Item.objects.filter(kind='service').count(),1)
        self.assertContains(response,'confirm_duplicate')
        data['confirm_duplicate']='on'
        self.browser.post('/dashboard/new/service/',data)
        self.assertEqual(Item.objects.filter(kind='service').count(),2)

    def test_upload_proxy_enforces_permissions_and_supports_staff_corrections(self):
        self.browser_signin(self.user)
        self.assertEqual(self.browser.post('/dashboard/upload/images/',{'file':self.upload_image()}).status_code,403)
        self.browser_signin(self.mod)
        response=self.browser.post('/dashboard/upload/images/',{'file':self.upload_image()})
        self.assertEqual(response.status_code,201,response.content[:200])
        self.assertIn('id',response.json())
        # Reviewer permission still does not authorize creation of new content.
        self.assertEqual(self.browser.get('/dashboard/new/event/').status_code,404)

    def test_password_whitespace_is_preserved(self):
        self.user.set_password(' spaced secret ');self.user.save()
        self.assertEqual(self.browser.post('/dashboard/login/',{'email':self.user.email,'password':' spaced secret '}).status_code,302)

    def test_event_view_cookie_reaches_browser_for_guest_deduplication(self):
        from catalog.models import EventViewTotal
        item=self.approved()
        self.browser.get(f'/events/{item.pk}/')
        self.browser.get(f'/events/{item.pk}/')
        self.assertEqual(EventViewTotal.objects.get(event=item).count,1)
