# مُنسِّق / Munassiq

Professional directory and event app. Never submit patient or clinical data.

## Current scope

Backend core source only: liveness endpoint, OpenAPI, configuration and logs.
Accounts, content, dashboard, worker, Android, backups and restore are future milestones.
Django/DRF is the selected starting assumption after the Django discussion.
No database migrations are needed for the current core endpoints.

## Local setup (Linux, Python 3.10+)

Run these commands from the project directory, one at a time:

```bash
python3 -m venv .venv
```
Creates an isolated Python environment so project dependencies do not affect other programs.

```bash
.venv/bin/python -m pip install -r backend/requirements.txt
```
Downloads and installs the backend libraries. Dependency ranges are not a reproducible lockfile yet.

```bash
cp .env.example .env
chmod 600 .env
```
Creates your private configuration file and restricts access to your Linux user.

```bash
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(64))'
```
Generates a random secret. Paste it after `DJANGO_SECRET_KEY=` in `.env`.
Do not share or commit the resulting key. Keep the example local development values for now.

```bash
bash operations/scripts/run_dev.sh
```
Prepares private runtime directories and starts the local development server.
Open `http://127.0.0.1:8000/api/v1/health/`: expect
`{"status":"ok","service":"munassiq"}`. This proves only that the API can answer,
not that email, database or push delivery works.
Open `/api/v1/docs/` for API documentation; its UI currently loads assets from a CDN.
Press Ctrl+C to stop. The HTTP address here is for local development only.
Run scripts use the exported `APP_BIND` environment variable, or the local default;
other application settings are loaded from `.env`.

## Checks and tests

```bash
.venv/bin/python operations/scripts/prepare_runtime.py
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py test core
```
The first command creates writable directories. `check` checks Django configuration.
`test core` runs configuration and endpoint tests; these tests do not create a database.
Use local debug settings when running them. Run no Gradle/build/packaging commands
without separate authorization.

## Server operation (not internet-ready yet)

`run_server.sh` uses Gunicorn instead of the development server. The systemd example
shows automatic restart and boot startup, but must be customized before installation.
If `APP_RUNTIME_DIR` changes, update systemd `ReadWritePaths` too.
Production requires debug off, explicit allowed hosts, HTTPS and a configured local
reverse proxy. Enable proxy trust only when that proxy strips/replaces forwarded headers.
Do not expose this unfinished foundation as a completed application.
Daily UTC log rotation keeps 30 files. Logs are outside Git.

## Data, backup and restore

`APP_RUNTIME_DIR` contains the future database, public media, logs and a separate
`private_credentials` directory. Credentials must never enter backups.
Backup/restore scripts will be implemented once the schema and file lifecycle exist;
there is currently no production data or usable restore procedure.

## Updating

Stop the service before replacing source. Retain `.env` and runtime data separately.
Dependency upgrades and future schema changes must follow their milestone instructions.
Android APK installation/update instructions will arrive with the Android milestone.

## Design references

- https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- https://www.django-rest-framework.org/
- Remaining work: docs/plan.md; completed work and limits: docs/work-log.md.
