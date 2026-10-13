"""Load attributed locations while preserving existing IDs, labels and active flags."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.services import audit
from catalog.models import City, Country
from catalog.search import normalize


def load_locations():
    path = Path(__file__).resolve().parents[2]/'data'/'locations.json'
    return json.loads(path.read_text(encoding='utf-8'))


class Command(BaseCommand):
    help = 'Load all bundled Syrian cities/towns/villages; preserve existing location records.'

    def handle(self, *args, **options):
        added = 0
        with transaction.atomic():
            for entry in load_locations():
                country, created = Country.objects.get_or_create(code=entry['code'], defaults={
                    'name_ar': entry['name_ar'], 'name_en': entry['name_en']})
                added += int(created)
                existing = list(City.objects.filter(country=country))
                source_ids = {row.geonames_id for row in existing if row.geonames_id is not None}
                legacy = defaultdict(list)
                for row in existing:
                    if row.geonames_id is None:
                        legacy[row.name_en.casefold()].append(row)
                pending = []
                source_names = Counter(row['name_en'].casefold() for row in entry['cities'])
                for detail in entry['cities']:
                    source_id = detail['geonames_id']
                    if source_id in source_ids:
                        continue
                    source_ids.add(source_id)
                    candidates = legacy.get(detail['name_en'].casefold(), [])
                    if len(candidates) == 1 and source_names[detail['name_en'].casefold()] == 1:
                        # Adopt an unambiguous manually-created place without renaming,
                        # reactivating or changing its existing location/labels.
                        row = candidates.pop()
                        row.geonames_id = source_id
                        for field, value in detail.items():
                            if getattr(row, field) in (None, '', []):
                                setattr(row, field, value)
                        row.save()
                    else:
                        row = City(country=country, **detail)
                        row.search_text = normalize(' '.join([row.name_ar, row.name_en, row.region_ar,
                            row.region_en, row.district_ar, row.district_en, *row.aliases]))
                        pending.append(row)
                City.objects.bulk_create(pending, batch_size=300)
                added += len(pending)
            audit(None, 'locations.seed', added=added)
        self.stdout.write(f'Locations loaded; new entries: {added}. Existing names/statuses preserved.')
