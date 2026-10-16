"""Configure the current Linux account's Android paths; never run a build."""
import os
from pathlib import Path
import shutil
import time


def main():
    if os.getuid() == 0:
        raise SystemExit('Run as your regular account, without sudo.')
    home = Path.home()
    if home.stat().st_uid != os.getuid():
        raise SystemExit('HOME must belong to the current account.')
    sdk = Path('/opt/android-shared/Sdk')
    if not (sdk / 'platforms/android-35/android.jar').is_file():
        raise SystemExit('Shared SDK 35 is missing or inaccessible; no settings changed.')
    bashrc = home / '.bashrc'
    if bashrc.is_symlink():
        raise SystemExit('.bashrc is a symlink; inspect its target before changing it.')
    text = bashrc.read_text() if bashrc.exists() else ''
    start = '# BEGIN MUNASSIQ ANDROID ACCOUNT\n'
    end = '# END MUNASSIQ ANDROID ACCOUNT\n'
    block = (
        start
        + 'export ANDROID_HOME=/opt/android-shared/Sdk\n'
        + 'export ANDROID_SDK_ROOT="$ANDROID_HOME"\n'
        + 'export GRADLE_USER_HOME="$HOME/.gradle"\n'
        + 'case ":$PATH:" in\n'
        + '  *":$ANDROID_HOME/platform-tools:"*) ;;\n'
        + '  *) export PATH="$ANDROID_HOME/platform-tools:$PATH" ;;\n'
        + 'esac\n'
        + end
    )
    if start in text or end in text:
        if text.count(start) != 1 or text.count(end) != 1:
            raise SystemExit('Unexpected existing setup markers; no settings changed.')
        first = text.index(start)
        last = text.index(end) + len(end)
        if last <= first:
            raise SystemExit('Invalid setup marker order; no settings changed.')
        updated = text[:first] + block + text[last:]
    else:
        updated = text.rstrip('\n') + '\n\n' + block
    if updated == text:
        print('Account settings already configured. No changes needed.')
        return
    if bashrc.exists():
        backup = home / f'.bashrc.before-android-account-{time.time_ns()}'
        shutil.copy2(bashrc, backup)
        backup.chmod(0o600)
        print(f'Backup: {backup}')
    bashrc.write_text(updated)
    print('Configured shared SDK and personal Gradle cache. Open a new terminal.')
    print('No Java/Gradle version changes, downloads or builds ran.')


if __name__ == '__main__':
    main()
