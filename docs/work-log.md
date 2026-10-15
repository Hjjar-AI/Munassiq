# Work log
## 2026-10-13 — backend core source
- Started Django/DRF following the recommendation and user instruction to begin code.
- Added environment configuration, UTC storage settings, Arabic/English localization foundation,
  public liveness endpoint, OpenAPI schema/docs, daily rotating logs, runtime preparation,
  development/production run scripts and systemd example.
- Added configuration and core endpoint tests; no database schema or migration actions.
- Product decisions remain pending; no account or content behavior implemented yet.
- Runtime verification pending dependency installation. Source completion is not runtime verification.
- Lightweight checks passed: AST syntax parsing of all 10 Python files and bash syntax checks for both run scripts; no compilation.
- Endpoint tests and server startup were not run: DRF, dotenv and drf-spectacular are missing.
- Milestone commit unavailable: .git is a read-only placeholder, not a usable Git repository.

## Backend core verification
- Installed binary-only backend dependencies in .venv; no builds or compilation.
- Django configuration check and all 7 core tests passed using isolated temporary runtime paths.
- Git initialized after approved sandbox escalation. Core milestone is ready for commit.

## 2026-10-13 — authentication and roles milestone
- Added custom email accounts, Argon2 passwords, current-policy consent, rotating/revocable
  opaque sessions, temporary login lockout, verification/reset/email-change flows,
  own account export/deletion, admin role/ban/delete controls and minimal audit metadata.
- Added private 5 MB image/PDF organizer applications, single-open-request constraint,
  atomic reviewer claims, admin unlock, decisions and post-commit credential deletion.
- Added bilingual email queue, SMTP retry command, repeatable seven-day account cleanup,
  job-run records and optional systemd schedule examples; no real email was sent.
- Supplied requested initial account migration. Tests apply migrations only in temporary
  test databases; no production database was created or altered.
- Django check, migration drift check, OpenAPI validation (warnings fatal), and all
  45 core/account tests passed. After adding the streaming upload size guard, all
  3 affected upload integration tests passed. Shell syntax and whitespace checks passed.
- First run exposed 403/401 mismatch on public credential endpoints; corrected and retested.
- Installed binary-only dependencies, with bytecode writing disabled during checks.
  No builds, packaging, Gradle or explicit compilation ran.
- Real SMTP, HTTPS, scheduled services and Android runtime remain unverified.
  Push decisions and banned-device suppression belong to milestone 4. Content stewardship
  must be added to account deletion before content models become available.
- Preserved pre-existing backend Git history/remote; root records backend as a submodule.
  Milestone commits are local only; no publishing or remote pushes.

## 2026-10-14 — backend content and registration milestone
- Added event/service revisions, review locks, moderation, private attachments, recurring
  occurrences, archive snapshots, search/location APIs, reminders and roster CSV/PDF exports.
- Implemented atomic registration transitions, FIFO eligible promotion, cancellation,
  rescheduling, capacity checks, transition logs and durable notification intents.
- Applied user decisions: short-notice changes retain confirmed seats; banned users keep
  queue positions without promotion; account deletion retains published items without
  personal attribution; organizer removal requires a reason; series signup covers published
  future occurrences; staff may auditably correct archived details.
- Bundled 10,816 Syrian GeoNames populated places with source/license attribution;
  756 names use English fallback. Disposable database import added 10,817 country/place
  records, then zero on repeat. No production database was changed.
- Full run passed 106 core/account/catalog tests, including three concurrent registration
  tests. After the final attachment permission change, three targeted tests passed,
  including one new regression case; the complete 107-test suite was not rerun.
- Django configuration, migration drift, OpenAPI validation, Python AST, shell syntax and
  whitespace checks passed. Requested migrations were exercised in temporary databases.
- Push delivery, dashboard, Android, actual SMTP/HTTPS and scheduled service deployment
  remain unfinished or unverified. No builds, compilation, packaging or Gradle ran.

## 2026-10-15 — continuation handoff
- Filled original.propmpt.md with consolidated requirements and confirmed later
  decisions, distinguishing implementation policies and undecided behavior.
- Added docs/handoff.md with source/status map, detailed missing-feature checklist,
  unresolved questions, historical verification limits and new-agent instructions.
- Explained why the existing backend became a submodule, the two-commit workflow
  and risk of unpublished backend commits being absent from a remote clone.
- Linked handoff from README and plan. Documentation only; no application source,
  migrations, test suite, builds, repository layout or deployment changed.

## 2026-10-15 — notification backend milestone
- Added private session-bound device registration/rotation, user preferences,
  organizer/category follows, first-publication deduplication and local daily digests.
- Added due-reminder generation, FCM HTTP v1 OAuth adapter, durable per-device
  attempts/retries/expiry, invalid-token cleanup and ban/logout suppression.
- Added bilingual segmented announcements/banners, configurable daily admin cap,
  public app settings and audited admin-wide statistics APIs; supplied migrations
  and optional notification service/timer examples, not installed.
- User confirmed essential pushes always enabled; digest 09:00 local, banners
  seven days, three announcements per admin per day (UTC implementation), reminder
  grace one hour bounded by start, other occurrence messages start/24-hour expiry.
- Installed new dependencies as prebuilt wheels only; configuration, migration
  drift and OpenAPI validation passed. Full core/account/catalog/notification run
  passed 131 tests, including 24 notification tests and existing registration races.
- Subsequent source review rejected zero-minute reminders, which cannot deliver
  under the approved expiry rule. Two targeted tests passed (the new boundary and
  existing reminder/reschedule flow); the complete 132-test suite was not rerun.
  Python AST, shell syntax, Markdown links and whitespace checks passed.
  No production database changes, real push, deployment,
  compilation, builds, packaging or Gradle ran. Firebase/Android channel/receipt
  integration, dashboard, backup/restore and Android implementation remain pending.

## 2026-10-15 — web dashboard milestone
- Added server-rendered Arabic/English RTL/LTR browsing/account/organizer/staff
  dashboard, public event/service fallbacks, configured APK links, profiles and
  category event filters. No dashboard model or migration was introduced.
- Added fixed local API dispatch, HttpOnly session cookies/rotation, CSRF-protected
  forms and confirmation pages, private downloads, role/IP guards and no-store
  responses. APIs remain bearer-only; no browser tokens appear in page scripts.
- Added human-readable content forms, local-date conversion, image/PDF handling,
  service hours, searchable country/city choices, duplicate warning confirmation,
  manual OpenStreetMap picker, service clusters and existing-item management.
- Connected review locks/decisions, applications/credentials, reports/feedback,
  rosters/exports, admin users/roles/bans/audit/settings/stats/policies/announcements.
- Fixed evidenced current-policy failure with multiple policy versions; signup
  now rejects consent to an outdated displayed version. Allowed audited reviewer
  attachment uploads for corrections without granting item-creation privileges.
- All 153 tests passed, including 21 dashboard integration/security/workflow cases.
  Configuration/OpenAPI checks passed. Python AST, JavaScript parse-only and
  whitespace checks passed; no builds, compilation, packaging or Gradle ran.
- The final coincident-marker link list and preserving stricter response referrer
  policy received source checks; no browser runtime verification. No supported
  preview/browser tool was available. Layout/RTL/mobile/a11y/maps/share/async file
  UX and complete Arabic server-error copy remain acceptance work. Production
  deployment, real SMTP/FCM, Android and backup/restore remain pending.
