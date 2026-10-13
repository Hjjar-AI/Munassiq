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
