"""Verify an existing signed release APK and copy it into a chosen public folder."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from operations_common import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--public-root', type=Path, required=True)
    parser.add_argument('--certificate-sha256', required=True)
    parser.add_argument('--build-tools', type=Path, default=Path('/opt/android-shared/Sdk/build-tools/35.0.0'))
    args = parser.parse_args()
    expected = args.certificate_sha256.replace(':', '').lower()
    if not re.fullmatch('[0-9a-f]{64}', expected):
        raise SystemExit('Supply the expected PUBLIC signing certificate SHA-256 fingerprint')
    signature = subprocess.check_output([str(args.build_tools/'apksigner'), 'verify', '--verbose', '--print-certs', str(args.apk)], text=True)
    fingerprints = re.findall(r'certificate SHA-256 digest: ([0-9a-fA-F]+)', signature)
    if len(fingerprints) != 1 or fingerprints[0].lower() != expected or 'CN=Android Debug' in signature:
        raise SystemExit('Unexpected signing certificate or debug signing key; nothing published')
    badging = subprocess.check_output([str(args.build_tools/'aapt2'), 'dump', 'badging', str(args.apk)], text=True)
    match = re.search(r"^package: name='([^']+)' versionCode='([0-9]+)' versionName='([^']*)'", badging, re.M)
    if not match or match[1] != 'org.munassiq.app' or 'application-debuggable' in badging:
        raise SystemExit('Wrong package or debuggable APK; nothing published')
    destination = args.public_root.expanduser().resolve()/'downloads'
    destination.mkdir(mode=0o755, parents=True, exist_ok=True)
    target = destination/'munassiq.apk'
    with tempfile.NamedTemporaryFile(dir=destination, prefix='.apk-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with args.apk.open('rb') as source:
                shutil.copyfileobj(source, stream)
            stream.flush()
            os.fsync(stream.fileno())
            checksum = digest(temporary)
            if checksum != digest(args.apk):
                raise ValueError('APK changed while copying; no publication')
            temporary.chmod(0o644)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    metadata = {'package': match[1], 'version_code': int(match[2]), 'version_name': match[3],
        'sha256': checksum, 'certificate_sha256': expected, 'path': '/downloads/munassiq.apk'}
    (destination/'release-info.json').write_text(json.dumps(metadata, indent=2)+'\n')
    (destination/'release-info.json').chmod(0o644)
    print(json.dumps(metadata, indent=2))
    print('Existing signed APK copied. Set matching version/link in dashboard App settings after installation checks.')


if __name__ == '__main__':
    main()
