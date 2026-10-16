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

## 2026-10-15 — Android source / first-build checkpoint (milestone 6 in progress)
- Added a root-tracked native Kotlin/Compose/MVVM/Room project (no new submodule),
  API-24 minimum, candidate pinned toolchain, Arabic/English resources, RTL/theme/
  calendar settings, onboarding and placeholder vector icon. No app APK exists.
- Added HTTPS/bearer refresh client, Android-Keystore session encryption, bounded
  account-scoped recent cache, logout cleanup, native browsing/filter/details,
  registration/reminders, organizer forms/uploads/roster/export and account settings.
- Added Compose manual OSM picker/marker grouping, calendar/share/file-provider
  actions, FCM device sync/receipt source, contextual notification permission,
  local quiet-hour checks, deduplication/expiry and update metadata handling.
- Added text-only deployment preparation for a configured HTTPS host/public PEM,
  scoped Network Security Config and source/resource checking instructions.
- Extended server app settings with APK version code and migration; changed FCM
  payloads to data-only title/body/expiry plus item-kind routing for receipt-time
  quiet handling. Full backend run passed 155 tests; config/OpenAPI checks passed.
- Android XML, matching 233 Arabic/English resource keys, literal references,
  no-location-permission/disabled-backup checks and disposable public-CA/self-signed
  text preparation checks passed. No Gradle, dependency resolution, compilation,
  native tests, device/emulator, TLS handshake, APK packaging or deployment ran.
- docs/android.md records exact source coverage, first-build setup and acceptance
  gaps, including staff tools staying browser-based, verified App Links/signing,
  native validation/gallery/a11y/map/picker/UI work and real FCM/TLS verification.
  Do not mark Android complete or equate backend tests with Android verification.

## 2026-10-15 — user-run build workflow and side-by-side tools
- Read installed tools: Java 21, shared SDK at /opt/android-shared/Sdk, existing
  Gradle 8.7 under the user's wrapper cache; the pinned Gradle 8.13/SDK 35 were absent.
- Began temporary official archive downloads after "continue" to the build question;
  the interrupted job stopped with partial archives only. No Gradle/build ran,
  no tools were installed and no defaults were changed.
- User clarified: tools belong beside existing Android versions, defaults stay
  unchanged, and the user will run builds personally. Recorded this as current
  policy; do not treat earlier build authorization as permission to run it now.
- Added checksum-verified/resumable side-by-side setup script and an explicit-path
  build script. They are supplied for the user's terminal and were not executed.
- Moved the stopped job's partial archives and official checksum/metadata into
  /opt/android-shared/downloads/munassiq, without overwriting existing files.
  The user-run installer will resume/verify them; no versions were installed.
- Added a labelled validation configuration that blocks API calls until real IP
  HTTPS settings are supplied. A domain is not required; actual IP/certificate
  remain unspecified. Validation source/resources were checked without a build.

## 2026-10-15 — first user-run Android build correction
- User's Gradle 8.13 build reached KSP, then reported a missing closing brace in
  AppScreen.kt. Closed the FollowsScreen LazyColumn and expanded its nested lambdas
  so each scope is visible. No dependency or version changes.
- Lightweight resource/source checks passed; no agent-run Gradle, compilation,
  packaging or tests. Compilation and APK creation await the user's next build.

## 2026-10-15 — successful user build and nullable-value warnings
- User reported assembleDebug BUILD SUCCESSFUL after the brace correction.
  This verifies validation APK compilation/packaging, not server/device behavior.
- Fixed the three reported warnings: nullable JSON form values and absent roles
  arrays now use safe calls with empty-string fallbacks instead of direct calls.
- Resource/source checks and diff whitespace checks passed. No Gradle, compilation
  or tests run by the agent; warning-free compilation awaits the user's rebuild.

## 2026-10-16 — shared Android tools organization
- User confirmed the corrected validation build succeeded; device/server acceptance
  remains pending.
- Grouped the five existing download archives/checksum/metadata files under
  /opt/android-shared/downloads/gradle and downloads/android-sdk. Verified SHA-256
  before and after each move; removed the now-empty downloads/munassiq folder.
- Updated the installer to use these tool-specific directories, with legacy archive
  reuse. Preserved installed tools, SDK structure, versions, caches, defaults and
  unrelated /opt applications. Documented the layout in docs/android.md.
- Python syntax/help and diff checks passed; no downloads, builds or tests ran.

## 2026-10-16 — multi-account access inspection
- Host inspection confirms mhmmd/work already share android-dev, developer and
  pnpm-users groups. Sandbox nobody/nogroup mappings were misleading: the shared
  Gradle daemon directory is owned by work with mode 700, not corrupt ownership.
- Corrected mhmmd .bashrc ANDROID_HOME to /opt/android-shared/Sdk; private backup
  .bashrc.before-android-sdk-fix-20261016 retained. Shell syntax check pending.
- Project Android/build directories belong to mhmmd:mhmmd and are not writable by
  work. Shared tools are readable/executable. No new group or tool version needed.
- Automatic approval review rejected recursive group/ACL changes to android because
  they could expose deployment secrets. No project permissions were changed.
- work home configuration remains inaccessible without authentication. Await exact
  failing command/error and approval of shared-checkout access or separate checkout.
  No Gradle/build/tests ran; no caches were deleted or merged.

## 2026-10-16 — approved shared Android checkout access
- User explicitly approved write sharing between mhmmd/work, including Android
  deployment configuration. Applied developer-group read/write ACLs within android
  only and default directory ACLs for future build files. Verified 1,575 entries.
- Preserved file ownership, system/tool permissions, backend and Git metadata.
  Both users already belong to developer; no group creation/change was needed.
- mhmmd .bashrc syntax check passed. work shell configuration still not inspected;
  use command-scoped GRADLE_USER_HOME=$HOME/.gradle for its build and a home-folder
  log, since the project root is not shared for writing. No Gradle/build was run.

## 2026-10-16 — work account configuration helper
- Direct work home access still denied; sudo requires interactive authentication.
  No attempt made to bypass account isolation or request a password in chat.
- Added configure_android_account.py for work to run itself: backs up .bashrc,
  configures shared SDK and personal Gradle cache in a repeatable managed block.
  Preserves Java/Gradle versions and unrelated settings; refuses root execution.
- Python syntax and diff checks passed; helper not executed against work's private
  settings. User must run it as work. No Gradle/build/tests ran.

## 2026-10-16 — authorized work setup attempt
- User explicitly authorized authenticated account configuration. sudo authentication
  failed once; cancelled the prompt without repeated guesses. work .bashrc was not
  changed and its configuration checks did not run. Existing project ACL fix remains.
- No credential recorded in project files. work can run configure_android_account.py
  directly from its own session, without sudo. No Gradle/build/tests ran.

## 2026-10-16 — five native finishing areas
- Implemented memory-only sampled photo gallery (including profile photos), larger
  view, per-photo removal and event/service upload limits; preserved API file access.
- Added localized structured errors, known account/catalog/registration translations,
  field/status fallbacks, preserved user-authored ban reasons and spoken errors.
- Added native date/time controls, localized digit/decimal normalization, appropriate
  keyboards, exact decimal price serialization and field-labelled parse errors.
- Added paged/searchable city/venue pickers. Verified production backend city array
  responses use X-Next-Page; client adapts that header without changing backend API.
- Added spoken map controls, coordinate selection, accessible places list, retry,
  existing-coordinate initialization and bounded embedded scrolling.
- XML/304 bilingual keys/literal references/manifest and whitespace checks passed.
  No Gradle, builds, compilation, tests or device run. Prior user APK success predates
  these changes. Docs record precise fallback and acceptance limitations.
- User confirmed work account helper ran and SDK/personal-cache outputs are correct.

## 2026-10-16 — both accounts' Bash configuration organization
- Organized /home/mhmmd/.bashrc and /home/work/.bashrc with consistent sections
  for history, terminal/prompt, aliases, completion and installed development tools.
- Replaced old prose comments; preserved disabled options and managed Android
  markers. Exact executable lines and their order are unchanged, verified before
  writing; bash -n passed for both files. No shell startup commands were executed.
- Created private timestamped .bashrc.before-organization-* backups in each home.
  work retains its final personal-cache override; its earlier assignment is labelled
  legacy. No Java/SDK/Gradle versions, PATH behavior, permissions or caches changed.
- Used direct work-account authentication successfully; no credential stored in
  project files. No Gradle, builds, compilation or tests ran.

## 2026-10-16 — HTML-inspired Android design refresh
- Reviewed 17 local Downloads HTML themes; primary inspiration was Material You
  light/dark, One UI spacing and minimal typography. Original files left untouched.
- Added shared native teal/sage theme tokens/shapes/type and dependency-free Canvas
  glyphs, bottom navigation, secondary chips, spacious header/cards, browse intros,
  pill search/collapsible advanced filters, detail heroes and settings sections.
- Preserved prior native finishing edits, APIs, roles and Arabic/English behavior.
  No WebView/sample business data, font downloads or tool/dependency versions added.
- XML/313 bilingual keys/literal references/manifest/whitespace checks passed.
  No Gradle/build/compilation/tests or rendered visual QA; user rebuild and device
  acceptance required. Design rationale and limits recorded in android-design.md.

## 2026-10-16 — consolidate Git into one repository
- User requested fixing the nested/submodule layout after choosing one repository.
- Saved current Android/tooling/docs edits in checkpoint dee7218. Created verified
  full bundles, Git metadata archive and 158-file working snapshot/checksum manifest
  in private ignored .repo-backups/20261016-monorepo before conversion.
- Imported backend main (37f686f) unchanged into archive/backend-main and joined
  histories with an ours-strategy merge plus the exact backend files under backend/.
  Retained the original backend .git in recovery storage; removed the active gitlink,
  .gitmodules and submodule configuration. No histories were rewritten.
- Kept root master and sole active origin=https://github.com/Hjjar-AI/Munassiq.git.
  No network fetch/push, remote deletion or build/test/migration work performed.
- Updated README, handoff, consolidated prompt and Git/recovery guide. Historical
  log entries retain the previous two-repository arrangement as history only.

## 2026-10-16 — user-authorized publication
- User explicitly requested pushes. Fetched origin and verified origin/master was
  an ancestor of the consolidated local branch; no concurrent remote changes needed
  merging. Normal push advanced master from 8824194 to df2a14c, including original
  backend history, and established upstream tracking.
- Recovery snapshots/credentials/runtime/build outputs stayed ignored. No force push,
  old-backend remote changes, deployment or build/test work performed.
- Updated current Git documentation to reflect publication; historical records of
  the conversion remaining local at that time are retained.
