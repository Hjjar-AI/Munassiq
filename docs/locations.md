# Maintained Syrian location list

Launch country: Syria (`SY`), as requested. The bundled seed includes 10,816
GeoNames populated places: cities, towns, villages and populated localities.
It excludes records classified as historical, abandoned, destroyed or sections
of another populated place. This is the complete selected country extract,
not a claim that every real-world settlement is represented or up to date.

Source: [GeoNames country downloads](https://download.geonames.org/export/dump/)
and [language-labelled alternate names](https://download.geonames.org/export/dump/alternatenames/).
Location data derived from GeoNames (https://www.geonames.org/),
licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Keep this attribution when redistributing the seed; dashboard/app location
pickers must display the GeoNames attribution too.

Names prefer language-labelled Arabic/English non-historic variants. 756 entries
have no Arabic-labelled name and use English fallback. Region/district labels
help distinguish same-named towns. Stable GeoNames IDs preserve distinct places;
1,357 duplicate ASCII names in the source made a country/name unique rule unsuitable.
No coordinates are obtained from a user's GPS; the seed's coordinates are place centroids.
A service's actual coordinates must still be picked on the map.

To load the list after setup and migrations:

```bash
bash operations/scripts/run_management.sh seed_locations
```

This adds bundled country/city records to your database. Reruns preserve existing
IDs, names, active flags and manually corrected records. It does not fetch data
from the internet. Admins can edit/disable city records through the admin API.

`GET /api/v1/cities/?country=<country-id>&q=<search>&page=1` returns at most 50
choices. `X-Next-Page` identifies the next page when present. Search normalizes
Arabic/English names and aliases. Location selection uses existing IDs, not free text.

To prepare a later seed, download both Syria ZIPs from the source links above,
then use this local converter:

```bash
python3 operations/scripts/prepare_geonames_locations.py /path/to/SY.zip /path/to/names-SY.zip backend/catalog/data/locations.json --retrieved-date YYYY-MM-DD
```

The first two arguments are the downloaded country/name archives; the third is
the output file. Replace `YYYY-MM-DD` with your download date. This converts
location data and writes source hashes/counts in `locations-source.json`;
it does not access the network or change the database. Review the changed seed
before loading it. Existing records are not silently renamed or relocated.
