# Android source and first-build handoff

The native app source is in `android/`, tracked by the root Git repository. It is
not another submodule. **No Gradle, dependency resolution, Kotlin compilation,
APK packaging, emulator or device run has occurred. This is not a verified APK.**
The first build must be explicitly authorized under the user's AGENTS.md rules;
fixing compiler/dependency errors and runtime acceptance remains required work.

## Decisions and source layout

Minimum Android 7.0 (API 24) keeps declarative Network Security Config available
and avoids a separate Android 6 trust implementation. Compile/target SDK 35,
JDK 17, Gradle 8.13, AGP 8.11.1, Kotlin/Compose plugin 2.1.20, Compose BOM
2025.04.01, Room 2.7.1 and matching KSP 2.1.20-1.0.32 are the initial candidate
toolchain. These are pinned choices for a new project, not a verified dependency
resolution result or a claim of latest versions. No existing app version was changed.
Initial package/version placeholders are `org.munassiq.app`, code 1, name 0.1.0;
review package/signing identity before the first real distribution.

- `data/SessionVault.kt`: AES-GCM session storage with Android Keystore.
- `data/ApiClient.kt`: HTTPS JSON/multipart/download client, bearer sessions,
  serialized refresh, no redirect forwarding, bounded file handling.
- `data/Cache.kt`, `Repository.kt`: Room response cache scoped by account, bounded
  to 250 recent entries/seven days, mutation invalidation and logout cleanup.
- `ui/AppViewModel.kt`: state/navigation, jobs and existing API actions.
- `ui/AppScreen.kt`, `DetailScreens.kt`, `SettingsScreen.kt`: native Compose lists,
  details/registration, preferences and device actions.
- `ui/NativeForms.kt`, `FormsScreen.kt`: typed native account/organizer forms,
  standard reference pickers, attachments, hours and local-date conversion.
- `ui/MapScreen.kt`: Compose OpenStreetMap canvas, manual pan/zoom/pick and service
  marker grouping; no WebView, GPS, or location permission.
- `notifications/`: session-bound FCM device sync and receipt-time quiet-hour
  selection, deduplication, expiry and foreground/background service source.
- `res/values/`, `values-en/`: Arabic default and matching English strings.
  Display preferences include theme/language and Gregorian/Hijri formatting.

Source paths above are relative to `android/app/src/main/java/org/munassiq/app/`
except Android resources. Native moderator/admin tools are not implemented as
dedicated screens: Settings can open the existing browser dashboard. Organizer
tools have native forms. Do not describe this as complete feature/device parity.

## Prepare server configuration without a build

```bash
cp android/deployment.properties.example android/deployment.properties
```

Creates your ignored Android configuration. Preserve an existing file instead of
overwriting it. Edit `server.origin` to your actual HTTPS IP/domain origin, e.g.
the scheme plus host and optional port, without `/api/v1/` or any other path.
Do not put the Django secret, SMTP credentials or a Firebase service-account key
in Android configuration.

For self-signed HTTPS, set `server.certificate` to the **public PEM certificate**
or public issuing-CA certificate, never a private key. Relative certificate paths
are relative to deployment.properties. Leave it empty for a normal public CA.
`maps.tiles` selects the HTTPS tile provider; preserve provider attribution/policy.

```bash
python3 -B operations/scripts/prepare_android.py
```

Reads that configuration and writes ignored text resources under
`android/app/src/deployment/`. It creates the origin/host constants input and
Network Security Config, and copies only the public certificate when configured.
It does not run Gradle, compile code or create an APK. The generated deployment
directory is intentionally absent from Git; recreate it on another computer.

Trust is scoped to the exact server host; other hosts use system CAs. Cleartext
is rejected. Normal certificate validity and hostname verification remain enabled;
an IP-address certificate must contain that IP as an IP Subject Alternative Name.
Do not replace this with a trust-all manager or hostname-verification bypass.

A self-signed certificate does not automatically prove server ownership: verify
the certificate through a trusted channel before distributing it. Trusting your
own issuing CA allows routine server-leaf renewal without an app update; replacing
the trusted root or directly trusted self-signed leaf requires an app trust update
before the server switch. Moving to a real domain/CA means changing the origin,
clearing the custom certificate setting, rerunning preparation and distributing
the rebuilt app. Actual Android 7/IP trust must still be verified on a device.

For FCM, register this Android package in Firebase and place its **Android client**
`google-services.json` in `android/app/` (ignored). This is different from the
private server service-account JSON; never bundle that server key. Without Android
client configuration the Firebase plugin is skipped and device sync exits safely.
Configure the backend separately as described in notifications.md.

## Checks currently allowed

```bash
python3 -B operations/scripts/check_android_source.py
```

Checks XML parsing, matching Arabic/English string keys, literal resource names,
absence of location permissions, and disabled Android backup. It is **not** a
Kotlin parser, compiler, dependency resolver or device test. A disposable text-only
preparation check also exercised public-certificate scoping and switching back to
system-CA trust. No TLS handshake was tested by that check.

The small backend additions have real API tests: public/admin APK version metadata,
data-only FCM payloads with title/body/expiry, and event/service deep-link kind.
The full backend run passed 155 tests; that does not validate any Android code.

## First build — requires explicit permission

Do not run Android Studio automatic Gradle sync or a build until permission is
given. No wrapper JAR was generated/downloaded; no installed Gradle/SDK/JDK setup
has been verified. After authorization, install/verify the documented toolchain,
prepare real server configuration and use the installed Gradle 8.13 from `android/`:

```text
gradle :app:assembleDebug
```

This resolves libraries, runs KSP/Room generation, compiles Kotlin/resources and
packages a debug APK. It has **not** been run. Resolve evidenced build errors;
do not treat source checks as success. Release signing and release APK distribution
are separate work; keep signing keys private and stable across updates.

## Device acceptance and remaining work

Verify every written flow, then finish gaps found by the build/device run:

- First-launch intro; Arabic/English RTL/LTR, Arabic glyphs, phone digits, light/dark,
  Hijri/Gregorian, keyboard behavior, screen-reader labels and rotation/back navigation.
- Reach the real IP HTTPS server; reject wrong host/certificate/HTTP. Test Android
  7 and a recent Android version. Verify Google Play services/FCM availability.
- Browse without login; contacts hidden. Login/signup/current-policy consent,
  email verification/reset/change through existing browser links, password changes,
  bans, refresh races, logout/all, export/deletion and cache cleanup.
- Lists refresh on opening/pull; paginate/archive/search; cached offline banner
  with retry; no private cached data visible after switching accounts/logout.
- Standard country/city search, service hours/open-now/price/currency, map tiles,
  clusters/coincident places, manual selection, external directions/call/share.
- Event times in both zones, multi-day/series, calendar insert, registrations,
  overlap warning, waitlist promotion, cutoff/reconfirmation and short-notice rules.
- Organizer creation/edit/rejected resubmission/template, duplicate warning,
  photo/PDF/credential pick/upload/removal, roster/statistics/CSV/PDF external open,
  cancellation/reschedule, My items and application statuses.
- Notification permission on first reminder/registration without blocking the
  action if refused, token rotation/session binding, data-message receipts,
  duplicates/expiry, quiet hours at receipt, mute/bans/logout and banner targeting.
- HTTPS event deep links currently use a normal browser/app chooser intent filter.
  Verified Android App Links need the eventual signing fingerprint and a served
  `/.well-known/assetlinks.json`; neither is supplied yet. Account email links use
  the existing web confirmation page. Digest taps currently return to the home list.
- Update check compares public `apk_version_code` to the installed code and offers
  the configured HTTPS APK link. Browser downloads/install instructions are used;
  no APK was produced, signed, installed or verified. Set matching metadata only
  after a real APK exists; do not fabricate an update.
- Complete native UI polish/validation: full Arabic API-error copy, numeric/date
  entry/digits, photo gallery previews, map accessibility, picker paging and all
  follow/profile displays. Specialized staff tools remain browser-based.
- Write/run meaningful Android unit/instrumentation tests after the toolchain can
  execute them. No native test results exist yet.

Android milestone remains **in progress** until compilation and acceptance pass.
Production HTTPS, backup/restore, real SMTP/FCM and browser dashboard QA also remain.

Primary references used for source choices:
[AGP compatibility](https://developer.android.com/build/releases/agp-8-11-0-release-notes?hl=en),
[Compose April BOM](https://android-developers.googleblog.com/2025/04/whats-new-in-jetpack-compose-april-25.html),
[Room releases](https://developer.android.com/jetpack/androidx/releases/room),
[Android trust configuration](https://developer.android.com/privacy-and-security/security-config),
[FCM receive behavior](https://firebase.google.com/docs/cloud-messaging/android/receive-messages).
