"""Create public Digital Asset Links JSON from a signing certificate fingerprint."""
import argparse
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sha256', required=True, help='Public signing certificate SHA-256 fingerprint, not a password')
    parser.add_argument('--package', default='org.munassiq.app')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    fingerprint = args.sha256.replace(':', '').upper()
    if not re.fullmatch('[0-9A-F]{64}', fingerprint) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+', args.package):
        raise SystemExit('Invalid public fingerprint or application ID')
    formatted = ':'.join(fingerprint[index:index+2] for index in range(0, 64, 2))
    document = [{'relation':['delegate_permission/common.handle_all_urls'],
        'target':{'namespace':'android_app', 'package_name':args.package,
            'sha256_cert_fingerprints':[formatted]}}]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(document, stream, indent=2)
    print('Prepared public assetlinks.json. No signing keys, build, upload or verification ran.')


if __name__ == '__main__':
    main()
