# Remaining work

Read [the detailed handoff](handoff.md) for the feature-by-feature remaining
checklist, source map, unresolved decisions, Git handling and verification limits.
The consolidated target requirements are in [the updated prompt](../original.propmpt.md).

- Verify real milestone-4 integration: configure Firebase and check delivery,
  invalid tokens, quiet-hour channels and foreground/background behavior with Android.
  Worker/APIs, follows/digests, announcements and settings/stats source exists.
- Verify dashboard in a real browser: responsive RTL/LTR, maps/city lookup,
  uploads/share/downloads, accessibility and complete Arabic validation copy.
  Server-rendered role tools, account UI and public fallback pages are implemented.
- Finish milestone 6: user runs setup/build commands personally (see docs/android.md).
  Do not run Gradle/builds on the user's behalf unless instructed again. Verify
  toolchain/dependencies from their output, fix build errors and run device/native
  tests. Complete the acceptance/gap checklist in docs/android.md. User's validation
  APK build succeeded after the nullable-value corrections. Latest native finishing
  source (gallery, localized errors/input, map accessibility and paged pickers) awaits
  the user's rebuild and phone acceptance. The HTML-inspired native design refresh
  also needs light/dark, RTL/LTR, large-font and navigation acceptance (android-design.md).
  Real server connections remain unverified.
- Add Nginx/self-signed HTTPS configuration and verify real SMTP/FCM before launch.
- Add weekly backup/restore scripts, credential exclusions and deletion replay.
- Pin deployment dependencies for the selected Python/platform; requirements remain ranges.
- Review GeoNames location quality/Arabic fallbacks; preserve attribution in client pickers.
- Obtain explicit permission before builds, compilation, Gradle or packaging.
- Install additional Android tools side by side under /opt/android-shared, preserve
  other versions and defaults; select exact tools with command-scoped settings.
