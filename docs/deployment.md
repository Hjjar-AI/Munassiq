# Home-server deployment — prepare, review, then activate

The intended service account is mhmmd. The actual static IP has not been supplied.
No Nginx config, certificate, production database, system service or firewall was
installed/activated by the implementation work. Scripts render files for review.

## 1. Python and private storage

Follow README's initial setup for your existing database/admin. For a new Python
3.14 Linux environment, backend/requirements-linux-py314.lock.txt pins the versions
already present in the development environment; no versions were changed to create
it. It is a version snapshot, not a cross-platform/hashes lock. To install it in
your chosen environment, use its Python:

```bash
.venv/bin/python -m pip install --only-binary=:all: --no-compile -r backend/requirements-linux-py314.lock.txt
```

This downloads prebuilt dependencies, avoiding local native compilation. If a wheel
is unavailable, stop and report it; do not silently upgrade/downgrade versions.
For another Python/platform, review a separate lock snapshot first. Set exported
APP_VENV_DIR to a personal environment path if you don't use project/.venv;
systemd reads it from .env. Shell launchers select that interpreter, then load .env
through python-dotenv, not by executing .env as shell commands.

Create the backup and privacy folders described in backup-restore.md, then run
prepare_runtime.py with your backend Python. It creates private runtime directories
without opening/changing a database. Keep .env mode 600; generate the secret key
using README's instructions and never commit it.

## 2. Prepare static-IP HTTPS files

Substitute your actual IP for YOUR_STATIC_IP. It is a placeholder, not a command to
run unchanged:

```bash
.venv/bin/python -B operations/scripts/prepare_deployment.py \
  --ip YOUR_STATIC_IP --user mhmmd \
  --privacy /home/mhmmd/.local/share/munassiq/privacy \
  --backups /home/mhmmd/.local/share/munassiq/backups \
  --create-certificate
```

This generates review files under ignored operations/generated/deployment: Nginx,
systemd units with your actual project path, a weekly user-cron line, a non-secret
.env fragment, Android configuration example and an IP-SAN self-signed certificate.
The private key stays mode 600. No existing .env is overwritten, no service starts
and nothing is uploaded. It refuses an existing output folder; use --output for a
new version when preparing renewal or changed settings.

Merge deployment.env.fragment into .env, preserving your secret/SMTP/FCM settings.
In production: debug=false, HTTPS-only=true, trusted local proxy=true, explicit
allowed host and trusted CSRF origin. Gunicorn binds 127.0.0.1; Nginx replaces
X-Real-IP/X-Forwarded-Proto so callers cannot choose their authenticated client IP.
Never expose port 8000 to the internet. Nginx serves only static/APK/assetlinks;
all images/PDFs remain behind the API's permission checks. Credentials and .env
never have a public directory alias.

The self-signed certificate is not publicly trusted. Browsers warn unless users
explicitly trust it; distribute the public PEM/fingerprint through a trusted route.
Never distribute the private key. Android embeds only the public certificate,
scoped to this host. Anyone who installs an unrelated trust certificate could be
misled by an impostor, so check the fingerprint. The certificate is valid 365 days;
plan renewal and an app trust update before it expires. A real domain/publicly
trusted certificate later removes the custom trust requirement by changing config.

## 3. Publish static files and review server configuration

An administrator must create /var/www/munassiq and its static/downloads/.well-known
subfolders writable by mhmmd and readable by Nginx. For example:

```bash
sudo install -d -o mhmmd -g www-data -m 755 /var/www/munassiq /var/www/munassiq/static /var/www/munassiq/downloads /var/www/munassiq/.well-known
```

This changes only those public directories, not home/runtime permissions. After
APP_STATIC_DIR=/var/www/munassiq/static is in .env, collect server assets:

```bash
.venv/bin/python -B backend/manage.py collectstatic --noinput
chmod -R a+rX /var/www/munassiq/static
```

The first copies dashboard CSS/JS into the public static folder; the second makes
only these public assets readable. Do not use this permission command on runtime,
private credentials, keys or the project root.

Copy reviewed generated systemd files to /etc/systemd/system and the reviewed
Nginx configuration to your distribution's sites-available/enabled locations.
If another Nginx site already uses ports 80/443, reconcile that configuration first.
These are deliberate administrator steps, not automatic script side effects.

```bash
.venv/bin/python -B operations/scripts/check_deployment.py --certificate operations/generated/deployment/tls/server.pem
sudo nginx -t
sudo systemd-analyze verify operations/generated/deployment/systemd/*.service operations/generated/deployment/systemd/*.timer
```

These validate paths/security settings, Nginx syntax and unit syntax respectively;
they don't start the app. Also run the existing Django deployment check after
configuring runtime/log directories. Resolve warnings with actual deployment context.

When you approve the reviewed files, use systemctl daemon-reload and enable/start
munassiq.service and the account-cleanup, content-jobs, account-email and notification
timers. Workers are oneshot services started by timers. Their generated User is
mhmmd; private directories remain writable only by that account. ReadWritePaths
includes runtime and the persistent privacy journal. Customize the unit if paths
change. Add the generated backup.cron to mhmmd's crontab without replacing existing
jobs. Nginx access/error logging follows your distribution's normal log rotation;
backend and operations logs are in runtime/logs.

## 4. Network, email and notifications

Allow inbound HTTPS (443), and HTTP (80) only for the supplied HTTPS redirect.
Preserve SSH/admin access before changing firewall rules. On a home router, forward
only the required ports to this server's local address; do not publish Gunicorn,
SQLite, credentials or development servers. IP address stability and ISP restrictions
must be verified from a separate network. No firewall/router changes were made.

SMTP: use your mailbox/provider's authenticated submission server, typically
STARTTLS on 587, with EMAIL_HOST/PORT/USER/PASSWORD/FROM and EMAIL_USE_TLS=true.
Use a provider-specific app password if required. Existing queued bilingual email
workers handle retries; actual verification/reset/change-email inbox delivery and
links still need checking. This does not impose app-account 2FA.

FCM: set FCM_PROJECT_ID/FCM_SERVICE_ACCOUNT_FILE and enable FCM only when the private
JSON exists outside Git/media/backups. Configure the corresponding Android Firebase
project and ignored google-services.json. Verify foreground/background receipts,
quiet hours and token expiry on a real phone. Server/app source cannot establish
real delivery without these credentials/devices.

## 5. Updates and recovery

Before updates: make/verify a backup, stop API and writer timers, record the current
Git revision, and update source. Reinstall dependencies only if the reviewed lock
changes. Apply any explicitly reviewed existing schema-update instructions from
README; this tooling does not generate or apply migrations. Refresh static assets,
validate configuration and resume services. For database recovery use
backup-restore.md: never roll old data into a live server without deletion replay.
Android release/install/update steps are in release.md.

References: Python sqlite3 online backup API, Nginx proxy_set_header documentation
and Android app-signing/website-association documentation were consulted for the
implementation. Disposable generated systemd units passed syntax verification (including this
project path with spaces). Real Nginx parsing, public HTTPS and production acceptance
remain unverified until your configuration and IP are available.
