# Remaining work

Read [the detailed handoff](handoff.md) for the feature-by-feature remaining
checklist, source map, unresolved decisions, Git handling and verification limits.
The consolidated target requirements are in [the updated prompt](../original.propmpt.md).

- Verify real milestone-4 integration: configure Firebase and check delivery,
  invalid tokens, quiet-hour channels and foreground/background behavior with Android.
  Worker/APIs, follows/digests, announcements and settings/stats source exists.
- Build milestone 5: role-specific Arabic/English dashboard, share/fallback pages and account UI.
- Build milestone 6: native Android, maps/clustering, Room cache, calendar/share, APK updates.
- Add Nginx/self-signed HTTPS configuration and verify real SMTP/FCM before launch.
- Add weekly backup/restore scripts, credential exclusions and deletion replay.
- Resolve remaining external-registration semantics and organizer reapplication
  restrictions before implementing their dependent behavior.
- Pin deployment dependencies for the selected Python/platform; requirements remain ranges.
- Review GeoNames location quality/Arabic fallbacks; preserve attribution in client pickers.
- Obtain explicit permission before builds, compilation, Gradle or packaging.
