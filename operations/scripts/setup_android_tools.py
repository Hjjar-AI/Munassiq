"""Install side-by-side Android tools; never run a build or change defaults."""
import argparse
import hashlib
from pathlib import Path
import shutil
import tempfile
from urllib.request import Request, urlopen
import zipfile

PACKAGES = [
    ('gradle-8.13-bin.zip', 'https://downloads.gradle.org/distributions/gradle-8.13-bin.zip',
        'sha256', '20f1b1176237254a6fc204d8434196fa11a4cfb387567519c61556e8710aed78',
        'gradle/gradle-8.13', 'bin/gradle', 'gradle.zip'),
    ('platform-35_r02.zip', 'https://dl.google.com/android/repository/platform-35_r02.zip',
        'sha1', '0bb560a90a7a2cbd0dd8348224d518b638fe7949',
        'Sdk/platforms/android-35', 'android.jar', 'platform35.zip'),
    ('build-tools_r35_linux.zip', 'https://dl.google.com/android/repository/build-tools_r35_linux.zip',
        'sha1', '2cfaa0bbb2336e9ec18ed3ecea84fa2e2af607bc',
        'Sdk/build-tools/35.0.0', 'aapt2', 'buildtools35.zip'),
]


def matches(path, algorithm, expected):
    if not path.is_file():
        return False
    digest = hashlib.new(algorithm)
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest() == expected


def download(url, path, algorithm, expected):
    if matches(path, algorithm, expected):
        return
    start = path.stat().st_size if path.exists() else 0
    headers = {'Range': f'bytes={start}-'} if start else {}
    print(f'Downloading {path.name}; existing partial: {start:,} bytes', flush=True)
    with urlopen(Request(url, headers=headers), timeout=90) as response:
        resume = response.status == 206 and response.headers.get('Content-Range', '').startswith(f'bytes {start}-')
        if response.status == 206 and not resume:
            raise RuntimeError('Unexpected partial download response; archive kept for inspection')
        with path.open('ab' if resume else 'wb') as output:
            shutil.copyfileobj(response, output)
    if not matches(path, algorithm, expected):
        raise RuntimeError(f'Checksum mismatch: {path}. Installation stopped; no existing version replaced.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/opt/android-shared'))
    parser.add_argument('--reuse-downloads', type=Path, help='Optional folder containing previous partial downloads')
    args = parser.parse_args()
    for name, url, algorithm, expected, relative, marker, previous_name in PACKAGES:
        target = args.root/relative
        if target.exists():
            if not (target/marker).is_file():
                raise SystemExit(f'Existing incomplete directory: {target}; no overwrite attempted.')
            print(f'Keeping existing version: {target}', flush=True)
            continue
        cache = args.root/'downloads'/('gradle' if relative.startswith('gradle/') else 'android-sdk')
        cache.mkdir(parents=True, exist_ok=True)
        archive = cache/name
        legacy = args.root/'downloads/munassiq'/name
        if not archive.exists() and legacy.is_file():
            shutil.copy2(legacy, archive)
        if not archive.exists() and args.reuse_downloads and (args.reuse_downloads/previous_name).is_file():
            shutil.copy2(args.reuse_downloads/previous_name, archive)
        download(url, archive, algorithm, expected)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.munassiq-install-', dir=target.parent) as temporary:
            staging = Path(temporary)
            with zipfile.ZipFile(archive) as package:
                for entry in package.infolist():
                    output = staging/entry.filename
                    if not output.resolve().is_relative_to(staging.resolve()):
                        raise RuntimeError('Unsafe archive member')
                    # Reject links; these packages contain ordinary files/directories.
                    if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                        raise RuntimeError('Unexpected archive symlink')
                    package.extract(entry, staging)
                    mode = (entry.external_attr >> 16) & 0o777
                    if mode and output.is_file():
                        output.chmod(mode)
            contents = list(staging.iterdir())
            if len(contents) != 1 or not (contents[0]/marker).is_file():
                raise RuntimeError(f'Unexpected archive layout: {name}')
            if target.exists():
                raise RuntimeError('Destination appeared during installation; no overwrite attempted')
            contents[0].rename(target)
        print(f'Installed {target}', flush=True)
    print('Done. Existing versions, PATH, JAVA_HOME and SDK defaults were not changed.')
    print('No Gradle command, build, SDK license acceptance or packaging ran.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error)) from None
