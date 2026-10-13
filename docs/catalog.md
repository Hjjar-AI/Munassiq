# Content and registration milestone

## What the backend provides

Only events and service points are publishable content. Organizers create them
as pending submissions. Moderators claim a review and approve/reject it; another
reviewer cannot decide while the lock is held. Admins can unlock it. Organizer
PATCH requests create replacement revisions, preserving the live published version.
PATCH supports partial fields. Rejected submissions can be edited/resubmitted.
Moderator edits are immediate and audited. Organizers cannot delete items.

Guests receive published information with phone, contact person and registration
contact/link omitted. Login reveals those fields; verified email is required for
registration. Online meeting URLs are event information. External registration
links are stored as informational links and do not allocate seats in this API.

Services validate international phone numbers (including Arabic-digit input),
map coordinates, categories, optional amount/currency pairs, and non-overlapping
working-hour ranges. Overnight ranges use the service's zone. Price sorting
requires one currency. Similar normalized names warn without blocking submission.
The map endpoint supplies paginated marker data; map rendering/clustering is a
client feature for the dashboard/Android milestones.

Events support weekly/monthly finite series, up to 52 occurrences. Monthly dates
missing in a month are skipped. Recurrence in an ambiguous/nonexistent DST clock
time is rejected instead of silently choosing a time. UTC storage and IANA zones
produce both event-local and requested user-local dates. Multi-day duration and
series date ranges are included. Archive visibility begins at local midnight after
an occurrence ends, even if the job has not run. `archive=true` includes archived
occurrences; `archived_only=true` selects them. Lists/search are paginated.
Archived snapshots survive ordinary future-series edits. Staff may correct archived
content through audited moderator edits; organizers cannot. Archived rescheduling
and new registration remain unavailable.

An event can use a published service venue. Reviewed address/map snapshots remain
available if the service disappears; its live link is removed from public output.
The service's events endpoint lists upcoming linked events. Event duplication
requires a new start and produces a new pending item, with no copied registrations.

## Registration behavior

States: registered, waitlisted, pending_reconfirm, cancelled. One row per user and
occurrence; rejoining a cancelled row assigns a new queue time. Database transactions
allocate seats and log transitions together with durable notification intents.
Pending reconfirmation holds a seat. Eligible waitlisted users are promoted in
queue order; banned users keep their original position but are skipped until unbanned.
Overlap warns without blocking, including whole-series signup. Whole-series signup
covers currently published, still-open future occurrences; it does not enroll users
in later additions. Capacity proposals are checked again at approval time.

User cancellation closes at the cutoff. Pending-reconfirm users may decline until
their reconfirmation deadline. Authorized organizer removals require a reason;
moderators manage registrants when the owner is banned, loses organizer status or
is deleted. Admins can manage any roster. Moderators do not gain statistics access.

Normal rescheduling requires reconfirmation by the new cutoff, extended to at least
12 hours after the change when needed. Short-notice changes with less than 12 hours
before start preserve confirmed seats; confirmation is optional, per your decision.
Waitlisted users remain queued. Reminder offsets follow the new occurrence start.
Expired mandatory confirmations cancel registrations and release seats.
Cancelling/deleting an event cancels every active registration with a notification
intent. Restoration reopens an eligible occurrence but never restores registrations.

## Files, exports and scheduled work

Images accept JPEG/PNG/WEBP, apply orientation, strip metadata and resize to at most
1 MB. Uploads are limited to 5 MB while streaming. Events allow three images and an
optional PDF; services allow five images. PDFs must parse and be unencrypted.
Private drafts' files require ownership or staff authority. Credentials remain in
the separate account-only private folder and are never exposed by these endpoints.

Registrant CSV/PDF exports contain names and emails only; default selection is
registered/pending_reconfirm. `state=waitlisted` exports the waiting list separately.
CSV protects against spreadsheet formula injection; PDF shapes Arabic text using
an operator-configured Arabic-capable font. Set `EXPORT_FONT_PATH` in `.env`, for
example `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` if installed on your Linux
computer. Missing font configuration returns an unavailable response. Exports are
private and are not cached. PDF layout was exercised by tests; installed external
PDF viewers and real phones remain unverified.

Event views count one detail view per user/browser per UTC day, excluding organizers'
own views and staff. Guest deduplication uses a one-day cookie, with no stored raw IP.
Short-lived fingerprints are purged; aggregate totals remain. This is an approximate
view measure, not an exact count of distinct people.

```bash
bash operations/scripts/run_management.sh run_content_jobs
```

This archives eligible occurrences, expires reconfirmations, promotes waitlists and
hard-deletes items three days after soft deletion. It also cleans unreferenced media
without removing files shared by surviving items. It records each run and is safe
to repeat. The systemd timer examples run it each minute after operator installation.
They are not installed or activated automatically.

Account deletion removes account-associated registrations/data, releases seats, and
transfers published items to moderator stewardship. Revision authors and personal
contact fields are cleared; declared organizational contact remains. Unpublished
items are removed. Account export includes owned revision payloads, registrations,
reminders, reports/feedback, profile and uploaded-media metadata; credentials and
security secrets are excluded.

Notification intents are not delivered as push yet. Reminder delivery, follows,
announcements and FCM retries are the next milestone. Web share/fallback pages and
APK links arrive with the dashboard/Android milestones. No production HTTPS, real
SMTP/FCM, scheduled service installation or Android runtime has been verified.
