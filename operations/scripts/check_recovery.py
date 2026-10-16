"""Run explicitly requested recovery integration tests in a disposable runtime."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from operations_common import ROOT


def main():
    with tempfile.TemporaryDirectory(prefix='munassiq-recovery-check-') as value:
        runtime = Path(value)
        for name in ('logs', 'media', 'private_credentials'):
            (runtime/name).mkdir(mode=0o700)
        environment = os.environ.copy()
        environment.update(DJANGO_SECRET_KEY=secrets.token_urlsafe(60), DJANGO_DEBUG='true',
            DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1', DJANGO_HTTPS_ONLY='false',
            DJANGO_TRUST_PROXY='false', APP_PUBLIC_URL='http://127.0.0.1:8000',
            APP_RUNTIME_DIR=value, APP_PRIVACY_DIR=str(runtime/'privacy'),
            FCM_ENABLED='false', PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run([sys.executable, '-B', str(ROOT/'backend/manage.py'),
            'test', 'core.tests_operations', '--noinput', '--verbosity', '1'], env=environment, cwd=ROOT)
        if (runtime/'database.sqlite3').exists():
            raise RuntimeError('Unexpected non-test database in disposable test runtime')
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
