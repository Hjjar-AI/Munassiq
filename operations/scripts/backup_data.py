"""Online SQLite backup plus referenced media. Excludes private credentials/secrets."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import uuid
from operations_common import ROOT, configured, digest, exclusive, logger
from core.recovery import snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, help='Defaults to APP_BACKUP_DIR')
    args = parser.parse_args()
    os.umask(0o077)
    runtime, privacy = configured()
    log = logger(runtime, 'backup')
    try:
        value = args.destination or os.environ.get('APP_BACKUP_DIR')
        if not value:
            raise ValueError('Set APP_BACKUP_DIR to a separate private backup folder')
        destination = Path(value).expanduser().resolve()
        if destination == runtime or destination.is_relative_to(runtime) or runtime.is_relative_to(destination):
            raise ValueError('Backup destination must be separate from runtime')
        if not (runtime/'database.sqlite3').is_file():
            raise ValueError('No existing SQLite database; nothing was backed up')
        destination.mkdir(mode=0o700, parents=True, exist_ok=True)
        if destination.stat().st_mode & 0o077:
            raise ValueError('Backup folder must be private (mode 700)')
        keep = int(os.environ.get('BACKUP_KEEP', '4'))
        if keep < 1:
            raise ValueError('BACKUP_KEEP must be positive')
        with exclusive(destination/'.backup.lock'), tempfile.TemporaryDirectory(prefix='.backup-', dir=destination) as folder:
            staging = Path(folder)
            database = staging/'database.sqlite3'
            with closing(sqlite3.connect((runtime/'database.sqlite3').as_uri()+'?mode=ro', uri=True, timeout=30)) as source:
                with closing(sqlite3.connect(database)) as target:
                    source.backup(target, pages=256, sleep=.05)
                    if target.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                        raise ValueError('SQLite snapshot integrity check failed')
                    # Never preserve active sessions, bearer/FCM tokens or delivery queues.
                    for table in ('notifications_delivery', 'notifications_dispatch', 'catalog_notice',
                            'notifications_device', 'accounts_session', 'accounts_emailtoken', 'accounts_emailmessage'):
                        target.execute('DELETE FROM '+table)
                    target.execute("UPDATE accounts_organizerrequest SET credential_name='', credential_type=''")
                    names = [row[0] for row in target.execute('SELECT name FROM catalog_asset ORDER BY id')]
                    target.commit()
                    target.execute('VACUUM')  # Purge excluded values from freed pages too.
            (staging/'media').mkdir(mode=0o700)
            for name in names:
                if not name or Path(name).name != name or name in {'.', '..'}:
                    raise ValueError('Unsafe media name in database')
                source = runtime/'media'/name
                if source.is_symlink() or not source.is_file():
                    raise ValueError('Referenced media missing; backup aborted safely. Retry after concurrent cleanup.')
                shutil.copyfile(source, staging/'media'/name)
            _, marker = snapshot(privacy)
            files = {'database.sqlite3': digest(database)}
            files.update({'media/'+name: digest(staging/'media'/name) for name in names})
            revision = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True)
            manifest = {'format': 1, 'source_revision': revision.stdout.strip() if revision.returncode == 0 else 'unknown', 'created_at': datetime.now(timezone.utc).isoformat(),
                'journal': marker, 'files': files}
            (staging/'manifest.json').write_text(json.dumps(manifest, indent=2))
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            final = destination/f'munassiq-{stamp}-{uuid.uuid4().hex[:8]}.tar.gz'
            temporary = staging/'archive.tar.gz'
            with tarfile.open(temporary, 'w:gz') as archive:
                for name in ['manifest.json', *files]:
                    archive.add(staging/name, arcname=name, recursive=False)
            with temporary.open('rb') as stream:
                os.fsync(stream.fileno())
            temporary.rename(final)
            descriptor = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            # Remove only our own older completed archives, after successful publication.
            for old in sorted(destination.glob('munassiq-*.tar.gz'), reverse=True)[keep:]:
                if old.is_file() and not old.is_symlink():
                    old.unlink()
            log.info('backup.completed files=%s retained=%s archive=%s', len(files), keep, final.name)
            print(final)
    except Exception:
        log.exception('backup.failed')
        raise


if __name__ == '__main__':
    main()
