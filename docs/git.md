# One repository for Munassiq

The project now uses one Git repository at the project root, containing backend/,
android/, operations/ and docs/. backend/ is an ordinary folder, not a submodule.

## Everyday commands

Run from the project root:

```bash
git status
git diff --stat
```

These show pending files and a summary of changes. To record reviewed source work:

```bash
git add backend android operations docs README.md original.propmpt.md
git commit -m "Describe the change"
```

The first command stages changes; the second creates a local checkpoint. Review
what is staged with `git diff --cached --stat` first. Git does not include ignored
.env, virtual environments, runtime databases, build output or recovery backups.
Never force-add those files. Do not use separate backend commits or submodule
commands. Backend and Android releases can still have independent version numbers.

## Remote and history

The sole active remote is origin at https://github.com/Hjjar-AI/Munassiq.git.
The current project branch remains master to match the existing repository.
No GitHub repositories were deleted, renamed, archived or pushed by this conversion.
The former backend remote URL is retained only in recovery/historical records.
The old GitHub backend repository remains unchanged; archiving it is optional later.
Remote-tracking information was inspected locally, without fetching current GitHub
state. Local success does not prove these commits have been published.

Original backend commit hashes remain reachable through the consolidation merge's
second parent and local archive/backend-main branch. This branch is historical,
not a second repository. Inspect older backend history with:

```bash
git log archive/backend-main -- accounts/services.py
git log -- backend/accounts/services.py
```

The first reads pre-consolidation backend paths; the second reads changes under the
new backend/ prefix. History was joined without rewriting either original history.
An ordinary future push of master includes the merged backend ancestors too; no
force push or separate publication of the archive branch is needed.

## Recovery snapshot

Private ignored .repo-backups/20261016-monorepo contains:

- root.bundle and backend.bundle: verified, complete Git histories/refs before conversion.
- git-metadata.tar.gz: both original Git metadata directories.
- working-files.tar.gz and file-sha256.json: tracked/nonignored current files and hashes.
- repository-info.txt: original commits, status and remote configuration.
- backend-git-directory/: original backend metadata retained after removing nesting.

Ignored runtime files, databases, environments and credentials were left in place;
they are not included in the working-file snapshot. This local snapshot is not an
off-device operational backup. Restore into a separate directory first; never
extract old Git metadata over newer work. Bundles can be cloned separately for
investigation. Keep these recovery files private and outside published source.

The work account's existing Android-folder permissions were not expanded to root
Git metadata. Use the repository owner's account for Git mutations, or a separate
clone if work needs an independently writable Git checkout.
