# Native design refresh — 2026-10-16

Reviewed the 17 HTML files in /home/mhmmd/Downloads by reading their layout/content
and styles. Material You Light 605757 and its duplicate, Material You Dark 5ce317,
One UI 4b4837 and Minimal Monochrome dc9170 provided the main visual ideas.
No reference HTML was executed, copied into the app, modified or uploaded.

## Applied ideas

- Material You: rounded search, tonal hero/cards, selected navigation indicators,
  coordinated light/dark color roles and clear primary/secondary text hierarchy.
- One UI: spacious title, 20–24 dp content padding, rounded grouped surfaces and
  bottom destinations within thumb reach.
- Minimal Monochrome: restrained decoration and readable titles/metadata. The app
  retains a single teal/sage identity; these are inspirations, not 17 selectable skins.

DesignSystem.kt centralizes palette, typography, shapes and small native Canvas
icons. AppScreen uses a four-destination bottom bar for events, services, map and
registrations; categories/My items remain reachable through secondary chips, with
settings in the header. Browse intros contain descriptive text, not fabricated
user metrics. Search remains visible; advanced filters expand on request.
Details use a tonal title card. Settings has account, appearance and privacy
sections. Existing forms/galleries inherit shared tokens. Arabic strings, start/end
layout, phone digit preferences and original feature/permission APIs are preserved.
System sans-serif fallback renders Arabic; no font or dependency was downloaded.

## Verification limits

XML, 313 matching bilingual resource keys, literal references, manifest and
whitespace checks passed. There was no Gradle/build, compilation, native test,
emulator, screenshot or visual rendering. The user must rebuild and check light/
dark, Arabic/English, large text, narrow screens, navigation, keyboard/insets and
expanded-filter pagination. The source refresh does not prove visual acceptance.
