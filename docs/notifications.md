# Notification backend

Milestone 4 supplies device/follow/preferences APIs, reminder/digest generation,
FCM delivery/retries, announcements/banners, public app settings and admin-wide
statistics. Android is not implemented; real Firebase delivery is unverified.
There is no notification inbox.

## Setup

After normal README setup:

```bash
.venv/bin/python -B -m pip install --only-binary=:all: --no-compile -r backend/requirements.txt
bash operations/scripts/run_management.sh migrate
```

These install prebuilt libraries and create notification tables. Back up existing
real data before migrations. No production migration was run by the agent.

Enable Cloud Messaging HTTP v1 in your Firebase project and obtain a service
account with permission to send messages. Keep its JSON key outside Git, media,
upload folders and normal data backups, readable only by the service user.
Configure `.env`:

- `FCM_ENABLED=true` (default false).
- `FCM_PROJECT_ID`: your Firebase project ID.
- `FCM_SERVICE_ACCOUNT_FILE`: private service-account JSON path.
- `ANNOUNCEMENTS_PER_ADMIN_PER_DAY=3`: per-admin UTC-day cap.

The adapter follows [Firebase HTTP v1 sending](https://firebase.google.com/docs/cloud-messaging/send/v1-api)
and [error guidance](https://firebase.google.com/docs/cloud-messaging/error-codes).
Only the specific FCM `UNREGISTERED` error deletes a device token, not a generic
invalid-payload error. Credentials, tokens and provider bodies are not logged.

```bash
bash operations/scripts/run_management.sh send_notifications
```

This generates reminders/digests, expands up to 200 intents and attempts up to 20
due deliveries. Disabled FCM refuses to consume work. Run every minute using the
customized notification systemd examples; none is installed automatically. Keep
existing account-email/cleanup/content jobs running too. Batches are deliberately
small; backlogs need repeated runs. Each invocation records a maintenance run.

## API paths

Prefix all paths with `/api/v1/`. All require login except public banners/settings.

| Path | Methods | Purpose |
| --- | --- | --- |
| `me/devices/` | GET, PUT | Private device metadata; register/rotate token |
| `me/devices/<id>/` | DELETE | Remove own device |
| `me/notification-preferences/` | GET, PATCH | Language/zone/location, toggles, quiet hours, instant/daily |
| `me/follows/` | GET | Own organizer/category IDs |
| `me/follows/organizers/<id>/` | PUT, DELETE | Follow/unfollow organizer |
| `me/follows/categories/<id>/` | PUT, DELETE | Follow/unfollow active category |
| `announcements/` | GET | Matching current banners; guests see global banners |
| `admin/announcements/` | GET, POST | Admin history/send |
| `app-settings/` | GET | Public support email, APK URL, bilingual guide |
| `admin/app-settings/` | GET, PATCH | Edit those public values |
| `admin/statistics/` | GET | Users/active/banned, event/service totals, unresolved reports |

Device PUT takes an app-generated UUID `installation_id` and FCM `token`. The
device binds to its login session. Revoked/expired sessions cannot receive later
attempts; refresh rotation preserves that session. Re-register after a new login.
A token transfers to the latest authenticated account, removing old deliveries.
Maximum 20 installations per account. Lists/exports never include raw tokens.
Account export includes preferences/follows/device metadata; deletion removes them.

Preferences initially use account language, Asia/Damascus zone, optional types
enabled and instant follows. Clients must send the actual phone zone. Quiet hours
are off when both fields are null; set both `quiet_start`/`quiet_end`, e.g. `22:00`
and `07:00`. Cross-midnight ranges work. Country/city are explicit selections,
never GPS. Language PATCH updates the account's shared Arabic/English language.

Daily digest: once per local day after 09:00. Events published after that day's
09:00 cutoff wait for tomorrow. New alerts arise only on first publication;
edits/restores do not repeat them. Organizer/category overlap is deduplicated.
Unfollow/hide/cancel/mutes are rechecked before attempts. Digest payload includes
up to 20 eligible event IDs plus total count, without unpublished details.

Essential pushes (registration, cancellation, reschedule, promotion, moderation)
cannot be muted. Reminders, followed events and announcements can be muted;
announcement mute also hides authenticated banners. Announcements require ar/en
title/body and audience `everyone`, `organizers`, or `location` with country and
optional city. Default banner expiry seven days; custom expiry up to 30 days.
Push recipients are selected on creation; banners use current role/location.
Admin endpoints enforce IP restriction and auditing. Statistics include unverified
accounts, exclude soft-deleted items and count series items rather than occurrences.

## Delivery limits

- Reminders expire one hour after their chosen time, never after event start.
  Choose at least one minute before start; zero-minute reminders are rejected.
  Rescheduling moves due time and suppresses stale queued reminders.
- Other occurrence messages expire at start or after 24 hours, whichever is first.
  Announcement pushes additionally respect banner expiry.
- Retry intervals: 1, 2, 4, 8, 16 minutes, up to six attempts and expiry. Provider
  retry delays may extend the intervals. Invalid payloads terminate that delivery.
- Ban suppresses old work and removes devices; unban does not replay old messages.
- Notice/device pairs are unique, but a crash after provider acceptance and before
  commit can cause resend. Android must deduplicate `notice_id`; notification tags
  also replace repeats. No exactly-once delivery guarantee.
- No devices at fanout means no replay for a later installation. Intent/delivery
  history is removed after 30 days; this is not a notification inbox.
- Bounded sends serialize with bans. Messages already accepted/in transit cannot
  be recalled. Provider acceptance does not prove timely arrival or user reading.

Server messages are now **data-only**: title/body/expiry accompany routing IDs and
quiet-hour metadata. Android source selects `munassiq_silent` or `munassiq_default`
at receipt, including delayed/background delivery, and deduplicates `notice_id`.
This avoids FCM auto-display using a stale send-time channel. Real FCM/phone
delivery, OS permission, connectivity, high-priority handling and channel behavior
remain unverified until Android is built and tested. Provider/OS background limits
can still delay/drop data messages; there is no guaranteed reminder delivery.
Admin public settings now include `apk_version_code` (default zero/no update),
paired with the APK URL; set it to the actual released Android version code.
