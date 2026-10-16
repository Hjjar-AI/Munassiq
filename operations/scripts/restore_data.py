"""Verify and restore a backup into a NEW offline runtime, replaying deletion intents."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from operations_common import ROOT, configured, digest, logger
from core.recovery import replaying, verify_current


def extract(archive_path, staging, limit):
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        if len(members) > 100000 or sum(member.size for member in members) > limit:
            raise ValueError('Archive exceeds the configured extraction limit')
        seen = set()
        for member in members:
            path = PurePosixPath(member.name)
            valid = member.name in {'manifest.json', 'database.sqlite3'} or (
                len(path.parts) == 2 and path.parts[0] == 'media' and path.name not in {'.', '..'})
            if not valid or not member.isfile() or member.name in seen or path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe, duplicate or unexpected archive entry')
            seen.add(member.name)
        manifest_member = archive.getmember('manifest.json')
        if manifest_member.size > 8*1024*1024:
            raise ValueError('Manifest is too large')
        manifest = json.load(archive.extractfile(manifest_member))
        if manifest.get('format') != 1 or not isinstance(manifest.get('files'), dict):
            raise ValueError('Unsupported backup format')
        if seen != {'manifest.json', *manifest['files']} or 'database.sqlite3' not in seen:
            raise ValueError('Manifest/archive entries do not match')
        for member in members:
            if member.name == 'manifest.json':
                continue
            target = staging/member.name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open('xb') as output:
                shutil.copyfileobj(source, output)
            if digest(target) != manifest['files'][member.name]:
                raise ValueError('Backup checksum mismatch')
    return manifest


def sanitize(records):
    from django.db import transaction
    from django.utils import timezone
    from accounts.maintenance import delete_user
    from accounts.models import EmailMessage, EmailToken, OrganizerRequest, Session, User
    from catalog.models import Asset, Item, Notice
    from notifications.models import Delivery, Device, Dispatch, PendingFollow
    with replaying(), transaction.atomic():
        for record in records:
            model = User if record['kind'] == 'user' else Item
            obj = model.objects.select_for_update().filter(pk=record['pk'], created_at=datetime.fromisoformat(record['created_at'])).first()
            if obj:
                delete_user(obj) if model is User else obj.delete()
        # Credential files are intentionally not backed up. Applicants can immediately reapply.
        OrganizerRequest.objects.filter(status='pending').update(status='rejected',
            credential_name='', credential_type='', locked=False, reviewer=None,
            decided_at=timezone.now(), decision_reason='Restored without private documents; please reapply. / أُعيدت البيانات دون الوثائق الخاصة؛ يرجى إعادة الطلب.')
        OrganizerRequest.objects.update(credential_name='', credential_type='', locked=False, reviewer=None)
        Item.objects.update(locked=False, reviewer=None)
        Delivery.objects.all().delete()
        Dispatch.objects.all().delete()
        Notice.objects.all().delete()
        Device.objects.all().delete()
        Session.objects.all().delete()
        EmailToken.objects.all().delete()
        EmailMessage.objects.all().delete()
        PendingFollow.objects.all().delete()
        Asset.objects.filter(revisions__isnull=True, organizerprofile__isnull=True).delete()
        from django.conf import settings
        allowed = set(Asset.objects.values_list('name', flat=True))
        for path in Path(settings.MEDIA_ROOT).iterdir():
            if path.name not in allowed:
                path.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--target-runtime', type=Path, required=True, help='Must not exist; never a live runtime')
    parser.add_argument('--journal-dir', type=Path, required=True, help='CURRENT privacy journal; never an old backup copy')
    parser.add_argument('--offline', action='store_true', required=True, help='Confirm API, workers and cron writers are stopped until restored data is reviewed and activated')
    parser.add_argument('--max-bytes', type=int, default=2*1024**3)
    args = parser.parse_args()
    os.umask(0o077)
    current_runtime, _ = configured()
    target = args.target_runtime.expanduser().absolute()
    if target.exists() or target.is_symlink() or target.resolve() == current_runtime:
        raise SystemExit('Refusing existing/live target. Choose a new, empty path.')
    if not target.parent.is_dir():
        raise SystemExit('Target parent directory must already exist')
    if target.parent.stat().st_uid != os.getuid() or target.parent.stat().st_mode & 0o002:
        raise SystemExit('Use a parent folder owned by this account and not world-writable')
    log = logger(current_runtime, 'restore')
    try:
        with tempfile.TemporaryDirectory(prefix='.munassiq-restore-', dir=target.parent) as folder:
            staging = Path(folder)
            manifest = extract(args.archive, staging, args.max_bytes)
            records = verify_current(args.journal_dir, manifest['journal'])
            for name in ('logs', 'media', 'private_credentials', 'static'):
                (staging/name).mkdir(mode=0o700, exist_ok=True)
            with sqlite3.connect(staging/'database.sqlite3') as connection:
                if connection.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                    raise ValueError('Restored SQLite integrity check failed')
            # Configure Django exclusively for the staged DB, never the existing runtime.
            os.environ['APP_RUNTIME_DIR'] = str(staging)
            os.environ['APP_PRIVACY_DIR'] = str(args.journal_dir.resolve())
            os.environ['FCM_ENABLED'] = 'false'
            os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
            import django
            django.setup()
            sanitize(records)
            from django.db import connections
            connections.close_all()
            with sqlite3.connect(staging/'database.sqlite3') as connection:
                connection.execute('VACUUM')
                if connection.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('Restored foreign-key check failed')
            (staging/'RESTORE-REVIEW.txt').write_text(
                'Offline restore. Review before enabling services. All sessions/devices/queued emails and pushes were cleared.\n'
                'Pending organizer credentials must be uploaded again. Keep the existing current privacy journal.\n')
            # No live runtime, .env or service is replaced automatically.
            staging.rename(target)
        log.info('restore.completed deletion_intents=%s target=%s', len(records), target)
        print(f'Restored OFFLINE to {target}; update configuration only after review. No services started.')
    except Exception:
        log.exception('restore.failed')
        raise


if __name__ == '__main__':
    main()
