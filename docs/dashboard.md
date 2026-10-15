# Web dashboard

Open `/dashboard/` (or `/`) on the configured server. The default interface is
Arabic with RTL layout; the header switches to English. It is server-rendered
Django HTML with progressive JavaScript, without a frontend build step.

## Local run

After the existing README setup, database migration and first-admin bootstrap:

```bash
bash operations/scripts/run_dev.sh
```

This starts the local development server. Open `http://127.0.0.1:8000/dashboard/`.
Keep debug mode local; production needs the pending HTTPS/Nginx deployment work.
The development server serves the bundled CSS/JavaScript. Production must serve
the collected static directory through the reverse proxy; that deployment is
not configured or verified yet.

```bash
bash operations/scripts/run_management.sh test core accounts catalog notifications dashboard --noinput
```

This runs isolated tests and does not launch a browser or compile/build assets.

## Screens and expected behavior

- Guests: upcoming events, service directory, filters/archive, categories, service
  map, event/venue/organizer pages, public policies and signup/login/recovery.
  Protected contacts remain hidden until login.
- Accounts: profile/password/email, organizer application with private credential,
  application statuses, preferences/quiet hours, followed organizers/categories,
  own devices, feedback, data download, account deletion, logout/all devices.
- Organizers: My items, event/service creation, image/PDF uploads, multiple daily
  service-hour ranges, standard location choices and manual map picking. Edits
  await review while the live version remains visible; statuses/reasons appear
  in My items. Duplicate-event forms require a new start. Similar service names
  require an explicit confirmation before creating the pending item.
- Event occurrence: registration, calendar download and reminders. Owners see
  registrants, required-reason removal, stats and private CSV/PDF links (including
  separate waiting-list exports). Reschedule/cancel are confirmed actions.
  Moderators see rosters only where the existing API allows stewardship; they
  do not gain statistics access. Past/cancelled/archived occurrences show a
  read-only notice; staff descriptive archive corrections use the review editor.
- Moderators: content queue, reviewer names/locks, claim/decision, all-status
  management list, immediate audited corrections, hide/delete/restore, applications
  and private credential download, reports, feedback, category editing.
- Admins: all moderator tools plus users/roles/bans/deletion, audit, statistics,
  announcements, public settings, policy editing, location corrections/additions
  and review unlock. IP restriction applies to these admin screens.

Give an admin the organizer role if it should create items. Admin/moderator status
alone still does not allow creation. Staff may upload replacement attachments for
audited corrections without an organizer grant; this does not grant item creation.

For a simple acceptance flow: create a one-seat event as organizer; it should say
pending. Claim and approve as staff; it appears publicly. Register two verified
users; one becomes registered and one waitlisted. Cancel the first before cutoff;
the next is promoted. Edit the published title as organizer; the previous title
stays live until approval. Backend push delivery needs separate Firebase setup.

Public fallback URLs `/events/<id>/` and `/services/<id>/` show details without
requiring the Android app. Share uses the browser share sheet or clipboard. Set
the public APK URL through admin app settings to display its download button;
no fake APK link is supplied. Android deep-link handling remains its own milestone.

## Browser security and behavior

The web layer dispatches fixed allowlisted operations into existing REST views
locally; browser parameters never choose an arbitrary API URL. API routes still
accept bearer authentication only, not ambient cookies. Dashboard access/refresh
tokens are HttpOnly, SameSite=Lax and Secure outside local debug. Browser mutation
forms require CSRF, including login/logout; GET confirmation pages do not mutate.
Refresh rotation reuses the existing server sessions; bans/revocations apply to
both clients. No access/refresh tokens are placed in HTML or JavaScript storage.

Credential/media/export downloads reuse API permissions. Dashboard responses
are not cached. Templates escape submitted text; policy text is displayed as
text, not trusted HTML. Signup submits the displayed policy version and rejects
stale consent if an admin publishes a new version in the meantime. Some API
validation detail remains in its existing server language (often English); full
Arabic error-copy review remains part of localization acceptance.

Photo/PDF selection uploads files individually with CSRF when JavaScript is
enabled, avoiding one large multi-file request. Save the form to attach uploaded
files; abandoned uploads are cleaned by existing jobs. Without JavaScript,
ordinary multipart forms still work within the existing combined upload limit
of 5 MB. Unchecking current images removes them from the submitted revision;
removing a PDF has a separate checkbox. File limits/types still apply server-side.

Local event times are converted using the selected IANA zone, rejecting ambiguous
or nonexistent DST times. Date precision is preserved when editing existing API
content. Public detail cards show event-local dates and browser-local dates;
browser date formatting follows the phone/computer locale.

## Maps and verification limits

Set `MAP_TILE_URL` in `.env`; the example uses the standard OpenStreetMap tile
template. Map tile requests are made by the browser, not a server-side proxy.
Keep OpenStreetMap attribution visible and respect the chosen provider's policy.
There is no GPS/location permission. Use zoom/pan buttons and click to choose a
place, or enter coordinates directly. Service markers cluster by screen grid;
click a cluster to zoom or an individual marker to open its service. City lookup
is name-searchable and uses the paginated location API (first 50 matching choices).
Refine a city search to reach names outside that first page. GeoNames credit is
shown in the footer.

Server integration tests exercise rendered HTML, form submissions, permissions,
CSRF, cookies/refresh, multipart credentials/media, exports and workflow behavior.
No supported browser-preview tool was available: layout, map tile requests,
interactive clustering, clipboard/share, screen readers and actual mobile browser
behavior have not been visually/runtime verified. No builds, compilation,
packaging, production services or public deployment ran.
