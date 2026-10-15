# مُنسِّق / Munassiq

A professional directory and event app. Never submit patient or clinical data.

## What is available now

The Django backend core and account/role APIs are implemented. This includes signup,
email verification, password recovery, email changes, revocable sessions, bans,
role management, versioned bilingual policies, account export/deletion, private
organizer applications, review locks and audit records.
Events/services, reviewed revisions, recurrence, registration/waitlists,
rescheduling/reconfirmation, media, search, map-marker data, reports/feedback,
organizer profiles, calendar files and CSV/PDF exports are now implemented too.
The notification backend adds FCM queue/retries, follows, preferences,
announcements/banners, public app settings and admin statistics. Real Firebase
and phone delivery remain unverified. A server-rendered Arabic/English dashboard
now exposes account, organizer, moderation and admin workflows. Android, weekly
backup/restore and production HTTPS deployment remain unfinished. Native Android
source is now in `android/`, but has not been compiled or run; no APK exists.
See [Android setup and first-build handoff](docs/android.md).

## Local setup (Linux, Python 3.10+)

Run each command from the project directory. Development uses your computer only;
do not expose the development server to the internet.

```bash
python3 -m venv .venv
```
Creates an isolated Python environment so dependencies do not affect other programs.

```bash
.venv/bin/python -m pip install --only-binary=:all: --no-compile -r backend/requirements.txt
```
Downloads backend libraries as ready-made packages, without building packages.
The version ranges are not a reproducible lockfile yet. If binary packages are
unavailable for your computer, stop and report that error rather than enabling builds.

```bash
cp .env.example .env
chmod 600 .env
```
Creates private configuration and restricts access to your Linux user.
If `.env` already exists, preserve it and add any missing settings from the example.

```bash
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(64))'
```
Generates a random secret. Paste it after `DJANGO_SECRET_KEY=` in `.env`.
Keep that key private. The example local development settings include
`APP_PUBLIC_URL=http://127.0.0.1:8000`; deployment needs your actual HTTPS origin.

```bash
bash operations/scripts/run_management.sh migrate
```
Creates database tables from the supplied migration records. Back up an existing
database before applying future migrations. The helper creates private runtime
folders first; it does not run migrations unless you explicitly supply `migrate`.

```bash
bash operations/scripts/run_management.sh bootstrap_admin
```
Asks for your first administrator's email, name, and password. Password input is
hidden. It creates a verified admin and placeholder Arabic/English policies, and
refuses to run again if an admin exists. Admin does not automatically receive the
organizer role. Review the placeholder policies before launch.

```bash
bash operations/scripts/run_dev.sh
```
Starts the local development server. Visit:

- `http://127.0.0.1:8000/api/v1/health/`: expect `{"status":"ok","service":"munassiq"}`.
- `http://127.0.0.1:8000/api/v1/docs/`: interactive API documentation.
- `http://127.0.0.1:8000/api/v1/policies/current/`: current bilingual terms/privacy.
- `http://127.0.0.1:8000/dashboard/`: Arabic/English browser dashboard.

The health response proves only that the API answers, not SMTP or push delivery.
Press Ctrl+C to stop. API paths include a trailing slash; use the displayed paths.
The API documentation UI currently uses CDN assets. Dashboard CSS/JavaScript is local.
See [dashboard screens and verification limits](docs/dashboard.md).

## Try accounts using API documentation

1. Open the documentation and expand `POST /api/v1/auth/login/`.
2. Choose **Try it out**, enter your admin email/password, and execute.
3. A successful response contains an access token and a refresh token. Keep both private.
4. Click **Authorize** and paste only the access token to try authorized endpoints.
5. An ordinary signup supplies the current policy ID and `consent: true`, which
   means accepting both displayed Terms and Privacy. The resulting account is unverified.
6. Unverified users cannot apply to become organizers. Verify through the email link.

Access tokens last 15 minutes; refresh sessions last 30 days by default. Refresh
rotates both tokens, making the old pair unusable. Logout revokes the current session;
logout-all, password reset/change and confirmed email changes revoke all sessions.

See [account API notes](docs/accounts.md) for permission and file-handling details.

## Email and account cleanup

Set `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and
`EMAIL_FROM` in `.env` using your SMTP provider's details. The default is SMTP STARTTLS.
No real provider is configured by the example.

```bash
bash operations/scripts/run_management.sh send_account_emails
```
Sends up to 20 queued bilingual messages. Temporary failures schedule retries;
rerun the command after the retry time. Sent message bodies are cleared to avoid
retaining verification/reset link secrets. SMTP acceptance does not prove inbox delivery.
A crash after SMTP acceptance can produce a duplicate email on retry.
Links open a bilingual confirmation page; merely opening a link does not change an account.

```bash
bash operations/scripts/run_management.sh cleanup_accounts
```
Deletes accounts never verified within seven days, expired security records and
old orphaned private files. It is safe to repeat. Existing verified accounts remain.
The scheduled-service examples in `operations/systemd/` process mail each minute
and cleanup hourly; they are not installed or activated automatically.

## Checks and tests

```bash
bash operations/scripts/run_management.sh check
bash operations/scripts/run_management.sh test core accounts catalog notifications dashboard --noinput
```
`check` examines Django configuration. `test` creates and destroys a separate test
database in `runtime/test.sqlite3`, exercising security rules, API endpoints and
real two-connection registration races. Use local debug settings. This named test
file is separate from `runtime/database.sqlite3`; do not use it for real data.
These commands do not build the Android app. Builds, compilation, Gradle and
packaging require separate authorization.

## Try events and services

After installing the updated requirements and configuring `.env`, run:

```bash
bash operations/scripts/run_management.sh migrate
bash operations/scripts/run_management.sh seed_locations
```

The first command applies the new content tables. Use development data for this
milestone; production backup/restore instructions are not ready yet. The second
loads Syria and all 10,816 bundled GeoNames populated places. Rerunning the location
command preserves existing records. See [location data and attribution](docs/locations.md).

Using the API documentation with your admin access token:

1. Create at least one category through `POST /api/v1/categories/`. For a service
   with prices, also create the currencies you want enabled through `/currencies/`.
2. Grant the organizer role to the creating account through the admin role endpoint.
   Admin/moderator status alone never authorizes creation.
3. Create an event or service. Expect `status: pending`; guests should not see it.
4. Sign in as a moderator/admin, claim its review, then submit an approved decision.
   It should now appear in the public event/service list.
5. Sign in as a verified regular user and register for an occurrence. With one seat,
   the first user is `registered`, the next is `waitlisted`. Cancelling the first
   before cutoff should promote the waiting user automatically.
6. Try an organizer edit: expect `pending_changes`, while guests still see the
   previous published version. Approval swaps in the new version.

Dates must include a UTC offset or `Z`; the `time_zone` field uses an IANA name such
as `Asia/Damascus`. Series registration operates on currently open future occurrences.
Choose cities through the searchable `/cities/?country=<id>&q=<name>&page=1` endpoint.

For Arabic-capable PDF exports, set `EXPORT_FONT_PATH` to an installed TrueType font.
The [content guide](docs/catalog.md) explains fields, privacy, state transitions,
exports, archive behavior, files and scheduled jobs.

```bash
bash operations/scripts/run_management.sh run_content_jobs
```

Runs archive, reconfirmation-expiry, promotion and three-day deletion work once.
Notification delivery uses the separate `send_notifications` command after Firebase
configuration; see [notification setup and policies](docs/notifications.md).
The content-job timer examples are not activated automatically.

## Production operation is still pending

`run_server.sh` uses Gunicorn. Configure Nginx and self-signed HTTPS before internet
use; never expose Gunicorn directly. Set debug off, explicit allowed hosts and
trusted CSRF origins, `DJANGO_HTTPS_ONLY=true`, and an HTTPS `APP_PUBLIC_URL`.
With a trusted local reverse proxy, enable `DJANGO_TRUST_PROXY=true`; Nginx must
replace `X-Real-IP` with the actual client address and replace `X-Forwarded-Proto`
with the actual connection scheme. Forwarded addresses from non-loopback peers
are rejected. `ADMIN_IP_RESTRICTION` checks that validated address.

Customize the systemd examples' user, project path, and runtime permissions before
installation. If `APP_RUNTIME_DIR` changes, update `ReadWritePaths` in the main unit.
Run scripts use exported `APP_BIND`, or `127.0.0.1:8000`; systemd loads it from `.env`.
Daily UTC log rotation retains 30 rotated files. Background units use separate log names.

## Data, backup, restore and updates

Runtime data is excluded from Git. `APP_RUNTIME_DIR` contains the database, media,
logs, static assets and a separate `private_credentials` folder. Never expose or
back up that credential folder. Documents are deleted after organizer decisions
and account deletion; cleanup retries orphaned files after interrupted deletion.

Weekly backup/restore scripts are not implemented yet. Do not treat these milestone
files as a production-ready deployment. Before replacing source, stop services
and preserve `.env` and runtime data. Follow future migration/backup instructions.
APK install/update instructions will arrive with the Android milestone.

## Work records and Git

For a new conversation or agent, start with [docs/handoff.md](docs/handoff.md)
and the [updated project prompt](original.propmpt.md). The handoff distinguishes
implemented APIs from missing clients/delivery/deployment and explains both Git repositories.

Remaining work is in [docs/plan.md](docs/plan.md); completed work and verification
limits are in [docs/work-log.md](docs/work-log.md).
The existing backend Git repository is preserved and recorded as the root repository's
`backend` submodule. Root operations/docs and backend source have separate milestone
commits. No source was pushed to a remote; new backend commits currently exist locally.

Design references: [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
and [Django REST Framework](https://www.django-rest-framework.org/).
