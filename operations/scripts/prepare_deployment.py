"""Render reviewable IP-HTTPS/Nginx/systemd files. Never installs or starts services."""
import argparse
import ipaddress
import os
from pathlib import Path
import pwd
import re
import shlex
import subprocess
from operations_common import ROOT


def quoted(path):
    text = str(path)
    if any(ord(char) < 32 for char in text):
        raise ValueError('Paths must not contain control characters')
    return '"'+text.replace('\\', '\\\\').replace('"', '\\"')+'"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ip', required=True, help='Your actual static IPv4 or IPv6 address')
    parser.add_argument('--user', default='mhmmd')
    parser.add_argument('--output', type=Path, default=ROOT/'operations/generated/deployment')
    parser.add_argument('--runtime', type=Path, default=ROOT/'runtime')
    parser.add_argument('--privacy', type=Path, required=True, help='Persistent journal folder, outside runtime')
    parser.add_argument('--backups', type=Path, required=True, help='Private backup folder, outside runtime')
    parser.add_argument('--public-root', type=Path, default=Path('/var/www/munassiq'))
    parser.add_argument('--venv', type=Path, default=ROOT/'.venv')
    parser.add_argument('--upstream-port', type=int, default=8000)
    parser.add_argument('--create-certificate', action='store_true', help='Generate a new self-signed IP-SAN certificate/key using OpenSSL')
    args = parser.parse_args()
    address = ipaddress.ip_address(args.ip)
    if not re.fullmatch('[a-z_][a-z0-9_-]*', args.user) or not 1024 <= args.upstream_port <= 65535:
        raise SystemExit('Invalid service user or upstream port')
    pwd.getpwnam(args.user)
    os.umask(0o077)
    output = args.output.expanduser().resolve()
    runtime, privacy, backups, public, venv = [path.expanduser().resolve() for path in (args.runtime, args.privacy, args.backups, args.public_root, args.venv)]
    for directory in (privacy, backups, public):
        if directory == runtime or directory.is_relative_to(runtime) or runtime.is_relative_to(directory):
            raise SystemExit('Privacy, backups and public folders must be separate from runtime')
    if privacy == backups or privacy.is_relative_to(backups) or backups.is_relative_to(privacy):
        raise SystemExit('Privacy journal and rotating backups must have separate folders')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output/'tls').mkdir(mode=0o700)
    (output/'systemd').mkdir(mode=0o700)
    pem, key = output/'tls/server.pem', output/'tls/server.key.pem'
    host = f'[{address}]' if address.version == 6 else str(address)
    if args.create_certificate:
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-sha256', '-nodes', '-days', '365',
            '-keyout', str(key), '-out', str(pem), '-subj', '/CN='+str(address),
            '-addext', 'subjectAltName=IP:'+str(address),
            '-addext', 'basicConstraints=critical,CA:TRUE',
            '-addext', 'keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign',
            '-addext', 'extendedKeyUsage=serverAuth'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        key.chmod(0o600)
        pem.chmod(0o644)
    nginx = f'''# Install only after reviewing paths/certificate. Never serve runtime/media directly.
server {{
    listen 80;
    listen [::]:80;
    server_name {address};
    return 301 https://{host}$request_uri;
}}
server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name {address};
    ssl_certificate {quoted(pem)};
    ssl_certificate_key {quoted(key)};
    ssl_protocols TLSv1.2 TLSv1.3;
    server_tokens off;
    client_max_body_size 6m;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy same-origin always;
    location /static/ {{
        alias {quoted(str(public/'static')+'/')};
        autoindex off;
        expires 1h;
    }}
    location = /.well-known/assetlinks.json {{
        root {quoted(public)};
        default_type application/json;
        try_files $uri =404;
    }}
    location = /downloads/munassiq.apk {{
        root {quoted(public)};
        default_type application/vnd.android.package-archive;
        try_files $uri =404;
    }}
    location ~ ^/\\. {{ return 404; }}
    location / {{
        proxy_pass http://127.0.0.1:{args.upstream_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For "";
        proxy_set_header Connection "";
        proxy_read_timeout 60s;
    }}
}}
'''
    (output/'munassiq.nginx.conf').write_text(nginx)
    values = {
        'DJANGO_DEBUG':'false', 'DJANGO_ALLOWED_HOSTS':host,
        'DJANGO_CSRF_TRUSTED_ORIGINS':f'https://{host}', 'DJANGO_HTTPS_ONLY':'true',
        'DJANGO_TRUST_PROXY':'true', 'APP_PUBLIC_URL':f'https://{host}',
        'APP_BIND':f'127.0.0.1:{args.upstream_port}', 'APP_RUNTIME_DIR':str(runtime),
        'APP_PRIVACY_DIR':str(privacy), 'APP_BACKUP_DIR':str(backups), 'BACKUP_KEEP':'4',
        'APP_STATIC_DIR':str(public/'static'), 'APP_VENV_DIR':str(venv)}
    # Merge these non-secret settings into .env; never overwrite existing secrets.
    (output/'deployment.env.fragment').write_text('\n'.join(name+'='+shlex.quote(value) for name,value in values.items())+'\n')
    (output/'android-deployment.properties.example').write_text(
        f'server.origin=https://{host}\nserver.certificate={pem}\nmaps.tiles=\n')
    for template in (ROOT/'operations/systemd').glob('*.example'):
        text = template.read_text().replace('User=munassiq', 'User='+args.user)
        text = text.replace('WorkingDirectory=/absolute/path/munassiq', 'WorkingDirectory='+quoted(ROOT))
        text = text.replace('EnvironmentFile=/absolute/path/munassiq/.env', 'EnvironmentFile='+quoted(ROOT/'.env'))
        text = re.sub(r'ExecStart=/bin/bash /absolute/path/munassiq/(operations/scripts/[^\s]+)([^\n]*)',
            lambda match: 'ExecStart=/bin/bash '+quoted(ROOT/match.group(1))+match.group(2), text)
        text = text.replace('ReadWritePaths=/absolute/path/munassiq/runtime', 'ReadWritePaths='+quoted(runtime)+' '+quoted(privacy))
        (output/'systemd'/template.name.removesuffix('.example')).write_text(text)
    cron = '0 3 * * 0 cd '+shlex.quote(str(ROOT))+' && '+shlex.quote(str(venv/'bin/python'))+' -B operations/scripts/backup_data.py\n'
    (output/'backup.cron').write_text('# User crontab for '+args.user+'; weekly Sunday 03:00 server-local.\n'+cron)
    print(f'Prepared review files in {output}. No .env overwrite, service install/start or build ran.')
    print('Certificate/key created.' if args.create_certificate else 'Certificate/key NOT created; supply them before enabling Nginx.')


if __name__ == '__main__':
    main()
