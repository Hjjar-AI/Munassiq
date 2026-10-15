"""Prepare text configuration/resources only. Never runs Gradle or creates an APK."""
import argparse
from pathlib import Path
import ssl
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'android/deployment.properties')
    parser.add_argument('--output', type=Path, default=ROOT/'android/app/src/deployment')
    parser.add_argument('--validation', action='store_true', help='Label this as a non-connecting build for compilation/UI checks')
    args = parser.parse_args()
    values = {}
    for line in args.config.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, separator, value = line.partition('=')
            if not separator: raise SystemExit('Configuration lines need key=value')
            values[key.strip()] = value.strip()
    origin = values.get('server.origin', '').rstrip('/')
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.path or parsed.query
            or parsed.fragment or parsed.username or parsed.password):
        raise SystemExit('server.origin must be an HTTPS origin without path or credentials')
    if any(character in origin for character in '\r\n\\'):
        raise SystemExit('Invalid origin')
    try: parsed.port
    except ValueError: raise SystemExit('Invalid server port')
    output = args.output
    (output/'res/xml').mkdir(parents=True, exist_ok=True)
    root = ET.Element('network-security-config')
    base = ET.SubElement(root, 'base-config', {'cleartextTrafficPermitted':'false'})
    ET.SubElement(ET.SubElement(base,'trust-anchors'),'certificates',{'src':'system'})
    certificate = values.get('server.certificate')
    if certificate:
        path = Path(certificate).expanduser()
        if not path.is_absolute(): path = args.config.resolve().parent/path
        pem = path.read_text()
        if 'PRIVATE KEY' in pem: raise SystemExit('Use a public certificate, never a private key')
        ssl.PEM_cert_to_DER_cert(pem)
        (output/'res/raw').mkdir(exist_ok=True)
        (output/'res/raw/server_ca.pem').write_text(pem)
        domain = ET.SubElement(root,'domain-config',{'cleartextTrafficPermitted':'false'})
        ET.SubElement(domain,'domain',{'includeSubdomains':'false'}).text = parsed.hostname
        ET.SubElement(ET.SubElement(domain,'trust-anchors'),'certificates',{'src':'@raw/server_ca'})
    else:
        (output/'res/raw/server_ca.pem').unlink(missing_ok=True)
    ET.indent(root)
    ET.ElementTree(root).write(output/'res/xml/network_security_config.xml',encoding='utf-8',xml_declaration=True)
    tiles = values.get('maps.tiles','')
    if tiles and not tiles.startswith('https://'): raise SystemExit('Map tiles require HTTPS')
    if any(character in tiles for character in '\r\n\\'): raise SystemExit('Invalid map tile template')
    (output/'server.properties').write_text(f'server.origin={origin}\nserver.host={parsed.hostname}\nmaps.tiles={tiles}\nvalidation={str(args.validation).lower()}\n')
    print('Prepared ignored Android text resources. No Gradle, build or packaging ran.')


if __name__ == '__main__': main()
