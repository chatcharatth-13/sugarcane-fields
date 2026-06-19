# Sugarcane-burning hotspot mapping — Northeast Thailand

End-to-end workflow to replace manual GISTDA collection. Run on your own
machine (it needs internet + the libraries below).

> **New here?** Start with **[docs/HANDOFF.md](docs/HANDOFF.md)** — a full handoff
> (architecture, pipeline, adding a district, cloud, deployment, user guide,
> limitations, credentials). Focused docs: [DEPLOY](docs/DEPLOY.md) · [CLOUD_SETUP](docs/CLOUD_SETUP.md).

## Project layout
```
app/        the deployable web app (field_manager.html + manifest.json +
            th_adm3.geojson + data/) — see docs/DEPLOY.md
scripts/    the pipeline (run from the project ROOT, e.g. python scripts/enrich_fields.py)
work/       intermediate outputs: *.gpkg, *_fields.geojson, summaries, quick maps
raw/        heavy inputs: landuse/ (LDD shapefiles), downloaded admin boundaries
docs/       SETUP.md, DEPLOY.md, how_to_run.html
archive/    field_picker.html (the old single-district tool)
```

## Pipeline at a glance (run from the project root)
```bash
python scripts/make_sugarcane.py     # raw/landuse/*.shp     -> work/sugarcane.gpkg
python scripts/run_districts.py      # FIRMS hotspots        -> work/<prefix>_hotspots.gpkg ...
python scripts/run_reports.py        # clip + burned area    -> work/ + app/data/
python scripts/enrich_fields.py      # admin names + manifest-> app/data/ + app/manifest.json
```
Districts are listed in `scripts/run_districts.py` / `run_reports.py`. The
single-district scripts below are what those wrappers call.

## 0. Install
```bash
pip install -r requirements.txt
```
`geopandas` pulls in GDAL; if pip struggles, use conda:
`conda install -c conda-forge geopandas folium requests`.

## 1. Boundary — now automatic
You no longer need to fetch the boundary by hand. If you omit `--boundary`,
the script downloads Thailand ADM2 districts from geoBoundaries (free, no
key), filters to Si Chomphu, and derives the bounding box from it. Supply
`--boundary sichomphu.geojson` only if you already have a preferred polygon
(e.g. a more precise OCSB/LDD boundary) or want to skip the download.

## 2. Get a sugarcane layer (this is what makes a hotspot "sugarcane")
A hotspot only says *something burned here* — not the crop. To isolate
sugarcane you overlay a sugarcane parcel layer. Two ways:

**Easiest — let the script fetch it (GISTDA).** GISTDA publishes the
satellite-derived sugarcane map (40 m, updated every 2 weeks) under an open
licence. Register a free key at https://api-gateway.gistda.or.th/v2 , then
pass `--gistda-key YOURKEY` (no `--sugarcane` needed). The script queries the
"search by geometry" endpoint with the district bbox and builds the layer
for you, saved as `sugarcane_gistda.geojson`.

**Or supply your own file** via `--sugarcane sugarcane.gpkg`. Sources:
- **OCSB** (สอน.) — note its *open* portal only has province-level area
  statistics (CSV), not parcels; the GIS plot layer is request-only via their
  ICT division. For polygons, GISTDA above is the practical source.
- **LDD** (กรมพัฒนาที่ดิน) land-use maps — filter to the sugarcane class.
- **DIY**: classify Sentinel-2 in QGIS/GEE.

Either way it's optional — without a sugarcane layer you still get all
district hotspots, just not crop-filtered.

## 3. Get a free FIRMS MAP_KEY (only for `--mode api`)
https://firms.modaps.eosdis.nasa.gov/api/area/ → "Get MAP_KEY".
Limit: 5000 requests / 10 min — far more than this job needs.

## 4. Run it

### Option A — Archive download + file mode (simplest for a fixed past range)
1. https://firms.modaps.eosdis.nasa.gov/download/ → draw/enter your area,
   set 2025-12-01 to 2026-05-05, pick **VIIRS** (S-NPP, NOAA-20, NOAA-21),
   export **CSV** or **SHP**. The archive tool auto-fills science-quality
   (SP) data where ready and NRT for the most recent weeks.
2. ```bash
   python scripts/firms_sichomphu.py --mode file --in firms_archive.csv \
       --district "chomphu" --sugarcane work/sugarcane.gpkg --out-prefix sichomphu
   ```

### Option B — Direct API (best for repeatable / ongoing monitoring)
```bash
python scripts/firms_sichomphu.py --mode api --map-key YOURKEY \
    --district "chomphu" --sugarcane work/sugarcane.gpkg --out-prefix sichomphu
```
Note on data quality: SP (science-quality) lags observation by ~2–3 months
(up to 5). For the most recent weeks the SP sources return nothing — re-run
adding the NRT sources by editing `API_SOURCES` (add `VIIRS_SNPP_NRT`,
`VIIRS_NOAA20_NRT`), then let dedup merge them.

### Useful flags
- `--min-conf n` keep nominal+high confidence VIIRS (drops `l`)
- `--min-frp 1` drop very low fire radiative power
- `--start / --end` change the window
- `--out-prefix sichomphu_2025_26` name the outputs

## 5. Outputs (under `work/`)
- `work/<prefix>_hotspots.gpkg` — all detections inside the district
- `work/<prefix>_sugarcane_hotspots.gpkg` — only those inside sugarcane parcels
- `work/<prefix>_summary.csv` — counts by month (and sugarcane / not)
- `work/<prefix>_map.html` — quick interactive check (red = sugarcane, gray = other)

`prep_fields.py` + `enrich_fields.py` then turn these into the web app's
`app/data/*.geojson` + `app/manifest.json`. Open the `.gpkg` files in QGIS for
cartography, density maps, or further analysis.

## Notes / caveats
- **VIIRS over MODIS**: 375 m vs 1 km. Sugarcane plots are small; MODIS
  misses many. The script defaults to VIIRS.
- **Persistent same-location hotspots** across many dates are often a sugar
  mill or other industrial source, not field burning — inspect before
  concluding.
- A FIRMS pixel is a detection footprint, not a precise fire outline; treat
  counts as relative intensity, not exact burned area.

## Manual / no-code alternative (QGIS)
1. Load `sichomphu.geojson` and the archive CSV (Add Delimited Text Layer,
   X=longitude, Y=latitude, CRS EPSG:4326).
2. Vector ▸ Geoprocessing ▸ **Clip** points by the district polygon.
3. Vector ▸ Data Management ▸ **Join attributes by location** (predicate
   *within*) against the sugarcane layer → filter to matched features.
4. Style / export. Same result as the script, fully manual.
