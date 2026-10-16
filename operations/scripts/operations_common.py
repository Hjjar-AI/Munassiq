"""Shared paths and private, logged operations; no Django setup on import."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))


def configured():
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env', override=False)
    value = Path(os.environ.get('APP_RUNTIME_DIR', 'runtime')).expanduser()
    runtime = value if value.is_absolute() else ROOT/value
    value = Path(os.environ.get('APP_PRIVACY_DIR', str(runtime/'privacy'))).expanduser()
    privacy = value if value.is_absolute() else ROOT/value
    return runtime.resolve(), privacy.resolve()


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def logger(runtime, name):
    folder = runtime/'logs'
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    handler = logging.FileHandler(folder/f'{name}-{day}.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    value = logging.getLogger(name)
    value.setLevel(logging.INFO)
    value.addHandler(handler)
    value.addHandler(logging.StreamHandler())
    return value


@contextmanager
def exclusive(path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
