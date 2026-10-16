# Backup and restore

The scripts operate on SQLite only. They do not deploy, overwrite a live database,
start services, accept uploads or include patient data. Run them as mhmmd, using
its backend virtual environment. Six isolated integration tests, including a real disposable backup/restore drill, passed.
No live data has been backed up or restored by this work.

## Configure storage

Choose private folders on this computer, separate from the runtime. For example:

```bash
install -d -m 700 "$HOME/.local/share/munassiq/backups" "$HOME/.local/share/munassiq/privacy"
```

This creates folders only. Put their absolute paths in .env:

```dotenv
APP_BACKUP_DIR=/home/mhmmd/.local/share/munassiq/backups
APP_PRIVACY_DIR=/home/mhmmd/.local/share/munassiq/privacy
BACKUP_KEEP=4
```

APP_PRIVACY_DIR is the persistent deletion journal. Set it before first deployment;
do not casually change it after backups exist. Keep .env private with chmod 600.
If a journal already exists at runtime/privacy, stop all writers and move that
existing folder to the chosen private location; never replace it with a new empty
journal. Existing journal identity must match older backups.

## Make a backup

```bash
.venv/bin/python -B operations/scripts/backup_data.py
```

Loads .env, makes a consistent snapshot with SQLite's online backup API, checks
integrity, scrubs active authentication/FCM tokens and email/push queues, vacuums
removed values out of the snapshot, copies only referenced images/PDFs and writes
a checksum manifest with the source Git revision. Credential documents, their storage names, .env, Firebase
keys, TLS/signing keys and logs are excluded. Existing original data is not edited.

If a referenced file disappears during concurrent cleanup, backup aborts instead
of publishing an incomplete archive. Retry after cleanup. A per-destination lock
prevents concurrent backup runs. Only completed archives are rotated, keeping four.
Archive names include UTC time. Daily run/failure logs are in runtime/logs.
Backups contain account/directory data and password hashes: keep them private.
Copies on the same disk do not protect against disk failure.

For weekly automation, open your own crontab:

```bash
crontab -e
```

Add the line from operations/cron/munassiq-backup.cron.example, or the tailored
backup.cron produced by prepare_deployment.py. This runs Sunday at 03:00 in the
server's time zone. Do not replace the whole crontab or run it as root. Check
runtime/logs/backup-YYYY-MM-DD.log after the first scheduled run.

## Why the deletion journal is separate

Account deletion and final item deletion sync a PII-free intent before deleting.
It contains object ID, creation timestamp and request timestamp, never email/name,
credentials or clinical data. A restore must supply the CURRENT journal, including
records added after the backup. Older snapshots cannot replace it. Preserve it
independently when moving computers; no current journal means restore refuses.

If a deletion transaction later rolls back, its intent can still exist. Recovery
conservatively honors that deletion request rather than risk resurrecting private
data. Live data is not deleted by journal replay until an explicit offline restore.
An unwritable/corrupt journal blocks new deletions; fix its permissions/storage,
not by erasing the journal. This is an intentional privacy-first recovery policy.

## Restore safely

Stop the API, all email/notification/content/account-cleanup timers/services and
backup cron first. Keep every writer stopped until the restore is reviewed and
activated. The script only creates a NEW runtime, never overwrites an existing one.
Choose an archive filename from your backup folder, then substitute it below:

```bash
.venv/bin/python -B operations/scripts/restore_data.py \
  --archive /absolute/path/to/munassiq-TIMESTAMP.tar.gz \
  --target-runtime /absolute/path/to/runtime-restored \
  --journal-dir /home/mhmmd/.local/share/munassiq/privacy \
  --offline
```

The command checks tar paths/types/size limits, file checksums, SQLite integrity,
foreign keys and the journal's identity/history. It replays account deletion with
moderator stewardship and removes hard-deleted content. It clears sessions, device
tokens and queued email/pushes so old actions are not resent. It removes orphaned
media and unlocks reviews. Pending organizer applications become rejected with a
bilingual explanation to reapply, because credentials are deliberately absent.

Use the same source revision as the backup for initial recovery. This script does
not apply migrations or guess cross-version schema changes. Preserve users' new
signups, role/ban changes or edits made after the backup separately if needed;
a backup is a point-in-time recovery, not a merge of two databases.

Read runtime-restored/RESTORE-REVIEW.txt. Verify accounts, stewardship, registrations,
roles/bans and media while offline. Everyone must log in again. Change APP_RUNTIME_DIR
and the systemd ReadWritePaths to the reviewed directory, keeping APP_PRIVACY_DIR
pointing to the CURRENT journal. Resume services/cron only after review. Original
runtime stays untouched for recovery. Never expose a restored backup before replay.

## Moving to a VPS

Transfer source, reviewed runtime/media, current privacy journal, .env and separately
protected TLS/Firebase/signing secrets. Recreate Python dependencies from the lock
file; do not copy a virtual environment. Change URLs/paths, generate new deployment
files, verify permissions and repeat client checks. Do not transfer organizer
credential files into a backup; deal with any still-pending requests explicitly.

## Repeat the isolated integration checks

```bash
.venv/bin/python -B operations/scripts/check_recovery.py
```

Uses a new private temporary runtime and ephemeral configuration, creates a test
database from existing application migrations, and removes it afterwards. It never
opens your live database, sends SMTP/FCM, builds Android or starts services. Six
checks cover exclusions/VACUUM, four-archive retention, deletion replay/stewardship/
seat promotion, missing credential reapplication, safe target refusal, journal
identity and archive traversal/checksum failures, plus fail-closed journal access.
The first execution passed all six tests with a 7.210-second test body. Actual
production backups, scheduling, storage recovery and user-facing clients still
need acceptance in the configured environment.
