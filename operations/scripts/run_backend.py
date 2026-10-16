"""Select a backend process using .env without executing .env as shell code."""
import os
from pathlib import Path
import sys
from operations_common import ROOT, configured

runtime, privacy = configured()
os.umask(0o077)
for path in [runtime, privacy, *[runtime/name for name in ('media', 'private_credentials', 'logs', 'static')]]:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
mode, *arguments = sys.argv[1:]
bind = os.environ.get('APP_BIND', '127.0.0.1:8000')
if mode == 'server':
    command = [sys.executable, '-B', '-m', 'gunicorn', '--chdir', str(ROOT/'backend'),
        'config.wsgi:application', '--bind', bind, '--workers', '1', '--access-logfile', '/dev/null', *arguments]
elif mode in {'dev', 'management'}:
    command = [sys.executable, '-B', str(ROOT/'backend/manage.py')]
    command += ['runserver', '--noreload', bind, *arguments] if mode == 'dev' else arguments
else:
    raise SystemExit('Expected server, dev or management mode')
os.chdir(ROOT)
os.execv(sys.executable, command)
