"""Disposable end-to-end checks for the real backup/restore command-line tools."""
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from datetime import timedelta
from django.conf import settings
from django.db import connection, transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from accounts.maintenance import delete_user
from accounts.models import EmailMessage, EmailToken, OrganizerRequest, Session, User
from catalog.maintenance import run_jobs
from catalog.models import Asset, Item, Occurrence, OrganizerProfile, Registration, Revision
from core.recovery import record_deletion, snapshot
from notifications.models import Device


class OperationsRecoveryTests(TransactionTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='munassiq-operations-integration-')
        self.root = Path(self.directory.name)
        self.live = self.root/'live'
        self.privacy = self.root/'privacy'
        self.backups = self.root/'backups'
        for folder in [self.live, self.live/'media', self.live/'private_credentials', self.live/'logs']:
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.override = override_settings(RUNTIME_ROOT=self.live, MEDIA_ROOT=self.live/'media',
            PRIVATE_CREDENTIAL_ROOT=self.live/'private_credentials', PRIVACY_JOURNAL_DIR=self.privacy)
        self.override.enable()
        now = timezone.now()
        self.owner = User.objects.create_user('owner@example.invalid', 'password-fixture', name='Owner', verified_at=now)
        self.applicant = User.objects.create_user('applicant@example.invalid', 'password-fixture', name='Applicant', verified_at=now)
        self.event = Item.objects.create(kind='event', owner=self.owner, status='approved', name='Professional lecture')
        payload = {'title':'Professional lecture', 'contact_scope':'personal', 'phone':'+963111111111',
            'contact_person':'Owner', 'description':'Professional directory fixture'}
        self.revision = Revision.objects.create(item=self.event, author=self.owner, payload=payload)
        self.event.published_revision = self.revision
        self.event.save(update_fields=['published_revision'])
        self.occurrence = Occurrence.objects.create(event=self.event, revision=self.revision,
            starts_at=now+timedelta(days=2), ends_at=now+timedelta(days=2, hours=1),
            time_zone='Asia/Damascus', seat_limit=1)
        Registration.objects.create(user=self.owner, occurrence=self.occurrence, state='registered')
        Registration.objects.create(user=self.applicant, occurrence=self.occurrence, state='waitlisted')
        self.disposable = Item.objects.create(kind='service', owner=self.owner, status='soft_deleted',
            deleted_at=now-timedelta(days=4))
        # Tiny valid PNG from Pillow; backup copies bytes, it does not decode images.
        from PIL import Image
        buffer = io.BytesIO()
        Image.new('RGB', (1, 1), 'green').save(buffer, format='PNG')
        photo = buffer.getvalue()
        asset = Asset.objects.create(owner=self.owner, name='fixture.png', kind='image', content_type='image/png', size=len(photo))
        self.revision.assets.add(asset)
        (self.live/'media'/asset.name).write_bytes(photo)
        avatar = Asset.objects.create(owner=self.owner, name='avatar.png', kind='image', content_type='image/png', size=len(photo))
        OrganizerProfile.objects.create(user=self.owner, photo=avatar)
        (self.live/'media'/avatar.name).write_bytes(photo)
        OrganizerRequest.objects.create(user=self.applicant, name='Applicant', workplace='Directory office',
            reason='Organizer request', credential_name='private-license.pdf', credential_type='application/pdf')
        (self.live/'private_credentials/private-license.pdf').write_bytes(b'PRIVATE-CREDENTIAL-FIXTURE')
        session = Session.objects.create(user=self.owner, access_hash='a'*64, refresh_hash='b'*64,
            access_expires_at=now+timedelta(minutes=15), expires_at=now+timedelta(days=30))
        Device.objects.create(user=self.owner, session=session, token='fixture-device-secret', token_hash='c'*64,
            installation_id='00000000-0000-0000-0000-000000000001')
        EmailToken.objects.create(user=self.owner, token_hash='d'*64, purpose='reset', expires_at=now+timedelta(hours=1))
        EmailMessage.objects.create(user=self.owner, recipient=self.owner.email, subject='Fixture',
            body='fixture-email-secret', expires_at=now+timedelta(hours=1))
        connection.ensure_connection()
        with sqlite3.connect(connection.settings_dict['NAME']) as source, sqlite3.connect(self.live/'database.sqlite3') as target:
            source.backup(target)
        self.env = os.environ.copy()
        self.env.update(APP_RUNTIME_DIR=str(self.live), APP_PRIVACY_DIR=str(self.privacy),
            APP_BACKUP_DIR=str(self.backups), BACKUP_KEEP='4', FCM_ENABLED='false', PYTHONDONTWRITEBYTECODE='1')

    def tearDown(self):
        self.override.disable()
        self.directory.cleanup()
        super().tearDown()

    def command(self, name, *args, success=True):
        result = subprocess.run([sys.executable, '-B', str(settings.PROJECT_ROOT/'operations/scripts'/name), *map(str,args)],
            env=self.env, capture_output=True, text=True, timeout=60)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout+'\n'+result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def backup(self):
        self.command('backup_data.py')
        return sorted(self.backups.glob('munassiq-*.tar.gz'))[-1]

    def restore(self, archive, target=None, journal=None, success=True):
        target = target or self.root/'restored'
        return self.command('restore_data.py','--archive',archive,'--target-runtime',target,
            '--journal-dir',journal or self.privacy,'--offline',success=success)

    def test_backup_exclusions_integrity_and_four_archive_retention(self):
        archives = [self.backup() for _ in range(5)]
        self.assertEqual(len(list(self.backups.glob('munassiq-*.tar.gz'))), 4)
        self.assertFalse(archives[0].exists())
        with tarfile.open(archives[-1], 'r:gz') as archive:
            names = set(archive.getnames())
            self.assertEqual(names, {'manifest.json','database.sqlite3','media/fixture.png','media/avatar.png'})
            manifest = json.load(archive.extractfile('manifest.json'))
            self.assertEqual(manifest['format'], 1)
            database = self.root/'snapshot.sqlite3'
            database.write_bytes(archive.extractfile('database.sqlite3').read())
        with sqlite3.connect(database) as database_connection:
            self.assertEqual(database_connection.execute('PRAGMA integrity_check').fetchone(), ('ok',))
            for table in ['accounts_session','accounts_emailtoken','accounts_emailmessage','notifications_device']:
                self.assertEqual(database_connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 0)
            self.assertEqual(database_connection.execute('SELECT credential_name,credential_type FROM accounts_organizerrequest').fetchone(), ('',''))
        content = database.read_bytes()
        self.assertNotIn(b'fixture-device-secret', content)
        self.assertNotIn(b'fixture-email-secret', content)
        self.assertNotIn(b'private-license.pdf', content)
        self.assertTrue((self.live/'private_credentials/private-license.pdf').exists())

    def test_restore_replays_real_deletions_preserves_stewardship_and_rejects_missing_credentials(self):
        archive = self.backup()
        owner_id, item_id = self.owner.pk, self.disposable.pk
        record_deletion('user', self.owner)  # Duplicate intents are safe to replay.
        with transaction.atomic():
            delete_user(self.owner)
        run_jobs()
        self.assertFalse(User.objects.filter(pk=owner_id).exists())
        self.assertFalse(Item.objects.filter(pk=item_id).exists())
        self.restore(archive)
        with sqlite3.connect(self.root/'restored/database.sqlite3') as restored:
            self.assertEqual(restored.execute('SELECT COUNT(*) FROM accounts_user WHERE id=?',(owner_id,)).fetchone()[0], 0)
            self.assertEqual(restored.execute('SELECT COUNT(*) FROM catalog_item WHERE id=?',(item_id,)).fetchone()[0], 0)
            self.assertIsNone(restored.execute('SELECT owner_id FROM catalog_item WHERE id=?',(self.event.pk,)).fetchone()[0])
            payload = json.loads(restored.execute('SELECT payload FROM catalog_revision WHERE id=?',(self.revision.pk,)).fetchone()[0])
            self.assertEqual(payload['phone'], '')
            self.assertEqual(payload['contact_person'], '')
            self.assertEqual(restored.execute('SELECT state FROM catalog_registration WHERE user_id=?',(self.applicant.pk,)).fetchone()[0], 'registered')
            status, reason = restored.execute('SELECT status,decision_reason FROM accounts_organizerrequest').fetchone()
            self.assertEqual(status, 'rejected')
            self.assertIn('يرجى', reason)
            self.assertIsNone(restored.execute('PRAGMA foreign_key_check').fetchone())
        self.assertFalse((self.root/'restored/media/avatar.png').exists())
        self.assertTrue((self.root/'restored/media/fixture.png').exists())
        self.assertEqual(list((self.root/'restored/private_credentials').iterdir()), [])
        self.assertNotIn(b'owner@example.invalid', (self.root/'restored/database.sqlite3').read_bytes())
        # The source snapshot was not overwritten by restoration.
        with sqlite3.connect(self.live/'database.sqlite3') as original:
            self.assertEqual(original.execute('SELECT COUNT(*) FROM accounts_user WHERE id=?',(owner_id,)).fetchone()[0], 1)

    def test_restore_refuses_existing_target_without_touching_it(self):
        archive = self.backup()
        target = self.root/'restored'
        target.mkdir()
        marker = target/'keep.txt'
        marker.write_text('untouched')
        self.restore(archive, target=target, success=False)
        self.assertEqual(marker.read_text(), 'untouched')

    def test_restore_requires_current_matching_journal(self):
        archive = self.backup()
        self.restore(archive,journal=self.root/'missing-journal',success=False)
        other = self.root/'other-journal'
        snapshot(other)
        self.restore(archive,journal=other,success=False)
        self.assertFalse((self.root/'restored').exists())

    def test_restore_refuses_traversal_and_checksum_tampering(self):
        original = self.backup()
        for attack in ('traversal','checksum'):
            modified = self.root/(attack+'.tar.gz')
            with tarfile.open(original, 'r:gz') as source, tarfile.open(modified, 'w:gz') as destination:
                for member in source:
                    data = source.extractfile(member).read()
                    if attack == 'checksum' and member.name == 'media/fixture.png':
                        data = b'changed-media'
                    member.size = len(data)
                    destination.addfile(member, io.BytesIO(data))
                if attack == 'traversal':
                    member = tarfile.TarInfo('../escaped-file')
                    member.size = 1
                    destination.addfile(member, io.BytesIO(b'x'))
            self.restore(modified, success=False)
        self.assertFalse((self.root/'escaped-file').exists())
        self.assertFalse((self.root/'restored').exists())

    def test_unreadable_journal_blocks_deletion_before_any_account_changes(self):
        self.backup()
        path = self.privacy/'deletions.jsonl'
        path.chmod(0o644)
        owner_id = self.owner.pk
        with self.assertRaises(OSError), transaction.atomic():
            delete_user(self.owner)
        self.assertTrue(User.objects.filter(pk=owner_id).exists())
        self.event.refresh_from_db()
        self.assertEqual(self.event.owner_id, owner_id)
        path.chmod(0o600)
