# Deploying the Sugarcane Field Manager

The whole web app lives in **`app/`** and is self-contained:
```
app/
├── field_manager.html     the app
├── manifest.json          district list (paths are relative: "data/...")
├── th_adm3.geojson        runtime tambon/อำเภอ/จังหวัด auto-detect + dropdowns
└── data/                  per-district geojson the app fetches (one set per district)
```
It reads `manifest.json` and, per district, fetches that district's
`*_fields_enriched`, `*_hotspots`, `*_sugarcane_hotspots`, `*_burned_patches`
from `data/`. Only the selected district loads, so the per-visitor footprint is small.

## 0. (Re)generate the data
Run from the **project root** after any pipeline change:
```bash
python scripts/enrich_fields.py
```
This reads `work/*_fields.geojson` + `app/data/*_hotspots.geojson` and (re)writes
`app/data/*_fields_enriched.geojson` and `app/manifest.json`, adding
ตำบล / อำเภอ / จังหวัด (Thai, from `app/th_adm3.geojson`) and X/Y coordinates.

## What to deploy
Upload the **entire `app/` folder** (html + manifest + th_adm3 + villages.json +
data/ + `firebase-config.js`). Nothing else is needed. The dropdown is
manifest-driven, so adding districts just means re-running the pipeline +
`enrich_fields.py`, then re-uploading `app/`.

## Shared cloud autosave (optional)
By default the app saves per-browser (localStorage). To let a team share one live,
auto-saving dataset, set up Firebase (free) and connect via the **☁** button — see
**[CLOUD_SETUP.md](CLOUD_SETUP.md)**. With Firebase, **Firebase Hosting** is the
simplest host (`firebase init hosting` pointing at `app/`, then `firebase deploy`);
GitHub Pages also works if you add the Pages domain to Firebase Authorized domains.

## What to NEVER deploy
- `raw/` — LDD land-use + downloaded admin boundaries (hundreds of MB, prep-only)
- `work/` — `*.gpkg`, intermediate `*_fields.geojson`, summaries, quick-look maps
- `scripts/`
`.gitignore` keeps `raw/` and the heavy parts of `work/` out of git entirely.

## Option A — GitHub Pages (share a URL)
```bash
cd C:/Users/WINDOWS/Downloads/sichomphu_project
git add -A && git commit -m "Sugarcane field manager"
gh repo create sugarcane-fields --public --source=. --push
```
Then on GitHub: **Settings → Pages → Branch: main / root → Save**.
The URL will be `https://<you>.github.io/sugarcane-fields/app/field_manager.html`.

## Option B — Netlify (drag & drop, no git)
1. Go to https://app.netlify.com/drop and drag the **`app/`** folder in.
2. Share the generated URL (append `/field_manager.html`).

## Run locally (for editing / offline)
The app must be served over HTTP (file:// can't `fetch`):
```bash
python -m http.server 8000        # run from the project root
# open http://localhost:8000/app/field_manager.html
```

## How the app works (v2)
- **Primary data = hotspots.** The LDD `*_fields_enriched.geojson` are an *optional
  reference* layer (off by default) — they are NOT anyone's real fields.
- **Buying stations (จุดรับซื้อ):** click **➕ จุดรับซื้อ** then click the map to drop a
  station; set a **radius (กม.)** per station. Hotspots/fields are tagged by the
  station whose radius contains them, and **เฉพาะในรัศมี** filters to inside-radius only.
- **Your real fields:** draw them with the polygon tool (top-left). A field is marked
  **เผา/ไม่เผา** by whether a sugarcane hotspot falls inside it.
- **Quotas (โควตา):** the **โควตา ▾** menu manages a list of quotas (ชื่อ + เลขโควตา) and
  picks the active one. New fields you draw auto-join the active quota; **🏷 ผูกโควตา**
  lets you click existing fields onto it; each field row also has a quota dropdown.
  Selecting a quota shows only its fields (color-coded border); **ทั้งหมด** shows all.
  Reports gain a **โควตา** column and respect the filter.
- **Find a place:** the **🔎 ค้นหาสถานที่** box searches ตำบล/อำเภอ/จังหวัด (offline) + your
  stations/fields; if nothing matches it falls back to an online geocoder (needs internet).
- **Multi-district:** tick several อำเภอ in the dropdown to combine their hotspots.
- **Import:** **📁 นำเข้า** loads any GeoJSON — points → hotspots, polygons → your
  fields, points with `radius_km` → stations (e.g. another district's hotspots).
- **Two reports:** pick **รายงานจุดความร้อน** or **รายงานแปลงของฉัน**, then **CSV**/**PDF**.

## Village (หมู่บ้าน) dropdown — `app/villages.json`
ตำบล / อำเภอ / จังหวัด are auto-detected for each drawn field; the **หมู่บ้าน** cell is a
dropdown filtered to that exact location. `app/villages.json` **ships with 7,853
villages** across the 5 working provinces (Khon Kaen, Chaiyaphum, Nong Bua Lamphu,
Udon Thani, Maha Sarakham), built from DOPA's open dataset (data.go.th `gis-01`),
which matched `th_adm3` names 100%. You can also type a village to add one
(remembered per location in the browser).

**Rebuild / extend it** (e.g. add provinces — edit `PROVINCES` in the script):
```bash
python scripts/build_villages.py     # downloads DOPA village data -> app/villages.json
```
The file is a plain JSON array; both key spellings are accepted if you hand-edit:
```json
[
  {"changwat":"ขอนแก่น","amphoe":"สีชมพู","tambon":"วังเพิ่ม","village":"บ้านวังเพิ่ม"},
  {"province":"ขอนแก่น","district":"สีชมพู","subdistrict":"วังเพิ่ม","name":"บ้านโนนทอง"}
]
```
Deploy it alongside `app/manifest.json`. Names must match the Thai ตำบล/อำเภอ/จังหวัด
spelling from `th_adm3.geojson` (the build script validates this).

## Notes for coworkers
- Without `villages.json`, the หมู่บ้าน dropdown **builds itself** — type a village once
  for a given ตำบล and it becomes a reusable option there.
- Stations, drawn fields, and edits are saved **in that person's own browser**
  (localStorage), not shared live. To share, use **⤓ แปลง** / **⤓ จุดรับซื้อ** to export
  GeoJSON and send the file (others load it via **📁 นำเข้า**).
