"""Check deployment configuration/paths without starting services or opening a DB."""
import argparse
import ipaddress
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit
from operations_common import ROOT, configured


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--certificate', type=Path, help='Optional public server PEM for OpenSSL host/expiry checks')
    args = parser.parse_args()
    runtime, privacy = configured()
    issues = []
    for key, required in [('DJANGO_DEBUG','false'),('DJANGO_HTTPS_ONLY','true'),('DJANGO_TRUST_PROXY','true')]:
        if os.environ.get(key, '').lower() != required:
            issues.append(f'{key} must be {required} for the supplied Nginx setup')
    if len(os.environ.get('DJANGO_SECRET_KEY', '')) < 50:
        issues.append('A random DJANGO_SECRET_KEY of at least 50 characters is required')
    parsed = urlsplit(os.environ.get('APP_PUBLIC_URL', ''))
    if parsed.scheme != 'https' or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
        issues.append('APP_PUBLIC_URL must be an HTTPS origin')
    allowed = [part.strip() for part in os.environ.get('DJANGO_ALLOWED_HOSTS','').split(',') if part.strip()]
    if not allowed or '*' in allowed:
        issues.append('Explicit DJANGO_ALLOWED_HOSTS are required')
    if os.environ.get('APP_PUBLIC_URL','') not in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS','').split(','):
        issues.append('Add APP_PUBLIC_URL to DJANGO_CSRF_TRUSTED_ORIGINS')
    if not os.environ.get('APP_BIND','').startswith('127.0.0.1:'):
        issues.append('The supplied Nginx configuration requires APP_BIND=127.0.0.1:<port>')
    env = ROOT/'.env'
    if not env.is_file() or stat.S_IMODE(env.stat().st_mode) & 0o077:
        issues.append('.env must exist and be private (chmod 600)')
    backup_value = os.environ.get('APP_BACKUP_DIR')
    for name,path in [('runtime',runtime),('privacy',privacy),('backups',Path(backup_value).expanduser().resolve() if backup_value else None)]:
        if path is None or not path.is_dir() or not os.access(path, os.W_OK):
            issues.append(f'{name} folder must exist and be writable by this account')
        elif stat.S_IMODE(path.stat().st_mode) & 0o077:
            issues.append(f'{name} folder must be private (mode 700)')
    if args.certificate and parsed.hostname:
        import subprocess
        try:
            ipaddress.ip_address(parsed.hostname)
            flag = '-checkip'
        except ValueError:
            flag = '-checkhost'
        result = subprocess.run(['openssl','x509','-in',str(args.certificate),'-noout',flag,parsed.hostname],capture_output=True)
        expiry = subprocess.run(['openssl','x509','-in',str(args.certificate),'-noout','-checkend','2592000'],capture_output=True)
        if result.returncode or b'does match certificate' not in result.stdout or expiry.returncode:
            issues.append('Public certificate does not match the host or expires within 30 days')
    if issues:
        print('\n'.join('- '+issue for issue in issues))
        raise SystemExit(1)
    print('Configuration/path checks passed. Database, network, Nginx syntax, SMTP/FCM and real clients remain unverified.')


if __name__ == '__main__':
    main()
