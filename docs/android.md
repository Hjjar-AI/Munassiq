# Android source and first-build handoff

The native app source is in `android/`, tracked by the root Git repository. It is
not another submodule. The user reported a successful validation APK build,
including the nullable-warning corrections. Device behavior and real server
connections remain unverified.
The user's latest instruction is to run builds personally: agents should supply
the command and must not invoke Gradle/builds themselves unless the user explicitly
changes that instruction. Fixing compiler/dependency errors and runtime acceptance
remains required work once the user supplies build output.

## Shared tool layout

```text
/opt/android-shared/
├── android-studio/       Installed IDE with its bundled Java
├── Sdk/                  SDK-managed components; preserve its internal structure
├── gradle/               Explicitly installed, versioned Gradle distributions
├── downloads/
│   ├── gradle/           Gradle archives and checksums
│   └── android-sdk/      SDK archives and repository metadata
└── .gradle/              Existing shared Gradle user-home/cache data
```

Keep installed versions side by side. Do not move active Gradle caches or the
SDK merely to rename them: other projects, IDE settings and daemons may reference
those paths. Personal Gradle caches under the user's home are independent and
are not merged here. No global PATH, Java or SDK defaults are changed.
Joplin and containerd remain separate applications under /opt.

## Commands for your terminal (current workflow)

Run from the project directory:

```bash
python3 -B operations/scripts/setup_android_tools.py
```

Downloads/checks the pinned archives and installs alongside existing versions:
`/opt/android-shared/Sdk/platforms/android-35`,
`/opt/android-shared/Sdk/build-tools/35.0.0`, and
`/opt/android-shared/gradle/gradle-8.13`. Download archives stay in
`/opt/android-shared/downloads/gradle` and `downloads/android-sdk`, grouped by tool
rather than project. Partial downloads resume when the provider supports it. Existing installations are preserved. It does not run a build,
change PATH/Java/SDK defaults or accept licenses. The shared SDK already has an
accepted license record; this command does not change it. You need write access
to those shared directories. If permission fails, report the error rather than
running the whole toolchain as root. You may use `--root` for a different explicit
shared installation directory if desired.

Until your actual IP HTTPS server and public certificate are ready:

```bash
bash operations/scripts/build_android.sh --validation --console=plain 2>&1 | tee android-build.log
```

Builds a **validation-only debug APK**, with a visible warning and API networking
blocked. A reserved, non-connecting address is used only to validate compilation.
`tee` displays and saves the output so you can share compiler errors. The build
script selects the exact Gradle and SDK paths only for this process; shell and
Android Studio defaults remain unchanged. A successful build should place the APK
in `android/app/build/outputs/apk/debug/app-debug.apk`. The user has reported a successful validation build. No build has been run by the agent.

When `android/deployment.properties` contains your actual HTTPS IP origin and
public certificate, use the connecting build instead:

```bash
bash operations/scripts/build_android.sh --console=plain 2>&1 | tee android-build.log
```

No domain is required. The server certificate must include the static IP as an IP
Subject Alternative Name. These scripts do not set up the server's HTTPS for you.
JDK 21 is currently installed and selected on this machine; the source targets
Java 17 bytecode. No Java installation/default was changed. Installation/build
commands above have not been executed; syntax/source checks alone have passed.

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

## First build — user runs it

The agent has not run Android Studio sync, Gradle or a build. No wrapper JAR was
generated/downloaded. The side-by-side setup/build scripts above are the current
workflow. The equivalent explicit Gradle invocation uses the versioned executable
with the shared SDK selected just for that command:

```text
ANDROID_HOME=/opt/android-shared/Sdk ANDROID_SDK_ROOT=/opt/android-shared/Sdk /opt/android-shared/gradle/gradle-8.13/bin/gradle --project-dir android :app:assembleDebug
```

This resolves libraries, runs KSP/Room generation, compiles Kotlin/resources and
packages a debug APK. The user successfully ran the validation build before the latest UI changes. Resolve evidenced build errors;
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
  a debug validation APK was built by the user; release signing and installation remain unverified. Set matching metadata only
  after a real APK exists; do not fabricate an update.
- Verify the new native finishing work described below on a real device. Specialized
  staff tools remain browser-based; follow/profile displays still need acceptance.
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

## Building from the work account

The user approved developer-group write access to this checkout's android folder,
including deployment configuration. ACLs grant existing access and inheritance for
new files; project root, backend and Git metadata were not changed. Both mhmmd and
work already belong to developer. Avoid simultaneous builds of the same checkout.

Run as work (not through sudo):

```bash
cd "/mnt/Common/IT Projects/Lects"
GRADLE_USER_HOME="$HOME/.gradle" bash operations/scripts/build_android.sh --validation --console=plain 2>&1 | tee "$HOME/munassiq-android-build.log"
```

This selects work's personal dependency cache and saves its log in its own home;
the build script selects the shared SDK and Gradle executable. work's private shell
configuration was not inspected. ACL inspection passed; a build from work remains
unverified until the user supplies its output.

## 2026-10-16 — native finishing implementation

- PhotoGallery loads permitted API files into sampled, memory-only bitmaps, with
  previous/next, a larger dialog, spoken position, error/retry and individual removal
  in organizer forms. Event/service images and organizer profile photos use it.
  Upload buttons respect the existing three-event/five-service photo limits.
- InputSupport translates known account/content/registration errors into bilingual
  resources, flattens field errors instead of showing JSON, and provides localized
  status fallbacks for unknown messages. Unknown English validation text becomes a
  localized field/status message in Arabic; it is not an exact translation of every
  future server error. User-authored ban reasons retain their original text.
- Numeric input supports Arabic/Persian digits and Arabic decimal/group separators.
  Price serialization retains decimal precision. Email/phone/password/numeric
  keyboards are selected, with field-labelled parse errors and spoken error updates.
- Native date/time pickers support event dates, rescheduling, deadlines, quiet hours
  and working hours. Text entry remains available; local event dates use the selected
  IANA zone and reject DST gaps/ambiguities. ISO text entry remains Gregorian even
  when the display calendar is Hijri; display preferences do not change API dates.
- ReferencePicker searches and appends city/venue pages, preserves choices by ID,
  resets pages when search/country changes, and offers retry/loading/empty states.
  ApiClient adapts the actual city's X-Next-Page header to results/next_page internally;
  the backend API contract is unchanged. Countries/categories/currencies are unpaged
  in the current API. No API endpoints were invented.
- Map controls have localized spoken names. Coordinate entry, select-center and a
  text list provide alternatives to canvas gestures. The embedded map has a bounded
  scroll area, and existing venue coordinates initialize organizer editing.

XML, resource parity (304 keys), literal resource references, manifest and whitespace
checks passed. No Gradle, compilation, builds or test-suite work was performed for
this change. Prior user build success predates this source: rebuild and exercise
RTL/LTR, TalkBack, small screens, upload/removal, page two/search/country reset,
invalid dates/numbers, permissions and offline failures before declaring acceptance.

## HTML-inspired native visual refresh

See [design notes](android-design.md). DesignSystem.kt now centralizes the teal/sage
light/dark scheme, shapes, typography and native glyphs. A bottom bar, clearer
headers, tonal browse/detail cards, collapsible advanced filters and grouped settings
adapt ideas from the user's local Material You/One UI/minimal HTML examples.
313 bilingual resource keys pass source checks. Rebuild and visual/device acceptance
remain required; no HTML WebView, dependency/version change or build was introduced.

## Release tooling checkpoint

See release.md for environment-only signing, --release in the user-run build helper,
verified APK publication and domain assetlinks generation. Validation releases are
rejected. Version code/name remain unchanged. HTTPS service deep links now route
natively too; autoVerify remains false for static-IP/self-signed deployments and
can be enabled only for a domain/public-trust configuration. No release build,
key generation, signing verification or device App Link verification ran.
