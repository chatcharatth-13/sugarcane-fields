# Deploying the Sugarcane Field Manager

`field_manager.html` is a static web app. It reads `manifest.json` and, per
district, fetches `<prefix>_fields_enriched.geojson` + `<prefix>_sugarcane_hotspots.geojson`
+ `<prefix>_burned_patches.geojson`. Only the selected district loads, so the
hosted footprint per visitor is small.

## 0. (Re)generate the data
Run after any change to the source field/hotspot files:
```bash
python enrich_fields.py
```
This (re)writes the 11 `*_fields_enriched.geojson` and `manifest.json`, adding
ตำบล / อำเภอ / จังหวัด (Thai, from `th_adm3.geojson`) and X/Y coordinates.

## What to deploy (the slim set)
Upload ONLY these to the host:
- `field_manager.html`
- `manifest.json`
- `*_sugarcane_hotspots.geojson` (11 files — the primary layer)
- `*_hotspots.geojson`           (11 files — all fires)
- `*_burned_patches.geojson`     (one per district)
- `*_fields_enriched.geojson`    (optional LDD reference layer)
- `th_adm3.geojson`              (7 MB — runtime tambon/อำเภอ/จังหวัด auto-detect + dropdowns)

(File counts grow as you add districts — the dropdown is manifest-driven.)

## What to NEVER deploy
- `tha_adm2.geojson`, `_tha_adm2.geojson` (265 MB each — prep inputs only)
- `th_adm1.geojson`, `th_adm2.geojson`, `sugarcane.gpkg`, all `*.gpkg`
- the Python scripts and `*_map.html`
`.gitignore` already excludes these. Note `th_adm3.geojson` IS needed at runtime
(it is not ignored), unlike the other admin files which are prep-only.

## Option A — GitHub Pages (share a URL)
```bash
cd C:/Users/WINDOWS/Downloads/sichomphu_project
git init
git add field_manager.html manifest.json *_fields_enriched.geojson *_sugarcane_hotspots.geojson *_burned_patches.geojson .gitignore
git commit -m "Sugarcane field manager"
gh repo create sugarcane-fields --public --source=. --push
```
Then on GitHub: **Settings → Pages → Branch: main / root → Save**.
The URL will be `https://<you>.github.io/sugarcane-fields/field_manager.html`.

## Option B — Netlify (drag & drop, no git)
1. Copy the slim set into an empty folder.
2. Go to https://app.netlify.com/drop and drag that folder in.
3. Share the generated URL (append `/field_manager.html`).

## Run locally (for editing / offline)
The app must be served over HTTP (file:// can't `fetch`):
```bash
python -m http.server 8000        # run inside this folder
# open http://localhost:8000/field_manager.html
```

## How the app works (v2)
- **Primary data = hotspots.** The LDD `*_fields_enriched.geojson` are an *optional
  reference* layer (off by default) — they are NOT anyone's real fields.
- **Buying stations (จุดรับซื้อ):** click **➕ จุดรับซื้อ** then click the map to drop a
  station; set a **radius (กม.)** per station. Hotspots/fields are tagged by the
  station whose radius contains them, and **เฉพาะในรัศมี** filters to inside-radius only.
- **Your real fields:** draw them with the polygon tool (top-left). A field is marked
  **เผา/ไม่เผา** by whether a sugarcane hotspot falls inside it.
- **Multi-district:** tick several อำเภอ in the dropdown to combine their hotspots.
- **Import:** **📁 นำเข้า** loads any GeoJSON — points → hotspots, polygons → your
  fields, points with `radius_km` → stations (e.g. another district's hotspots).
- **Two reports:** pick **รายงานจุดความร้อน** or **รายงานแปลงของฉัน**, then **CSV**/**PDF**.

## Notes for coworkers
- **หมู่บ้าน / ตำบล** on your drawn fields are typed in manually (อำเภอ/จังหวัด default
  from the selected district); there is no open dataset for village.
- Stations, drawn fields, and edits are saved **in that person's own browser**
  (localStorage), not shared live. To share, use **⤓ แปลง** / **⤓ จุดรับซื้อ** to export
  GeoJSON and send the file (others load it via **📁 นำเข้า**).
