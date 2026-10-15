"""Lightweight text/resource checks only; not Kotlin/Gradle/build verification."""
import ast
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def main():
    res = ROOT/'android/app/src/main/res'
    for path in res.rglob('*.xml'):
        ET.parse(path)
    languages = [{node.attrib['name'] for node in ET.parse(res/directory/'strings.xml').getroot()}
        for directory in ('values', 'values-en')]
    if languages[0] != languages[1]:
        raise SystemExit('Arabic/English string keys differ')
    for path in (ROOT/'android/app/src/main/java').rglob('*.kt'):
        for pair in re.findall(r'R\.string\.(\w+)|label\("(\w+)"\)', path.read_text()):
            key = next(value for value in pair if value)
            if key not in languages[0]:
                raise SystemExit(f'Missing string {key} in {path.name}')
    manifest = ET.parse(ROOT/'android/app/src/main/AndroidManifest.xml')
    android = '{http://schemas.android.com/apk/res/android}'
    permissions = {node.get(android+'name') for node in manifest.getroot().findall('uses-permission')}
    if any('LOCATION' in name for name in permissions):
        raise SystemExit('Unexpected location permission')
    if manifest.getroot().find('application').get(android+'allowBackup') != 'false':
        raise SystemExit('Account storage must be excluded from Android backup')
    ast.parse((ROOT/'operations/scripts/prepare_android.py').read_text())
    print(f'XML, matching {len(languages[0])} resource keys, literal references and manifest checks passed.')
    print('Kotlin, dependency resolution, TLS, Room and device behavior remain unverified; no Gradle/build ran.')


if __name__ == '__main__': main()
