# مُنسِّق / Munassiq — updated project prompt

Updated 2026-10-15. This is the consolidated target specification, including the
user's later decisions. It is **not a claim that all features exist**. Before
continuing, read `docs/handoff.md`, `docs/plan.md`, and `docs/work-log.md`, then
verify the relevant current source. Preserve existing work and Git history.

## Role and working process

Act as a senior full-stack engineer and patient mentor for a beginner. Explain
each step and every command simply. Complete authorized work rather than merely
proposing it. Ask about material ambiguities instead of inventing product rules.

The initial architecture approval stage has already been followed by user
authorization to write code and continue. Do not restart the project or repeat
the initial approval process. Continue these milestones in order:

1. Backend core.
2. Authentication and roles.
3. Events/services/maps/media/registration backend.
4. Notifications, follows, announcements.
5. Web dashboard.
6. Native Android app.

After each milestone explain what exists, how to run/test it, and expected results.
Use Git and commit after milestones. Do not push or publish without authorization.
Read applicable AGENTS.md and work records first. No migration inspection/changes
without an explicit migration request; no test-suite inspection/work without an
explicit test request. The original project explicitly requested migrations,
core unit tests, endpoint integration tests and registration race tests; this
documentation task does not require any such work. Production study/exam code is
not a test suite. No Gradle, builds, compilation or packaging without explicit
permission. Use lightweight production-source checks and report unverified work.
No version changes unless requested. Preserve unrelated edits. Keep remaining
work in the plan and completed work/limits in the log. Source completion does not
mean runtime verification. Do not invent time/token usage figures; if a visible
five-hour allowance reaches 20% remaining, finish the current step and stop.

## Product and stack

Free international app for mental-health professionals, mainly psychiatrists,
possibly psychologists. Dozens of users expected in year one. Arabic primary,
English only other language. Store professional/directory data only: never
patient or clinical data. Only two content types: service points and events/
lectures with registration, reminders and follows. No posts or comments.

The implemented backend choice is **Django + Django REST Framework**, replacing
the original FastAPI/SQLAlchemy/Alembic default. Use Django ORM/migrations,
SQLite initially with an eventual PostgreSQL move kept practical, Argon2 password
hashing and OpenAPI. Server-rendered bilingual RTL dashboard. Android: Kotlin,
Jetpack Compose, MVVM, Room. Plain Linux scripts/systemd, no Docker.

Launch country is Syria (SY), with **all Syrian cities/places** requested. Current
seed contains 10,816 selected GeoNames populated places, not a guarantee of every
real settlement; 756 lack Arabic names. Preserve source/license attribution,
stable source IDs, admin corrections, and additions. Keep multi-country design.

## Roles and permissions

Multiple roles per account: regular user, approved organizer, moderator, admin.
Enforce all permissions on the server. Audit every moderator/admin action.
Guests browse; phone/contact person and registration contact/link need login.
Unverified accounts browse but cannot register or request organizer status.

Regular users register, choose reminders, follow organizers/categories, report,
send feedback and apply for organizer status. Application: name, workplace, short
reason, private photo/PDF credential up to 5 MB. Only moderators/admins may access
credentials; delete after decision; exclude from backups. One open application
per user; rejection allows immediate reapplication. Organizer role gives verified badge.

Organizers create in app and dashboard; new items require approval. Rejection
reason optional; notify owner. Rejected items can be edited/resubmitted. Cancel
or reschedule own events immediately; other edits require approval while the
published revision remains live. Duplicate events as templates, without copying
registrations. Cannot delete or create past events. See own item statuses,
per-event views/registered/waitlist counts; export registrant names/emails as CSV
and PDF from app/dashboard. Cannot message registrants. Can remove a registrant
with a required reason. Removing organizer role keeps published items under
moderator management. Deleting the account keeps published items under moderator
stewardship and removes personal attribution/contact data; remove unpublished
items and account-associated data/registrations. Retain declared organizational
contacts where appropriate.

Moderators approve/reject items, revisions and organizer applications; any
moderator may handle any item. Handle reports by dismissing, hiding, or warning
organizer, without feedback to reporter. Edit/delete/restore any item, manage
categories, read feedback. Cannot manage roles, ban/delete accounts, access
statistics or audit log. Need organizer role to create, including past events
for archive. Archived organizer content is read-only; staff may make audited
corrections to archived details.

Admins have moderator abilities plus roles, ban/delete users, app-wide stats,
audit log, settings, announcements and review unlock. Still need organizer role
to create. Pending review locks show reviewer's name and remain until decision
or admin unlock. First admin via local `bootstrap_admin` command.

Bans block login with reason, retain items/registrations, revoke sessions and
stop all push. Moderators manage affected organizer events/registrants. Banned
waitlisted users retain position but are skipped for promotion until unbanned.

## Accounts/security

Email/password, verification, reset, change password/email in Settings. Delete
never-verified accounts after seven days. Configurable minimum password length
six. Temporary repeated-failure lockout, stricter staff protection, login/upload
rate limits. No CAPTCHA or 2FA. Revocable refresh sessions lasting weeks; logout
all devices. Signup consent to both Terms and Privacy; draft bilingual placeholder
policies editable by admin. Account data download and deletion.

Internet-accessible dashboard staff routes hidden from guests; enforce backend
permissions, strong lockout, optional IP restriction with one config switch.
Secrets in .env, supply .env.example; no hardcoded deployment URLs/secrets.

## Events

Title, description, speaker, topic, category, up to three images; in-person,
online or both, online link; start plus duration and multi-day date range;
optional registration contact/link; optional PDF up to 5 MB downloaded/opened
externally; map-picked place or linked service venue. A service page lists its
upcoming events; retain venue snapshot if the linked service disappears.

Weekly/monthly series. Current implementation uses finite series up to 52
occurrences, skips missing monthly dates and rejects ambiguous/nonexistent DST
recurrence times. Treat these as documented implementation policies, not newly
confirmed user requirements. Store UTC plus event IANA zone. Show event-local
and user-local times. Archive at local midnight after occurrence ends. Archive
read-only for organizers, no registration, lazy lists, search only with archive
filter. Staff corrections permitted as above.

Add to phone calendar; share text plus deep link. Without app, show simple web
event page and APK link. Public organizer name/bio/badge/events. Public category
pages and follows. User-defined per-event reminder offset. My registrations
shows confirmed/waitlisted status. No in-app notification inbox in v1.

## Registration state machine

States: registered, waitlisted, pending_reconfirm, cancelled. Log every transition
and emit appropriate notification. Atomic allocation and race tests for last seat.
One row per account/occurrence. Series signup covers **currently published future
occurrences only**, never silently enrolls in later additions. Warn, do not block,
overlap. Seat limit, optional registration deadline, cancellation cutoff before
start. Full events FIFO waitlist. Promote first eligible waiter automatically
when a seat opens; confirm in-app only. Skip banned users without losing position.
Users cancel until cutoff. Organizer must remove registrations before reducing
capacity below occupied seats. Cancel/delete ends registrations and notifies all;
restoration never restores registrations.

Reschedule normally moves registered users to pending_reconfirm, holding seats.
Deadline is new cutoff with at least 12 hours to respond. Expiry cancels and
promotes waitlist. **Exception approved by user:** allow starts less than 12 hours
away; keep existing seats confirmed and make reconfirmation optional. Do not
reject short-notice reschedules. Waitlisted users stay queued; reminders follow
new start. Pending users can decline within their reconfirmation deadline.

## Service points

Types: clinic/center, contact person/office, or service offered at a place. Fields:
name, type, address, validated international phone, working hours per weekday
with multiple ranges, specialty/category, contact person, up to five photos,
optional numeric approximate price and per-listing currency. Map location/zone.
Quick actions call, external directions, share, copy address. Sort/filter by
name A–Z, category, price and open-now; map with clustered markers. Warn on similar
normalized names at creation; allow proceeding; show duplicate flag to reviewer.

## Content lifecycle

Statuses pending, approved, rejected, pending_changes, hidden, soft_deleted.
Reports never auto-hide. Soft delete three days, staff restore within window,
then scheduled hard-delete row/files. Audit retains metadata only. Reports:
spam, wrong/fake information, other with free text. Scheduled account cleanup,
archiving, reminders, promotion, reconfirmation expiry and deletion must be
idempotent and log runs. Shared files must survive while referenced.

## App behavior

Upcoming events home; short onboarding and organizer guide. Standard country/city
pickers rather than free text. Arabic/English search normalizes alef forms,
diacritics, ta marbuta, ya and spelling variants. OpenStreetMap compatible with
Compose; no GPS/location permission, manual map selection. Profile/service/event
photos validated and resized server-side to about 1 MB, disk storage. Pull refresh
and refresh on opening lists; offline banner, retry and cached data. Cache only
lists/recent items and user's own data.

Settings: notification toggles/quiet hours/follows, Arabic/English, Gregorian/Hijri,
theme, privacy policy/export/delete, feedback, forgot/change password and email.
View-count proposal implemented: one detail view per user/browser per UTC day,
exclude own organizer/staff views, one-day guest cookie, no raw IP retention;
approximate aggregate rather than unique-person analytics.

## Notifications

FCM reminders, moderation decisions, cancellations/reschedules, promotions, new
events from followed organizers/categories (instant or daily digest), admin
announcements. Request OS permission on first reminder/registration. Quiet hours
off by default; notifications still arrive silently within configured hours.
Push text follows app language; emails bilingual Arabic/English.

Admin announcement push plus in-app banner to everyone by default, organizers
only, or country/city segment. Configurable few-per-day admin limit, user mute.
Design bounded retries, invalid-token removal, deduplication and missed-reminder
expiry/recovery; document delivery limitations. Ban must suppress all push.
The server now implements the worker/device/follow/announcement APIs and reminder
generation; Firebase remains disabled until configured, with real phone delivery
unverified. Essential pushes cannot be muted. Approved defaults: digest at 09:00
local, banners seven days, three announcements per admin per UTC day (configurable).
Missed reminders expire one hour after due time or at start, whichever is first;
other occurrence messages expire at start or after 24 hours, whichever is first.

## Android

Native Kotlin/Compose/MVVM/Room; full RTL, Arabic/English resources, Arabic-friendly
font, phone language with Arabic fallback, phone digits, accessibility. Light/dark,
one extensible default color theme, placeholder icon. Minimum Android version
chosen under the original delegated decision is Android 7.0/API 24, using Network
Security Config without a separate Android 6 certificate checker. Direct APK
distribution, in-app update check and install instructions. Android source now
exists in android/; it has not been compiled, packaged or device-tested. Milestone
6 remains in progress; see docs/android.md for source coverage and remaining work.

## Hosting/operations

Home Linux server, static IP, access by IP with self-signed HTTPS, plain run scripts,
systemd startup, daily logs; no Docker. Config-driven URLs/paths for VPS move.
SMTP STARTTLS configurable provider; real provider and delivery not yet verified.
Weekly cron backup of database/images/PDFs to configurable different local folder,
keep last four, exclude credentials; restore/update guide. Backup implementation
does not exist yet. Design restoration so deleted credentials/personal data are
not accidentally resurrected, and verify restore with disposable data.

Android trusts only the intended self-signed certificate using Network Security
Config on Android 7+, or a specific custom verification approach if Android 6
chosen; never trust all certificates. Explain trust/distribution/renewal risks
and easy move to real domain/certificate. Nginx/HTTPS configuration and real
internet deployment are not yet supplied/verified. systemd files are examples,
not installed services.

## Deliverables and acceptance

Source, beginner README for setup/run/backup/restore/update, .env.example,
migrations, run scripts, systemd examples, test instructions. Unit tests for core
logic, at least one integration test per endpoint, every registration transition
and concurrent-seat races. Maintain accurate per-milestone verification limits.
Do not claim production readiness from API tests. See handoff for existing source,
missing work, outstanding decisions and the two-repository Git arrangement.
