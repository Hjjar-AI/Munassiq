#!/usr/bin/env python3
"""Convert local GeoNames country/name archives into an attributed location seed.
No network requests and no database changes. See docs/locations.md for format/license.
"""
import argparse
from collections import defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import zipfile

CODES = {'PPL', 'PPLA', 'PPLA2', 'PPLA3', 'PPLA4', 'PPLA5', 'PPLC', 'PPLCD', 'PPLF', 'PPLG', 'PPLL', 'PPLR', 'PPLS'}


def rows(path, member):
    with zipfile.ZipFile(path) as archive:
        if archive.getinfo(member).file_size > 100*1024*1024:
            raise ValueError('Country data exceeds expected size')
        return [line.split('\t') for line in archive.read(member).decode('utf-8').splitlines()]


def prepare(country_archive, name_archive, output, retrieved):
    names = defaultdict(lambda: defaultdict(list))
    for row in rows(name_archive, 'SY.txt'):
        if len(row) >= 8 and row[2] in {'ar', 'en'} and row[7] != '1':
            names[row[1]][row[2]].append((row[4] != '1', row[6] == '1', int(row[0]), row[3]))
    for languages in names.values():
        for language, variants in languages.items():
            languages[language] = [value[3] for value in sorted(variants)]

    def labels(row):
        variants = names[row[0]]
        english = variants.get('en', [row[2] or row[1]])[0]
        arabic = variants.get('ar', [english])[0]
        return arabic, english

    places = rows(country_archive, 'SY.txt')
    regions = {row[10]: labels(row) for row in places if row[8] == 'SY' and row[6:8] == ['A', 'ADM1']}
    districts = {(row[10], row[11]): labels(row) for row in places if row[8] == 'SY' and row[6:8] == ['A', 'ADM2']}
    result, missing_arabic = [], 0
    for row in places:
        if row[8] != 'SY' or row[6] != 'P' or row[7] not in CODES:
            continue
        ar, en = labels(row)
        if not names[row[0]].get('ar'):
            missing_arabic += 1
        region = regions.get(row[10], ('', ''))
        district = districts.get((row[10], row[11]), ('', ''))
        aliases = list(dict.fromkeys([row[1], row[2], *names[row[0]].get('ar', []), *names[row[0]].get('en', [])]))
        result.append({'geonames_id': int(row[0]), 'name_ar': ar, 'name_en': en,
            'region_ar': region[0], 'region_en': region[1], 'district_ar': district[0], 'district_en': district[1],
            'latitude': float(row[4]), 'longitude': float(row[5]), 'time_zone': row[17], 'aliases': aliases})
    result.sort(key=lambda row: row['geonames_id'])
    Path(output).write_text(json.dumps([{'code': 'SY', 'name_ar': 'سوريا', 'name_en': 'Syria', 'cities': result}], ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    metadata = {'provider': 'GeoNames', 'license': 'CC BY 4.0', 'retrieved_client_date': retrieved,
        'source': 'https://download.geonames.org/export/dump/SY.zip',
        'names_source': 'https://download.geonames.org/export/dump/alternatenames/SY.zip',
        'attribution': 'Location data derived from GeoNames (https://www.geonames.org/), CC BY 4.0.',
        'included_feature_codes': sorted(CODES), 'places': len(result), 'arabic_name_fallbacks': missing_arabic,
        'country_archive_sha256': hashlib.sha256(Path(country_archive).read_bytes()).hexdigest(),
        'names_archive_sha256': hashlib.sha256(Path(name_archive).read_bytes()).hexdigest(),
        'transformations': 'Filter current populated-place feature codes; choose language-labelled non-historic preferred Arabic/English names; English fallback when Arabic is absent.'}
    Path(output).with_name('locations-source.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Prepared {len(result)} Syrian places; {missing_arabic} Arabic labels use English fallback.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('country_archive')
    parser.add_argument('names_archive')
    parser.add_argument('output')
    parser.add_argument('--retrieved-date', required=True, type=date.fromisoformat)
    args = parser.parse_args()
    prepare(args.country_archive, args.names_archive, args.output, args.retrieved_date.isoformat())
