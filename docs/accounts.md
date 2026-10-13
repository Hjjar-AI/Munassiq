# Account milestone

## Permissions

Every account is a regular user. Additional role grants are independent:
organizer, moderator and admin. Admin is not Django's unrestricted superuser.
Moderation accepts moderator or admin; administrative routes require admin,
plus the configured IP allowlist when enabled. Creator permissions will require
organizer even for admins/moderators when content models arrive.
The verified organizer badge will derive from the organizer role.

Policy updates create a new immutable version; existing signup consent remains
attached to its original version. New signup requires the latest policy ID.
Bootstrap is a local, one-time exception to public signup and does not grant organizer.

Login failures persist account and IP lockout counters. Login requests have an
additional route/IP limit. Staff have a stricter default threshold. Successful
login attempts also count toward the bounded lockout window to limit abuse.
Source IP headers are accepted only from an explicitly configured loopback proxy.
No CAPTCHA or two-factor authentication is added.

Bearer sessions store only token hashes. Refresh rotates tokens within a write
transaction. Revoked, expired or banned sessions cannot access protected endpoints.
Banned login with correct credentials returns the ban reason; incorrect credentials
return the generic failure. Bans retain account records and revoke sessions.
Stopping push for banned users will be implemented with push delivery in milestone 4.

## Organizer applications

`POST /api/v1/organizer-requests/` is multipart, with fields `name`, `workplace`,
`reason` and `credential`. It requires a verified email. Only one open request is
allowed per account; rejected applicants can reapply immediately.
Credentials accept JPEG/PNG or an unencrypted PDF, at most 5 MB.
A streaming upload handler stops oversized file data before the complete file is stored. Image decoding
and re-encoding strips metadata; PDF parsing validates basic document structure.
This is file-type validation, not a malware scanner. Files are stored with random
names outside public media and are accessible only through audited moderator/admin
attachment downloads. Server directories must already be prepared by the helper.

Review queue displays the lock holder's name. Claim is atomic; only the holder can
decide. Locks do not expire automatically; an admin can unlock. Approval grants
organizer and rejection leaves roles unchanged. Documents are removed after the
committed decision. Email queues the decision; push notifications are a later milestone.

## Data deletion and export

Account export includes current account details, consents, application metadata
and session dates. Passwords, token hashes, raw tokens and credential files are excluded.
Own deletion requires the current password; admin deletion is audited. The last
active admin cannot be banned, deleted or stripped of the admin role.
Dependent account records are removed and audit actors become anonymous references.
Private-file cleanup follows the commit. Future content/registration tables must
add the agreed stewardship and cancellation rules before becoming available.

## Scheduled work

`cleanup_accounts` and `send_account_emails` record runs in `MaintenanceRun`.
Cleanup is repeatable; SMTP retries are bounded by message expiry with exponential
backoff. SMTP can duplicate a message if the process crashes after acceptance.
No real email, FCM or internet HTTPS verification has occurred yet.
