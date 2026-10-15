# Handoff for the next conversation or agent

Recorded 2026-10-15. Read this, `../original.propmpt.md`, `plan.md`, `work-log.md`,
and applicable AGENTS.md before work. Verify current source: this records a
snapshot, not an automatic guarantee about subsequent edits.

## Where the project stands

Milestones 1–4 have backend implementations. This is an API development milestone,
not a finished app or production deployment. There is no functional dashboard or
Android app. Next implementation milestone: the web dashboard. Notification
backend setup/policies are in `notifications.md`; real FCM/phone integration is
unverified. The initial handoff was documentation-only; subsequent milestone 4
added source, requested migrations and tests, without builds or deployment.

Historical milestone-3 revisions: root `1e0fd94`, backend `9212104`. Inspect current
Git logs/status for newer milestone-4 commits. Commits are local; do not assume
they exist on a remote.

## Existing source and behavior

| Area | Exists | Important limit |
| --- | --- | --- |
| Backend core | Django/DRF, environment config, health/schema/docs, daily logs, Gunicorn/dev helpers | No real internet deployment checked; Swagger uses CDN assets |
| Accounts | Email/password, Argon2, signup consent, verification/reset/email change, revocable rotating sessions, logout-all, bans/roles, first admin command | Real SMTP/inbox delivery unverified |
| Policies | Versioned bilingual placeholders, API admin editing | Needs owner review and dashboard editor |
| Organizer applications | Private 5 MB credentials, one open request, locks/decision, credential deletion | Backup exclusion strategy not implemented as a backup script |
| Audit | Server-side staff action records and admin read API | No dashboard audit viewer |
| Content | Event/service APIs, reviewed revisions, lock/approval/rejection, hide/delete/restore, duplicate templates/check | No creation/review user interface |
| Registration | Four states, capacity transactions, FIFO promotion, overlap warning, cutoff, series signup, required-reason removal, reschedule/reconfirm | Configured worker attempts push; real delivery unverified |
| Archive/deletion | Local-midnight archive/snapshots, staff corrections, repeatable three-day purge, shared-file preservation | Timers are not installed |
| Files | Validated/resized images, private draft access, PDFs, profile photos | Real phone/external PDF viewer unverified; no malware scanner |
| Directory | Search normalization, hours/open-now, filters, marker API, venues and linked events | No visible map, clustering or device quick actions |
| Locations | Syria seed: 10,816 GeoNames places, stable IDs, searchable picker API, admin corrections | 756 English fallback names; source completeness/quality needs review |
| Organizer tools | Public profile/events API, own items, per-occurrence stats/roster and CSV/PDF export | PDF needs configured Arabic-capable font; client screens missing |
| Reports/feedback | Submit, staff list and report resolution; warning notification intent | No staff interface or delivered warning push |
| Calendar/views/reminders | ICS download, approximate daily view counts, reminder offsets/delivery worker | No phone calendar integration; real delivery unverified |
| Notifications | Devices, preferences, quiet-hour metadata, essential/optional types, follows/digests, announcements/banners, retries, bans, settings/stats APIs | Disabled until Firebase configured; Android channels/receipt behavior missing |
| Operations | .env.example, run scripts, systemd service/timer examples, job run logging | No Nginx/certificate/backup/restore implementation or active services |

Source map:

- `backend/config/`: environment, settings, routing, WSGI; SQLite write transactions
  use IMMEDIATE locking. Runtime path is configurable.
- `backend/accounts/`: models/security/permissions, account endpoints,
  organizer requests, private credentials, account email and cleanup commands.
- `backend/catalog/models.py`: reference locations/categories/currencies, items,
  revisions, occurrences, registrations/transitions, Notice, reports, feedback,
  assets, views, reminders, organizer profiles.
- `backend/catalog/services.py`: creation/revision/review/visibility, recurrence,
  normalization, venue snapshots, service open-now.
- `backend/catalog/registration.py`: allocation/transitions/promotion/cancellation/
  reschedule/reconfirmation/series. Preserve item → occurrence lock order.
- `backend/catalog/maintenance.py`: stewardship/account-deletion integration,
  archive/reconfirm/promotion/purge and file cleanup.
- `backend/catalog/views.py`, `urls.py`, `serializers.py`, `presentation.py`:
  API routes, validation, privacy and response projections. All API paths begin
  `/api/v1/`; route source is authoritative, not invented endpoint names.
- `backend/catalog/files.py`, `exports.py`, `search.py`: media, roster output,
  Arabic/English normalization. `data/` contains locations and attribution.
- `backend/notifications/`: models and APIs for devices/preferences/follows,
  announcements/settings/stats, queue generation, FCM adapter, delivery worker.
  `send_notifications` is the separate minute-by-minute job; see notifications.md.
- `operations/scripts/`: runtime preparation, management/dev/server helpers,
  offline GeoNames converter. `operations/systemd/`: examples only.
- `docs/accounts.md`, `catalog.md`, `locations.md`: detailed existing API behavior.

## Remaining work — implementation checklist

### Milestone 4: backend implemented; integration remains

- [x] Device registration/revocation endpoints and FCM credentials through config.
- [x] Delivery worker consuming Notice intents; record attempts, deduplicate,
  bound retries/backoff, remove expired tokens, handle expired/missed reminders.
- [x] Ensure account bans/deletion suppress delivery, including already queued work.
- [x] Generate due reminder intents idempotently; handle rescheduling/cancellation.
- [x] Organizer/category follow models/APIs, instant new-event delivery and daily
  digest grouping, deduplication when both organizer/category are followed.
- [x] User preferences: optional push types, locale/time zone, quiet hours, digest
  choice, announcement mute; define correct cross-midnight behavior.
- [x] Announcements: audiences, country/city filtering, banner API and expiry,
  configurable daily sending limit, admin authorization and audit.
- [x] App-settings/admin-wide user/event/report statistics endpoints.
- [x] New endpoint/permission/queue tests, suppression/retry/duplicate-run coverage.
- [x] Document notification meaning without inventing guaranteed delivery.
- [ ] Configure real Firebase and verify receipt, channels, foreground/background,
  quiet hours, expired tokens and retries on the actual Android app.

### Milestone 5: web dashboard

- [ ] Arabic/English server-rendered RTL navigation, authentication/session/CSRF
  integration, permission-based tools, error messages and accessibility.
- [ ] Organizer content creation/editing/resubmission, uploads, map picking,
  recurrence, own statuses, cancel/reschedule, roster/removal/CSV/PDF and stats.
- [ ] Moderator queues/locks/decisions, organizer credentials, reports, feedback,
  category management, archived corrections, hide/delete/restore/stewardship.
- [ ] Admin accounts/roles/bans, audit, statistics, settings, policy editing,
  locations, announcement sending and review unlock.
- [ ] Public event fallback/deep-link pages and APK download link, category and
  organizer public pages. Account email-link confirmation page already exists.
- [ ] Check UI localization coverage separately from Django language settings;
  those settings do not prove all existing API errors are translated.

### Milestone 6: Android — entire app remains

- [ ] Choose/document minimum Android version, project structure and dependencies.
- [ ] Compose/MVVM navigation, API/session client and safe token storage, Room
  cache, own-data cleanup on logout/deletion, refresh/offline/retry behavior.
- [ ] Arabic/English strings, RTL, Arabic font, phone digits, accessibility,
  light/dark/extensible palette and placeholder icon.
- [ ] Onboarding, upcoming events, standard country/city pickers, normalized
  search/filter/archive, multi-day/dual-zone event details.
- [ ] Service list/filter/open-now/price, clustered OpenStreetMap, manual picking
  without GPS permission, call/directions/share/copy address.
- [ ] Signup/verification/password/email flows, privacy/export/delete and feedback.
- [ ] Registration/waitlist/reconfirm/cancel/overlap, my registrations/reminders.
- [ ] Organizer content and request uploads, status/review reason, roster exports,
  cancellation/reschedule/template flow and organizer guide.
- [ ] Follow/preferences/quiet hours, context-triggered notification permission,
  FCM token lifecycle, silent quiet-hour delivery and announcement banners.
- [ ] Calendar integration (existing ICS may help), deep links, PDF external open,
  share text, Gregorian/Hijri display settings.
- [ ] APK update metadata/check/install instructions, certificate trust scoped to
  intended server; explain moving to a real domain/certificate.
- [ ] Device/emulator tests and builds only after explicit build permission.

### Operations and final acceptance

- [ ] Reproducible deployment dependency lock/pin after selecting target platform;
  requirements currently use ranges. Do not silently change versions.
- [ ] Nginx static-IP/self-signed HTTPS configuration, certificate creation/renewal
  guide, trusted-proxy checks, firewall/host/origin settings and public deployment.
- [ ] Configure real SMTP, verify bilingual links/expiry and inbox arrival.
- [ ] Configure real FCM and verify delivery/quiet hours/invalid tokens/retries.
- [ ] Weekly cron backup to configured local destination, retain four, SQLite
  consistency plus media/PDF coverage, credential exclusion, private permissions.
- [ ] Restore/update guide and disposable restore drill; design deletion replay
  or retention so restoring a backup does not resurrect deleted private data.
- [ ] Complete beginner README for real deployment, backup/restore, updates, APK
  distribution and recovery; current README explicitly marks these gaps.
- [ ] Review placeholder Terms/Privacy, location accuracy/Arabic labels and credit.
- [ ] Install/customize systemd units only in an explicitly authorized environment;
  no example has been activated here.
- [ ] Validate PostgreSQL portability before claiming it works there; current
  runtime/concurrency checks used SQLite only.
- [ ] Final cross-client permissions/privacy/language/accessibility/end-to-end
  review. Never equate source checks with successful deployment or phone behavior.

## Decisions to preserve and questions still open

Confirmed by user: Syria/all places; keep published items without personal
attribution after account deletion; banned queue position retained but promotion
suspended; organizer removal needs reason; whole-series signup covers published
future occurrences; staff archived corrections; short-notice reschedules retain
confirmed seats with optional reconfirmation. Do not ask these again.

Open or implementation-specific choices requiring review before dependent work:

- External registration link currently informational; does not reserve API seats.
  Clarify intended relationship to in-app registration if changing that behavior.
- After organizer-role removal, may the user immediately apply again? Rejected
  applications already allow immediate reapplication; these are different cases.
- Notification decisions confirmed: essential lifecycle/moderation pushes always
  enabled; digest 09:00 local; banners seven days; three announcements per admin
  per UTC day (configurable). Missed reminder expiry one hour after due, never
  after start; other occurrence pushes expire at start or after 24 hours.
  Quiet hours deliver silently rather than defer; client channel behavior awaits Android.
- Android minimum version remains undecided. Android 7+ is a candidate, not a
  confirmed decision. No Android certificate implementation currently exists.
- Recurrence limit 52, skipping invalid monthly dates and rejecting DST ambiguity
  are current implementation policies; document or discuss before changing them.

## Verification and environment — do not overstate

Milestone-4 full run: 131 tests passed, including the prior registration races and
24 new notification tests. Configuration, migration drift, OpenAPI validation and
lightweight syntax/whitespace checks passed. A subsequent zero-minute reminder
boundary change has its own targeted verification recorded in work-log.md.
This is historical evidence, not a guarantee about later source changes.

Supplied migrations were exercised in temporary databases only. Full Syria seed
in a disposable DB added 10,817 country/place rows; second run added zero. No
production database was migrated/seeded. No actual SMTP, FCM, browser dashboard,
Android, internet HTTPS, installed services or restore were verified. No builds,
compilation, packaging or Gradle ran. Python dependencies were installed using
prebuilt wheels and no bytecode-writing checks.

Local `.venv` exists in this workspace; do not assume it transfers to another
computer. No production `.env`/secrets were created by the agent. Follow README
setup before management commands. Runtime files are ignored by Git. Tests use
`runtime/test.sqlite3`, not the live database. Never put real data there.

## Why there is a submodule, and how to preserve the work

The backend already had its own Git history and origin
`https://github.com/Hjjar-AI/Munassiq-backend.git`. The agent created a root
repository for operations/docs and recorded that existing backend repository as
a submodule, preserving its history rather than folding it into the root.
This was an implementation choice, not a user requirement; it adds complexity
and should have been explained before being introduced.

The root stores a backend commit ID, **not the backend files themselves**. There
are two histories and potentially two sets of uncommitted changes. A normal root
commit does not save backend edits. Existing local files are present; no checkout
or update command is needed merely to continue working here.

Safe read-only checks:

```bash
git status --short
git -C backend status --short
git submodule status
```

These show root changes, backend changes, and the backend revision respectively.
For a milestone, commit backend changes inside backend first, then commit the
updated backend reference plus root docs/operations in root. No remote pushes
have been performed by the agent. **Copy both local repositories and their Git
metadata when moving this workspace**, or arrange authorized publishing of the
backend commits before relying on a clone elsewhere. Cloning the remote alone
may omit unpublished work. Do not use `git submodule update` to replace the
working backend blindly, remove its `.git`, reset, or flatten history to fix this.
If the owner wants one repository, plan a separate history-preserving conversion
and verify a complete copy first. This handoff does not change the Git layout.

## Suggested opening message for a new agent

> Continue Munassiq from this existing workspace. Read original.propmpt.md and
> docs/handoff.md, docs/plan.md and docs/work-log.md first, then verify current
> source and both Git statuses. Backend milestones 1–4 exist; next is milestone
> 5 web dashboard, with real Firebase integration still pending. Preserve confirmed decisions and local
> backend commits. Do not restart, flatten Git, deploy, or run builds. Ask about
> unresolved dependent policies, and follow my current AGENTS.md restrictions.
