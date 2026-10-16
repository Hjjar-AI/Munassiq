"""Durable, PII-free deletion intents for safe restoration of older backups.

An intent is synced before deletion. A rolled-back deletion can therefore still
be replayed conservatively during recovery. Never delete/truncate this journal.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import uuid

_replaying = ContextVar('privacy_replay', default=False)


@contextmanager
def replaying():
    token = _replaying.set(True)
    try:
        yield
    finally:
        _replaying.reset(token)


@contextmanager
def journal(directory=None):
    if directory is None:
        from django.conf import settings
        directory = settings.PRIVACY_JOURNAL_DIR
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink():
        raise OSError('Privacy journal directory must not be a symlink')
    descriptor = os.open(directory/'deletions.jsonl', os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        info = os.fstat(stream.fileno())
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise OSError('Privacy journal must be owned by the service account with mode 600')
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write((json.dumps({'format': 1, 'instance': str(uuid.uuid4())})+'\n').encode())
            stream.flush()
            os.fsync(stream.fileno())
            parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        yield stream


def record_deletion(kind, obj):
    if _replaying.get():
        return
    if kind not in {'user', 'item'} or not obj.pk:
        raise ValueError('Unsupported privacy intent')
    row = {'kind': kind, 'pk': obj.pk, 'created_at': obj.created_at.isoformat(),
        'requested_at': datetime.now(timezone.utc).isoformat()}
    with journal() as stream:
        stream.seek(0)
        parse(stream.read())
        stream.write((json.dumps(row, separators=(',', ':'))+'\n').encode())
        stream.flush()
        os.fsync(stream.fileno())


def snapshot(directory):
    with journal(directory) as stream:
        stream.seek(0)
        content = stream.read()
    records = parse(content)
    return content, {'instance': records[0]['instance'], 'bytes': len(content),
        'sha256': hashlib.sha256(content).hexdigest()}


def parse(content):
    if not content.endswith(b'\n'):
        raise ValueError('Incomplete privacy journal; do not restore until repaired')
    records = [json.loads(line) for line in content.splitlines()]
    if not records or records[0].get('format') != 1:
        raise ValueError('Invalid privacy journal format')
    uuid.UUID(records[0]['instance'])
    for row in records[1:]:
        if row.get('kind') not in {'user', 'item'} or type(row.get('pk')) is not int or row['pk'] < 1:
            raise ValueError('Invalid privacy deletion intent')
        datetime.fromisoformat(row['created_at'])
    return records


def verify_current(directory, marker):
    path = Path(directory)/'deletions.jsonl'
    if not path.is_file():
        raise ValueError('The current privacy journal is required; a backup cannot replace it')
    content, current = snapshot(directory)
    length = marker['bytes']
    if (type(length) is not int or length < 1 or len(content) < length
            or current['instance'] != marker['instance']
            or hashlib.sha256(content[:length]).hexdigest() != marker['sha256']):
        raise ValueError('Journal is truncated or belongs to a different server instance')
    return parse(content)[1:]
