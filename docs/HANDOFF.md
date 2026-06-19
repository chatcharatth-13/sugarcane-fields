# Sugarcane Field Manager — Project Handoff

A web app + data pipeline to map sugarcane fields and fire **hotspots** across
Northeast Thailand, so the team can locate the **not-burned** sugarcane fields that
supply each **buying station**, group them by **quota**, and produce reports. Built
as a single static HTML app backed by Firebase for shared, real‑time multi‑user use.

- **Live site:** GitHub Pages under `chatcharatth-13.github.io` (the `app/` folder).
- **Repo:** this project; remote `origin` → `github.com/chatcharatth-13/sugarcane-fields`.
- **Status:** 22 districts loaded; cloud collaboration working (per‑field documents).

This document has four parts: **A. Technical maintenance · B. User guide · C.
Limitations & roadmap · D. Credentials & ops notes.** See also the focused docs:
[README.md](../README.md), [DEPLOY.md](DEPLOY.md), [CLOUD_SETUP.md](CLOUD_SETUP.md),
[SETUP.md](SETUP.md).

---

## Repository layout
```
app/                 ← the deployable web app (this whole folder is the site)
  field_manager.html   the entire app (one self-contained file, ~1200 lines)
  manifest.json        the district list the app reads (22 districts)
  th_adm3.geojson      Thai tambon/amphoe/changwat boundaries (runtime auto-detect, 7 MB)
  villages.json        ~7,853 village names + coords (DOPA, 5 provinces)
  firebase-config.js   Firebase web config (pasted by the owner; public-safe)
  data/                per-district GeoJSON the app fetches (4 files × 22 districts)
scripts/             ← the data pipeline (Python; run from the repo ROOT)
work/                ← intermediates: *.gpkg (gitignored), *_fields.geojson, summaries
raw/                 ← heavy inputs: landuse/ (LDD shapefiles) + admin boundaries (gitignored)
docs/                ← README/DEPLOY/CLOUD_SETUP/SETUP/how_to_run + this file
archive/             ← field_picker.html (the original single-district prototype)
```

---

# PART A — Technical maintenance

## A1. The web app — `app/field_manager.html`
One self-contained file: HTML + CSS + vanilla JS, using **Leaflet** (map) +
**leaflet-draw** (polygons) + **Turf.js** (geometry) + **html-to-image** + **jsPDF**
(exports) + **LZ-string** (cloud compression) + **Firebase** (loaded dynamically).
No build step. Major in-file modules (search by these names):

| Area | Key functions / state |
|---|---|
| Map & layers | `map`, `baseLayers`, `scHotLayer/allHotLayer/burnLayer/ldLayer`, `myFieldsLayer`, `stationsLayer` |
| Districts | `manifest.json` → `DISTRICTS`; `districtCheckboxes()` (searchable, province‑grouped), `setDistricts()` |
| Hotspots | `scHotFeatures/allHotFeatures`, `renderHotspots()`, `loadHotspots` via `setDistricts` |
| Stations | `stations` Map, `addStation()`, `stationOf()`, `afterStationChange()`, radius circles + tagging |
| My fields | `myFields` Map (key = local `field_id`), `addFieldToMap()`, `L.Draw.Event.CREATED/EDITED`, `performSplit()` |
| Admin auto-detect | `loadADM3()` (lazy 7 MB), `detectAdmin()` (point-in-polygon), `tambonSelect()` |
| Villages | `villagesByLoc`/`villagePtsByLoc`, `villageSelect()`, `nearestVillage()`, `loadVillagesFile()` |
| Quotas | `quotas` Map, `addQuota()`, `assignQuotaToField()`, `bulkScopeFields()`/`doBulkAssign()`, `quotaColor()` |
| Duplicate block | `overlapsExisting()` (Turf intersect > 10% of smaller area; bbox pre-filter) |
| Reports | `hotspotReportRows()`, `fieldReportRows()`, `expCSV`/`expPDF`, map export `captureMap()`/`doMapExport()` |
| Search | `parseCoord()`, `gotoCoord()`, `searchOffline()` (th_adm3 + stations/fields), `searchOnline()` (Nominatim) |
| Persistence | `persistFields()`/`persistStations()`/`persistQuotas()` (localStorage) + cloud (A4) |
| Cloud | `initCloud()`, `fieldSyncNow()`, `applyRemoteFieldDoc()`, `metaDoc()`, `cz()`/`cloudParse()` |

**Data the app reads at runtime** (all under `app/`, fetched relative to the HTML):
`manifest.json`, `th_adm3.geojson`, `villages.json`, and per‑district files from
`data/`. `manifest.json` is fetched with `cache:'no-store'` so new districts appear
without a hard refresh.

## A2. Data pipeline — `scripts/` (run from the repo ROOT)
Install once: `pip install -r requirements.txt` (pandas, geopandas, shapely,
requests, folium; geopandas needs GDAL — conda‑forge is easiest on Windows).

Flow (each step writes the inputs of the next):
1. **`make_sugarcane.py`** — `raw/landuse/*.shp` (LDD land‑use) → `work/sugarcane.gpkg`
   (all sugarcane parcels). Currently covers **Khon Kaen, Chaiyaphum, Nong Bua
   Lamphu, Udon Thani, Maha Sarakham**.
2. **`run_districts.py`** → calls **`firms_sichomphu.py`** per district — downloads
   NASA **FIRMS VIIRS** fire detections (needs a MAP_KEY, see Part D), clips to the
   district, tags sugarcane → `work/<prefix>_hotspots.gpkg`, `_sugarcane_hotspots.gpkg`,
   `_summary.csv`, `_map.html`.
3. **`run_reports.py`** → calls **`prep_fields.py`** per district — clips sugarcane to
   the district, measures **burned vs not‑burned** area via the VIIRS pixel footprint →
   `work/<prefix>_fields.geojson` (+ .gpkg) and `app/data/<prefix>_{hotspots,
   sugarcane_hotspots,burned_patches}.geojson`.
4. **`enrich_fields.py`** — adds Thai **tambon/amphoe/changwat** (point‑in‑polygon vs
   `app/th_adm3.geojson`) + lon/lat → `app/data/<prefix>_fields_enriched.geojson` and
   rebuilds **`app/manifest.json`**.
5. **`build_villages.py`** — downloads DOPA village data (data.go.th `gis-01`) for the
   working provinces, validates names against `th_adm3`, writes **`app/villages.json`**
   (names + coords). Re‑run only when adding provinces.

`build_report.py`/`diag.py`/`run.sh` are legacy helpers (not required).

## A3. Adding a district (the common task)
This has been done ~12 times; the pattern:
1. Find the district's **geoBoundaries romanized name** (e.g. "Ban Thaen") and a unique
   substring. Add one row to the `DISTRICTS` list in **both**
   `scripts/run_districts.py` and `scripts/run_reports.py`:
   `("ban_thaen", "ban thaen"),  # Chaiyaphum`.
   ⚠️ Use a substring specific enough to avoid collisions (e.g. use `khok pho chai`,
   not `khok pho`, which also matches Khok Pho in Pattani).
2. Run for that district (FIRMS key is in `run_districts.py`):
   ```bash
   python scripts/firms_sichomphu.py --mode api --map-key <KEY> --district "ban thaen" --sugarcane work/sugarcane.gpkg --out-prefix ban_thaen
   python scripts/prep_fields.py    --district "ban thaen" --prefix ban_thaen
   python scripts/enrich_fields.py
   ```
   Check the printed **"matched district:"** line is the right one.
3. **Redeploy** `app/manifest.json` + the new `app/data/<prefix>_*` files (A5).
- **New province** (not one of the 5 covered): also drop that province's LDD land‑use
  folder into `raw/landuse/` and re‑run `make_sugarcane.py` first, else the district has
  no sugarcane parcels (you'd get all‑fire hotspots only).

## A4. Cloud sync — Firebase Firestore (shared workspace)
Default is **offline** (localStorage). When a **workspace code** is entered (☁ button)
and `firebase-config.js` is set, the app uses Firebase for **shared, real‑time,
auto‑saving** collaboration. Setup steps + Firestore rules: **[CLOUD_SETUP.md](CLOUD_SETUP.md)**.

**Model (important):**
- **Stations + quotas** → the single doc `workspaces/{ws}` (compressed JSON strings;
  whole‑doc, last‑write‑wins).
- **Fields** → **one document each** at `workspaces/{ws}/fields/{uid}` — so two people
  drawing at once never collide and there's no 1 MB ceiling. Each field has a stable
  `_uid`; `field_id` is just a local display number.
- **Auth:** anonymous; access gated by the **workspace code** (an unguessable shared
  string in the `#ws=` link). **Firestore rule must be recursive:**
  `match /workspaces/{ws}/{document=**} { allow read, write: if request.auth != null; }`
- **Sync:** outgoing is diff‑based (`fieldSyncNow` writes only changed/added/removed
  field docs, debounced); incoming uses per‑collection `onSnapshot` reconciled by `uid`.
  Old single‑doc workspaces auto‑migrate into the fields subcollection on first connect.
- Verified end‑to‑end against the live project: concurrent two‑user writes (no loss),
  delete, fresh‑client load, and migration all pass.

## A5. Deployment
The whole **`app/`** folder is the site. Deploy by pushing to the GitHub repo that
serves `chatcharatth-13.github.io` (remote `origin` = `sugarcane-fields`), then
**hard‑refresh** (Ctrl+Shift+R). Full steps + Firebase‑Hosting alternative:
**[DEPLOY.md](DEPLOY.md)**.
- **Adding a district** = redeploy `app/manifest.json` + that district's
  `app/data/<prefix>_*` files. Simplest foolproof move: **re‑upload the whole `app/`
  folder** every time so you never miss a file.
- For the cloud to work on the live domain, that domain must be in Firebase **Auth →
  Authorized domains**, and the Firestore rule must be the recursive one above.

---

# PART B — User guide (for the field team)

Open the site, then:
- **Pick district(s):** the **อำเภอ ▾** menu — type in its search box to filter; tick one
  or several (grouped by จังหวัด). The map loads that district's sugarcane fire hotspots.
- **Find a place:** the **🔎** box. Type a ตำบล/อำเภอ/จังหวัด name, a station/field name,
  or **coordinates** like `16.0497, 102.9496` → it jumps there and drops a pin (the pin
  has a **✕ ลบหมุด** button to remove it).
- **Buying stations:** **➕ จุดรับซื้อ** then click the map to drop one. In the
  **จุดรับซื้อ** tab set its **name** and **radius (กม.)**. Hotspots/fields get tagged to
  the station whose circle contains them; **เฉพาะในรัศมี** filters to inside‑radius only.
- **Quotas (โควตา):** the **โควตา ▾** menu creates quotas (ชื่อ + เลขโควตา) and picks the
  active one. New fields you draw join it automatically; **🏷 ผูกโควตา** lets you click
  existing fields onto it; each field row has a quota dropdown; and the **แปลงของฉัน**
  tab has a **bulk** bar ("ทุกแปลงที่แสดง" or "เฉพาะอำเภอที่เลือก") to assign many at once.
  Selecting a quota shows only its fields (colored border); **ทั้งหมด** shows all.
- **Draw your fields:** the polygon tool (top‑left). On finishing, the row auto‑fills
  ตำบล/อำเภอ/จังหวัด and the **nearest village**; **หมู่บ้าน/ตำบล** are correctable
  dropdowns. A field is **เผา/ไม่เผา** by whether a sugarcane hotspot falls inside it.
  Drawing a field that **overlaps an existing one is blocked** (prevents duplicates).
- **Reports:** choose **รายงานจุดความร้อน** or **รายงานแปลงของฉัน**, then **CSV** or **PDF**.
  **🗺 ภาพแผนที่** exports the map as PNG/PDF (current view / all / stations).
- **Import / export:** **📁 นำเข้า** loads GeoJSON (points→hotspots, polygons→your fields
  with duplicates auto‑skipped, points with `radius_km`→stations). **⤓ แปลง / ⤓ จุดรับซื้อ**
  export your data as GeoJSON.
- **Work together online:** **☁** → type the **same workspace code** + your name →
  **เชื่อมต่อ**. Everyone on that code sees and edits the same data, live and auto‑saved.
  Without a code, your work saves only in your own browser.

---

# PART C — Limitations & roadmap

**Known limitations**
- **Stations & quotas are not per‑document** — they share one workspace doc with
  last‑write‑wins. Two people adding a *station* at the same second could lose one.
  (Fields are safe.) → *Next: move stations/quotas to per‑document like fields.*
- **No open village polygons** — `villages.json` (DOPA) gives village **names + a point**
  per tambon, used for the dropdown + "nearest village" suggestion; there's no village
  boundary, so หมู่บ้าน is a best‑effort default you can change.
- **Field display number (แปลงที่ N) is per‑browser** — the same field can show a
  different number to different users; the field itself is identical.
- **Workspace‑code security is "shared link"** — anyone with the code can edit. Fine for
  a trusted team with a long random code. → *Next: Google sign‑in to attribute/limit edits.*
- **Duplicate blocking is overlap‑based** (>10% of the smaller polygon), so legitimately
  adjacent fields are allowed; near‑duplicates that don't overlap aren't caught.
- **Data caveats:** FIRMS science‑quality (SP) lags ~2–3 months (recent weeks need NRT);
  a VIIRS pixel is a 375 m footprint, not an exact burn outline; geoBoundaries name
  matching can hit the wrong district — always check the "matched district" line.
- **Provinces covered for sugarcane:** only the 5 with LDD land‑use in `raw/landuse/`.

**Recommended next steps**
1. Per‑document stations/quotas (removes the last concurrency gap).
2. Google sign‑in (tighter access + who‑edited attribution).
3. Move the FIRMS key out of source (env var / prompt) and rotate it (Part D).
4. Optional: slim `th_adm3.geojson` to the working provinces to cut the 7 MB load.

---

# PART D — Credentials & operations notes

**Secrets / keys (where they live — values not reproduced here):**
- **FIRMS MAP_KEY** is hard‑coded in `scripts/run_districts.py` (and passed to
  `firms_sichomphu.py`). It is **committed to the repo** → if the repo is public,
  **rotate it** (get a new key at firms.modaps.eosdis.nasa.gov/api/) and ideally read it
  from an environment variable instead of source.
- **Firebase web config** is in `app/firebase-config.js`. A Firebase web apiKey is **not
  a secret** (safe to ship); security comes from the **Firestore rules + workspace code**.
  Keep the recursive rule (A4/CLOUD_SETUP) and consider Google sign‑in later.
- **Firebase project:** `sugarcane-fields` (owner's Google account). Firestore +
  Anonymous Auth enabled; the hosting domain is in Authorized domains.

**Operational gotchas**
- After any data/code change, **redeploy `app/`** and **hard‑refresh**. `manifest.json`
  is fetched no‑store, but the HTML and `data/` files can be cached by the browser/CDN.
- **Firestore rule must be** `match /workspaces/{ws}/{document=**}` — without `/{document=**}`
  the per‑field subcollection is denied ("Missing or insufficient permissions").
- If Firestore was created in **test mode**, those rules **expire (~30 days)** — switch to
  the permanent rule in CLOUD_SETUP.
- **Git remotes:** `origin` → `chatcharatth-13/sugarcane-fields` (yours). A second remote
  `cnicolaz13/fields_mananger` exists but you can't push to it (different owner). Deploy
  from `origin`.
- **Local dev:** serve over HTTP (`python -m http.server` from the repo root, open
  `/app/field_manager.html`) — `file://` can't `fetch`. The dev server occasionally needs
  restarting; this does not affect the deployed site.
- **Line endings:** Git may warn LF→CRLF on Windows — harmless.

---

*Maintained alongside the code. When you change the pipeline, the cloud model, or
deployment, update the relevant section here.*
