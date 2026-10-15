"""API permissions and notification queue lifecycle, without sending real push."""
from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.core.management import call_command, CommandError
from django.utils import timezone
from accounts.models import AuditEntry, MaintenanceRun, User
from accounts.services import set_ban
from catalog.models import Notice, Reminder
from catalog.tests import FixtureMixin
from catalog import registration, services
from .fcm import PushError, Sender
from .models import Announcement, CategoryFollow, Delivery, Device, DigestRun, Dispatch, OrganizerFollow, PendingFollow, Preferences
from .services import generate_follow_notices, generate_reminders, quiet_now
from .worker import expand_notices, payload, run, send_due


class NotificationTests(FixtureMixin, TestCase):
    def device(self, user=None):
        self.signin(user or self.user)
        response = self.client.put('/api/v1/me/devices/', {'installation_id': str(uuid4()),
            'token': 'example-device-token-'+str(uuid4())}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return Device.objects.get(pk=response.data['id'])

    def test_preferences_validate_partial_updates_location_zone_and_quiet_hours(self):
        self.signin(self.user)
        path = '/api/v1/me/notification-preferences/'
        self.assertEqual(self.client.get(path).data['language'], 'ar')
        result = self.client.patch(path, {'language':'en', 'country_id':self.country.pk,
            'city_id':self.city.pk, 'quiet_start':'22:00', 'quiet_end':'07:00'}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.language, 'en')
        for data in [{'time_zone':'bad/zone'}, {'quiet_start':None}, {'country_id':None}, {'quiet_start':'07:00'}]:
            self.assertEqual(self.client.patch(path,data,format='json').status_code,400)
        self.assertEqual(self.client.patch(path, {'quiet_start':None, 'quiet_end':None}, format='json').status_code,200)

    def test_device_rotation_transfer_private_list_and_ownership(self):
        device = self.device()
        original_id = device.pk
        data = {'installation_id':str(device.installation_id),'token':device.token}
        self.assertEqual(self.client.put('/api/v1/me/devices/', data, format='json').data['id'],original_id)
        self.assertNotIn('token', self.client.get('/api/v1/me/devices/').data[0])
        self.signin(self.other)
        self.assertEqual(self.client.delete(f'/api/v1/me/devices/{original_id}/').status_code,404)
        self.assertEqual(self.client.put('/api/v1/me/devices/', data, format='json').status_code,200)
        self.assertFalse(Device.objects.filter(user=self.user).exists())
        moved = Device.objects.get(user=self.other)
        self.assertEqual(self.client.delete(f'/api/v1/me/devices/{moved.pk}/').status_code,204)

    def test_follow_endpoints_are_idempotent_and_private(self):
        self.signin(self.user)
        org = f'/api/v1/me/follows/organizers/{self.owner.pk}/'
        cat = f'/api/v1/me/follows/categories/{self.category.pk}/'
        for path in [org,cat]:
            self.assertEqual(self.client.put(path,{},format='json').status_code,204)
            self.assertEqual(self.client.put(path,{},format='json').status_code,204)
        self.assertEqual(self.client.get('/api/v1/me/follows/').data,
            {'organizer_ids':[self.owner.pk],'category_ids':[self.category.pk]})
        self.assertEqual(OrganizerFollow.objects.count(),1)
        for path in [org,cat]:
            self.assertEqual(self.client.delete(path).status_code,204)
        self.assertEqual(self.client.put(f'/api/v1/me/follows/organizers/{self.other.pk}/',{},format='json').status_code,404)

    def test_guests_cannot_read_private_notification_routes(self):
        for path in ['me/follows/','me/devices/','me/notification-preferences/','admin/statistics/','admin/announcements/','admin/app-settings/']:
            self.assertEqual(self.client.get('/api/v1/'+path).status_code,401)

    def test_admin_settings_statistics_permissions_and_audits(self):
        self.signin(self.mod)
        for path in ['statistics','app-settings','announcements']:
            self.assertEqual(self.client.get('/api/v1/admin/'+path+'/').status_code,403)
        self.signin(self.admin)
        self.assertEqual(self.client.get('/api/v1/admin/statistics/').data['users'],5)
        self.assertEqual(self.client.get('/api/v1/admin/app-settings/').status_code,200)
        result = self.client.patch('/api/v1/admin/app-settings/', {'guide_ar':'دليل','apk_download_url':'https://example.org/app.apk'}, format='json')
        self.assertEqual(result.status_code,200)
        self.client.credentials()
        self.assertEqual(self.client.get('/api/v1/app-settings/').data['guide_ar'],'دليل')
        self.assertTrue(AuditEntry.objects.filter(action='statistics.read',actor=self.admin).exists())

    def announcement(self, **extra):
        self.signin(self.admin)
        result = self.post('admin/announcements', {'title_ar':'إعلان','title_en':'Notice',
            'body_ar':'رسالة','body_en':'Message', **extra})
        self.assertEqual(result.status_code,201,result.data)
        return Announcement.objects.get(pk=result.data['id'])

    @override_settings(ANNOUNCEMENTS_PER_ADMIN_PER_DAY=1)
    def test_announcement_default_banner_limit_and_audit(self):
        row = self.announcement()
        self.assertAlmostEqual((row.expires_at-row.created_at).total_seconds(),7*86400,delta=5)
        self.assertEqual(self.post('admin/announcements', {'title_ar':'إعلان','title_en':'Notice','body_ar':'رسالة','body_en':'Message'}).status_code,400)
        self.assertEqual(self.client.get('/api/v1/admin/announcements/').status_code,200)
        self.client.credentials()
        self.assertEqual(self.client.get('/api/v1/announcements/').data[0]['id'],row.pk)
        self.assertEqual(Notice.objects.filter(kind='announcement').count(),5)

    def test_location_announcement_targets_and_muting(self):
        Preferences.objects.create(user=self.user,country=self.country,city=self.city)
        Preferences.objects.create(user=self.other,country=self.country,city=self.city,announcements=False)
        row = self.announcement(audience='location',country_id=self.country.pk,city_id=self.city.pk)
        self.assertEqual(list(Notice.objects.filter(kind='announcement').values_list('user_id',flat=True)),[self.user.pk])
        self.signin(self.other)
        self.assertEqual(self.client.get('/api/v1/announcements/').data,[])
        self.signin(self.user)
        self.assertEqual(self.client.get('/api/v1/announcements/').data[0]['id'],row.pk)

    def test_follow_fanout_deduplicates_and_ordinary_edits_do_not_repeat(self):
        OrganizerFollow.objects.create(user=self.user,organizer=self.owner)
        CategoryFollow.objects.create(user=self.user,category=self.category)
        item = self.approved()
        self.assertEqual(PendingFollow.objects.filter(user=self.user,event=item).count(),1)
        self.assertEqual(generate_follow_notices(),1)
        self.assertEqual(generate_follow_notices(),0)
        services.edit_item(self.owner,item.pk,{'title':'Updated'})
        services.claim_review(self.mod,item.pk)
        services.decide(self.mod,item.pk,True,'')
        self.assertEqual(generate_follow_notices(),0)
        self.assertEqual(Notice.objects.filter(user=self.user,kind='event.followed').count(),1)

    def test_daily_digest_local_schedule_and_once_per_day(self):
        CategoryFollow.objects.create(user=self.user,category=self.category)
        Preferences.objects.create(user=self.user,follow_delivery='daily',time_zone='Asia/Damascus')
        item = self.approved(starts_at=(timezone.now()+timedelta(days=10)).isoformat())
        local_day = timezone.now().date()+timedelta(days=1)
        before = datetime.combine(local_day,datetime.min.time(),tzinfo=dt_timezone.utc)+timedelta(hours=5,minutes=59)
        self.assertEqual(generate_follow_notices(before),0)
        self.assertEqual(generate_follow_notices(before+timedelta(minutes=1)),1)
        self.assertEqual(generate_follow_notices(before+timedelta(minutes=2)),0)
        self.assertEqual(DigestRun.objects.filter(user=self.user).count(),1)

    def test_reminders_idempotent_expire_and_move_with_reschedule(self):
        item = self.approved(starts_at=(timezone.now()+timedelta(hours=2)).isoformat())
        occurrence = item.occurrences.get()
        reminder = Reminder.objects.create(user=self.user,occurrence=occurrence,offset_minutes=120)
        self.assertEqual(generate_reminders(),1)
        self.assertEqual(generate_reminders(),0)
        Notice.objects.all().delete()
        registration.reschedule(self.owner,occurrence.pk,timezone.now()+timedelta(hours=4),60,'Asia/Damascus')
        self.assertEqual(generate_reminders(),0)
        occurrence.refresh_from_db()
        self.assertEqual(generate_reminders(occurrence.starts_at-timedelta(hours=2)+timedelta(minutes=2)),1)
        reminder.refresh_from_db()
        self.assertEqual(reminder.sent_for_start,occurrence.starts_at)

    def test_muted_reminder_and_removed_reminder_are_suppressed(self):
        item = self.approved(starts_at=(timezone.now()+timedelta(hours=2)).isoformat())
        row = Reminder.objects.create(user=self.user,occurrence=item.occurrences.get(),offset_minutes=120)
        self.device()
        Preferences.objects.create(user=self.user,reminders=False)
        generate_reminders()
        expand_notices()
        self.assertFalse(Delivery.objects.filter(dispatch__notice__kind='reminder').exists())

    def test_delivery_retry_then_success_and_no_duplicate_run(self):
        self.device()
        notice = Notice.objects.create(user=self.user,kind='item.approved')
        expand_notices()
        sender = Mock()
        sender.send.side_effect = PushError('provider_retry',True,120)
        self.assertEqual(send_due(sender),0)
        delivery = Delivery.objects.get(dispatch__notice=notice)
        self.assertEqual(delivery.attempts,1)
        self.assertGreater(delivery.next_attempt_at,timezone.now()+timedelta(seconds=100))
        Delivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
        sender.send.side_effect = None
        self.assertEqual(send_due(sender),1)
        self.assertEqual(send_due(sender),0)
        delivery.refresh_from_db()
        self.assertEqual(delivery.outcome,'accepted')

    def test_invalid_tokens_removed_but_bad_payload_keeps_device(self):
        self.device()
        Notice.objects.create(user=self.user,kind='item.approved')
        expand_notices()
        sender = Mock()
        sender.send.side_effect = PushError('provider_rejected')
        self.assertEqual(send_due(sender),1)
        self.assertEqual(Device.objects.filter(user=self.user).count(),1)
        Notice.objects.create(user=self.user,kind='item.approved')
        expand_notices()
        sender.send.side_effect = PushError('unregistered')
        self.assertEqual(send_due(sender),1)
        self.assertFalse(Device.objects.filter(user=self.user).exists())

    def test_ban_suppresses_existing_queue_and_does_not_replay_after_unban(self):
        self.device()
        notice = Notice.objects.create(user=self.user,kind='item.approved')
        expand_notices()
        set_ban(self.admin,self.user,True,'Reason')
        set_ban(self.admin,self.user,False,'')
        sender = Mock()
        send_due(sender)
        sender.send.assert_not_called()
        self.assertTrue(Dispatch.objects.get(notice=notice).suppressed)
        self.assertFalse(Device.objects.filter(user=self.user).exists())

    def test_essential_push_ignores_optional_mutes_and_uses_silent_local_channel(self):
        device = self.device()
        pref = Preferences.objects.create(user=self.user,reminders=False,announcements=False,followed_events=False,
            quiet_start='22:00',quiet_end='07:00')
        pref.refresh_from_db()
        notice = Notice.objects.create(user=self.user,kind='event.cancelled')
        expand_notices()
        self.assertTrue(Delivery.objects.filter(dispatch__notice=notice).exists())
        now = datetime(2026,10,15,20,tzinfo=dt_timezone.utc)
        message = payload(notice,device,pref,now,now+timedelta(hours=1))
        self.assertEqual(message['android']['notification']['channel_id'],'munassiq_silent')
        self.assertEqual(message['data']['silent'],'true')
        self.assertIn('أُلغيت',message['notification']['title'])
        self.assertFalse(quiet_now(pref,now+timedelta(hours=12)))

    def test_export_has_follows_and_device_metadata_but_no_raw_token(self):
        device = self.device()
        CategoryFollow.objects.create(user=self.user,category=self.category)
        response = self.client.get('/api/v1/me/data-export/')
        self.assertEqual(response.status_code,200)
        self.assertNotIn(device.token,str(response.data))
        self.assertEqual(response.data['follows']['category_ids'],[self.category.pk])

    def test_logout_all_suppresses_already_queued_device_delivery(self):
        self.device()
        Notice.objects.create(user=self.user,kind='item.approved')
        expand_notices()
        self.assertEqual(self.post('auth/logout-all').status_code,200)
        sender = Mock()
        send_due(sender)
        sender.send.assert_not_called()
        self.assertEqual(Delivery.objects.get().outcome,'suppressed')

    def test_expired_intents_are_not_sent_and_job_run_recorded(self):
        self.device()
        Notice.objects.create(user=self.user,kind='item.approved',created_at=timezone.now()-timedelta(days=2))
        sender = Mock()
        run(sender)
        sender.send.assert_not_called()
        self.assertTrue(MaintenanceRun.objects.filter(name='notifications.delivery',finished_at__isnull=False).exists())

    def test_fcm_only_unregistered_code_invalidates_token(self):
        sender = Sender.__new__(Sender)
        sender.credentials = SimpleNamespace(valid=True,token='private-oauth-token')
        sender.session = Mock()
        response = Mock(status_code=400,headers={})
        response.json.return_value = {'error':{'details':[{'@type':'type.googleapis.com/google.firebase.fcm.v1.FcmError','errorCode':'INVALID_ARGUMENT'}]}}
        sender.session.post.return_value = response
        with self.assertRaises(PushError) as caught:
            sender.send({'token':'private-device-token'})
        self.assertEqual(caught.exception.code,'provider_rejected')
        response.status_code = 404
        response.json.return_value['error']['details'][0]['errorCode']='UNREGISTERED'
        with self.assertRaises(PushError) as caught:
            sender.send({'token':'private-device-token'})
        self.assertEqual(caught.exception.code,'unregistered')

    def test_announcement_organizer_audience_and_admin_ip_guard(self):
        row = self.announcement(audience='organizers')
        self.assertEqual(list(Notice.objects.filter(kind='announcement').values_list('user_id',flat=True)),[self.owner.pk])
        self.signin(self.owner)
        self.assertEqual(self.client.get('/api/v1/announcements/').data[0]['id'],row.pk)
        self.signin(self.admin)
        with override_settings(ADMIN_IP_RESTRICTION=True,ADMIN_ALLOWED_NETWORKS=['192.0.2.0/24']):
            for path in ['statistics','announcements','app-settings']:
                self.assertEqual(self.client.get('/api/v1/admin/'+path+'/').status_code,403)

    def test_reminder_outage_expiry_and_deleted_reminder_before_retry(self):
        self.device()
        item = self.approved(starts_at=(timezone.now()+timedelta(hours=2)).isoformat())
        occurrence = item.occurrences.get()
        row = Reminder.objects.create(user=self.user,occurrence=occurrence,offset_minutes=240)
        self.assertEqual(generate_reminders(),0)
        row.refresh_from_db()
        self.assertEqual(row.sent_for_start,occurrence.starts_at)
        row.offset_minutes, row.sent_for_start = 120, None
        row.save()
        self.assertEqual(generate_reminders(),1)
        expand_notices()
        row.delete()
        sender = Mock()
        send_due(sender)
        self.assertFalse(Delivery.objects.filter(dispatch__notice__kind='reminder',outcome='accepted').exists())

    def test_zero_minute_reminder_rejected_because_delivery_expires_at_start(self):
        item = self.approved()
        self.signin(self.user)
        response = self.client.put(f'/api/v1/occurrences/{item.occurrences.get().pk}/reminder/',
            {'offset_minutes':0},format='json')
        self.assertEqual(response.status_code,400)

    def test_retry_budget_stops_after_six_attempts(self):
        self.device()
        notice = Notice.objects.create(user=self.user,kind='item.approved')
        expand_notices()
        sender = Mock()
        sender.send.side_effect = PushError('provider_retry',True)
        for _ in range(6):
            Delivery.objects.filter(dispatch__notice=notice).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
            send_due(sender)
        row = Delivery.objects.get(dispatch__notice=notice)
        self.assertEqual(row.attempts,6)
        self.assertIsNotNone(row.completed_at)
        self.assertEqual(send_due(sender),0)

    @override_settings(FCM_ENABLED=False)
    def test_disabled_worker_does_not_consume_queue(self):
        notice = Notice.objects.create(user=self.user,kind='item.approved')
        with self.assertRaises(CommandError):
            call_command('send_notifications')
        self.assertFalse(Dispatch.objects.filter(notice=notice).exists())

    def test_account_deletion_cascades_private_notification_data(self):
        self.device()
        CategoryFollow.objects.create(user=self.user,category=self.category)
        Preferences.objects.create(user=self.user)
        Notice.objects.create(user=self.user,kind='item.approved')
        expand_notices()
        response = self.client.delete('/api/v1/me/',{'password':'secret123'},format='json')
        self.assertEqual(response.status_code,204,response.data)
        self.assertFalse(Device.objects.filter(user_id=self.user.pk).exists())
        self.assertFalse(Notice.objects.filter(user_id=self.user.pk).exists())
