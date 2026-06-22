# Session Handoff — Sugarcane Field Manager (June 2026)

Continuation handoff for the work done in the June 2026 session. Read this **with**
the foundational [HANDOFF.md](HANDOFF.md) (project overview, pipeline, cloud model).
This doc = current state, what shipped, open threads, and the gotchas to know.

---

## 0. TL;DR — current state (updated 2026-06-22)

- **Production (live):** GitHub Pages from `origin` = `chatcharatth-13/sugarcane-fields` →
  `https://chatcharatth-13.github.io/sugarcane-fields/app/field_manager.html`.
  **`origin/main == master == e83bc9e`** (source of truth: `git rev-parse origin/main`).
- **Staging:** `chatcharatth-13/sugarcane-fields-staging` (app-only `git subtree split --prefix=app`,
  red TEST banner) → `…/sugarcane-fields-staging/field_manager.html`. Kept in sync each deploy.
- **🔒 The site is now PRIVATE (Google login gate).** Visitors see only "Sign in with Google";
  the app loads only for an **allowlisted** account. Owner = **`chatcharat.13@gmail.com`** (hardcoded
  `OWNER_EMAIL` in 3 places: the gate in `app/field_manager.html`, `app/manage_access.html`, and the
  Firestore rule's `isOwner()`). Anonymous auth is **disabled**. Allowlist lives in a Firestore
  **`allowed_users`** collection, managed self-serve at **`app/manage_access.html`** (owner signs in →
  add/remove emails → effective immediately, no redeploy).
  - **⚠️ ONE PENDING OWNER ACTION:** publish the Firestore rule in `docs/CLOUD_SETUP.md` §2
    (the `isOwner`/`isAllowed`/`allowed_users` version). Until it's published the admin page can't
    write the allowlist (owner still gets into the app via the hardcoded fallback; others blocked).
    A flat single-email allowlist rule IS currently published+working; the §2 rule is the upgrade
    that enables the admin page.
- **Firebase:** project `sugarcane-fields`, **Blaze**, Firestore + **Google** auth. Data isolation is
  by **workspace code** (no longer a security boundary — the rules are). Workspaces:
  - **`team-1`** — the real team data, **~4,567 fields** (mostly real hand-drawn polygons).
  - **`quota-2568`** — NEW this session: **4,340 fields**, imported from `~/Downloads/แยกโควต้า`
    (11 gov-form xlsx, 1 per quota holder), then **real polygons backfilled from `team-1` by exact
    coordinate** (3,514 multi-vertex + 826 hand-drawn quads/triangles; 0 placeholder squares left).
    11 quotas = the xlsx filenames; `depot` (folder) + `tons` kept as props.
- **Data: 39 districts** (was 23) across 5 provinces. `app/manifest.json` is the index; each district
  has `fields`/`hotspots`/`sugarcane_hotspots`/`patches` (any may be `null` for hotspots-only districts).
- **Burned area = REAL satellite burn-scar polygons**, not VIIRS 375 m boxes. Source file
  `raw/burnarea_2026.geojson` (= user's `~/Downloads/burnarea_2026_wgs84.geojson`, 13,851 nationwide
  polygons, gitignored). `prep_fields.py --burnarea` clips them per district → `burned_rai` + the
  `พื้นที่เผา` patches. **Burned numbers are now much lower but precise** (e.g. ban_phai 1200→370 ไร่,
  kumphawapi 6.7%→1.0%) — the old boxes overcounted. (If too conservative, a hybrid — real polygons
  for the map but hotspot-based per-field flag — is a quick `prep_fields` tweak + rerun.)

### What shipped THIS session (2026-06-22), newest → oldest
| Commit | What |
|---|---|
| `e83bc9e` | **Real burn-scar burned area (all 25)** + **Loei province (14 districts)** → 39 total. `prep_fields.py` gained `--burnarea` + a hotspots-only path (Loei isn't in our LDD land-use: 10 districts are hotspots-only, 4 got edge parcels). |
| `fc4c68f` | **🔥 Flag fields with a fire** — `fieldHasFire`/`allHotGrid`, per-field `_fire`, 🔥 table badge + map markers (`fireLayer`, toggle "แปลงมีไฟ") + tooltip. |
| `0ed64e6` | **Kumphawapi + Phen districts** (Udon Thani) → 25. |
| `5c4f8f5` | **Firestore-backed allowlist + `app/manage_access.html` admin page.** |
| `7b4116f` | **Google login gate** (`app/field_manager.html`) — replaces anonymous auth; the site is private. Allowlist rules. |
| `6b07b86` | Fix Leaflet layers control showing an empty 160px box when collapsed. |
| `3db6116` | **Field map context menu** (right-click / long-press: เปลี่ยนโควตา/ซูม/✂แบ่ง/ตัดออก-นำกลับ/ลบ) + light responsive hardening. |

### Open items
1. **Publish the §2 Firestore rule** (above) to activate `manage_access.html`. Only owner action left for the private-site work.
2. **🔑 Rotate the FIRMS `MAP_KEY`** — still exposed in this repo's public git history (now read from gitignored `.env`). Get a new key at firms.modaps.eosdis.nasa.gov/api/, put in `.env`, revoke the old.
3. **Sentinel-2 dNBR GEE script** (`scripts/burnscar_sentinel2.gee.js`) is now UNUSED — the user supplied a ready burn-scar file instead. Keep it for future seasons or drop it.
4. **Burned-area conservativeness** — confirm the new (much lower) burned numbers are acceptable, or switch to the hybrid.
5. **826?** — n/a now (all quota-2568 fields have real polygons). Loei has no field parcels (would need Loei LDD land-use).
6. Housekeeping: leftover `test-quota-*` Firestore workspaces (throwaway); `tools/quota_2568_*` + `raw/burnarea_2026.geojson` are gitignored/untracked by design.

---

## 1. Deploy model (important — how the two sites work)

- **One Firebase project, two GitHub Pages sites.** Editing data on *either* site writes to the
  same Firestore, **scoped by workspace code**. So "test on staging with live data" means: clone
  the live workspace into a `staging-…`/`test-…` workspace and open staging with `#ws=that-code`
  — **never** point a write-feature on staging at `#ws=team-1` (that edits production data).
- **Production deploy:** `git push origin master:main` (Pages serves `origin/main`'s `app/`).
  Local default branch is `master`; origin's default is `main` — they track each other.
- **Staging deploy (app-only, secret-free):**
  ```
  git branch -D staging-deploy 2>/dev/null
  git subtree split --prefix=app -b staging-deploy
  git push staging staging-deploy:main --force
  ```
  Only `app/` goes to staging (so `scripts/`, the FIRMS key, etc. never land in that public repo).
- **Remotes:** `origin` → `chatcharatth-13/sugarcane-fields` (production, full repo),
  `staging` → `chatcharatth-13/sugarcane-fields-staging` (app-only). A third remote
  `cnicolaz13/fields_mananger` exists but is not ours to push.
- **Env gotcha:** `gh` CLI is **not installed** and there's no GitHub token. `git push` works via
  the credential manager; creating repos must be done in the GitHub web UI. No `firebase` CLI.
  Python 3.14 is present but **lacks `openpyxl`** and `earthengine-api` (read xlsx via zip/XML; GEE
  runs in the browser Code Editor). On Windows, run Python with `PYTHONUTF8=1` for Thai output.

---

## 2. What shipped this session (newest → oldest)

All on `master`; all but `e03eca5` are in `origin/main` (production).

| Commit | What |
|---|---|
| `e03eca5` | GEE burn-scar script: drop debug prints (AOI resolves 5 provinces). **Not pushed to origin.** |
| `4419086`,`67eda11`,`6c608a5`,`497ddd4` | `scripts/burnscar_sentinel2.gee.js` — Sentinel-2 dNBR burn-scar script + fixes (see §5). |
| `b8b97af` | **Phase 2: in-app quota rebalance** (⇄ ย้ายโควตา) + per-quota fill numbers. |
| `ce95a76` | `tools/reassign_quota_from_excel.html` (the Book1.xlsx fix tool). |
| `6e55d97` | **เมืองชัยภูมิ (Mueang Chaiyaphum) district** added (manifest now 23 districts) + **quota filter → multi-select**. |
| `7486743` | Fix merge-on-join **duplicating** cloud fields + `tools/dedupe_workspace.html`. |
| `cae92d7` | Pre-deploy hardening: `afterStationChange` uses `setTimeout` not `requestAnimationFrame`. |
| `36c6d71` | Fields-table **filter + sort bar**. |
| `192b299` | **Performance at scale**: in-place row updates, lazy dropdowns, content-visibility, spatial burn index (~40× faster single edit, ~31× faster burn at 2,000 fields). |
| `c2101b8` | Safety quick-wins: draw-trash delete confirm+restore, merge-or-discard on cloud join, aria-labels + `:focus-visible`, CSV/PDF export row counts. |
| `858e946` | Fix overlapping 2-row sticky header in the fields table. |
| `46d19a6` | Redesign stats bar → grouped KPI strip. |
| `71a9127` | Redesign toolbar → labeled cluster menus (กรอง / ชั้นข้อมูล / แก้ไข / ข้อมูล / cloud). |
| `f295d59`,`a01673c` | Lock stations (non-draggable), saved-views (มุมมอง) menu, `tools/clone_workspace.html`; **FIRMS key → `.env`**. |

A full UX review (multi-agent, code-grounded) was run mid-session: overall **6/10**; most of its
P0/P1 findings (safety, performance, filter/sort) were implemented. Remaining review items: map
legend + non-color burn cue, collaboration visibility (last-edited-by/presence), locate-from-search.

---

## 3. Maintenance tools (`tools/` — local only, NOT deployed to the live site)

Run them by serving the repo root over HTTP (`python -m http.server 8000`) and opening
`http://localhost:8000/tools/<file>`. They use anonymous Firebase auth + the same `app/firebase-config.js`.

- **`clone_workspace.html`** — copy a workspace (read source, write a `staging-`/`test-`/`backup-` dest only). Use for backups and for seeding staging test data.
- **`dedupe_workspace.html`** — remove exact-geometry **duplicate** field docs (keep oldest per group). Preview-first, backup-gated. (Used once: `team-1` 4336 → 2172 after the merge bug duplicated fields.)
- **`reassign_quota_from_excel.html`** — match an Excel/CSV's **X/Y coordinates** to field docs and reassign their quota. Robust to the official gov-form layout (2-row header, skip form-header rows). Preview-first, backup-gated, fresh-read on apply. (Used once: moved 151 เจ้หมวย overflow fields → อภิพล in `team-1`.)

**Round-trip rule (applies to all of these and any future import):** match fields by `_uid`
(exact) or **lon/lat coordinate** (±~1e-5). **Never** by `แปลงที่` / `field_id` — that number is
re-sequenced in exports and is per-browser internally.

---

## 4. Data incidents resolved this session

- **Duplication:** the original merge-on-join re-uploaded all local fields without deduping →
  `team-1` doubled to 4336 docs. Fixed the merge logic (now skips fields whose geometry already
  exists in the cloud, `7486743`) and cleaned up with `dedupe_workspace.html` → back to **2172** real fields.
- **Quota overfill:** the 151 fields in the user's `Book1.xlsx` (quota เจ้หมวย overflow) were
  reassigned to **อภิพล** by X/Y match (151/151 matched). Backup `backup-quota-20260620` + a
  `reassign_undo.json` were produced.

---

## 5. Sentinel-2 burn-scar pipeline (in progress)

The user wants **actual burn-scar polygons** (their current "พื้นที่เผา" are just VIIRS 375 m pixel
footprints clipped to sugarcane — `prep_fields.py` lines ~60-86). Chosen source: **Sentinel-2 dNBR**.

- **Script:** `scripts/burnscar_sentinel2.gee.js` — runs in the **Google Earth Engine Code Editor**
  (code.earthengine.google.com), not locally. Computes dNBR (pre-season NBR − post-season NBR),
  thresholds (`THRESH=0.27`, tunable), vectorizes to polygons with `area_rai`, exports GeoJSON to Drive.
  Region = the 5 provinces; season Nov 2025 (pre) vs Apr–May 2026 (post), from the FIRMS date range.
- **Status:** the user got GEE access (EE API enabled on the `sugarcane-fields` Cloud project,
  noncommercial). The script's **AOI now resolves all 5 provinces** (Nong Bua Lamphu is matched by
  `ee.Filter.stringContains('ADM1_NAME','Nong Bua')` since GAUL's spelling differed). Several
  beginner snags were fixed: `reduceColumns` not `aggregate_*` (JS vs Python API), `Map.setCenter`
  not `Map.centerObject` (centroid/maxError quirk), and stale-paste confusion (must `Ctrl+A` →
  delete → paste the whole file). The debug prints were removed in `e03eca5`.
- **Next:** user runs the script → runs the `burnscar_2025_26` export task → hands the resulting
  GeoJSON back. Then integrate: in `prep_fields.py`, feed the burn-scar polygons into the existing
  field∩fire intersection (replacing the 375 m pixel boxes) → real `burned_rai`, real
  `<prefix>_burned_patches.geojson`. Later, update the app's runtime `fieldBurned()` for user-drawn
  fields to test field∩burn-scar instead of hotspot-point-in-polygon.

---

## 6. Open / in-flight items (prioritized)

1. **⚠️ Phase 2 rebalance is live in production but never got the staging live-data test.** It's
   verified-working code (move/undo/fill/scope all passed locally), so this is "validate or accept",
   not "broken". Decide: validate on a `team-1` clone via staging, or accept as-is.
2. **🔑 Rotate the FIRMS MAP_KEY** — still the one open security item. The old key
   (`scripts/run_districts.py` history) is in the **public** git history of `sugarcane-fields`, so
   it's permanently exposed. It's now read from `.env` (gitignored; `.env.example` is the template),
   but moving it doesn't scrub history. Get a new key at firms.modaps.eosdis.nasa.gov/api/, put it in
   `.env`, revoke the old one.
3. **Burn scars (§5)** — waiting on the user's GEE export, then the `prep_fields.py` integration.
4. **Quota overfill — Phases 3–4 (planned, not built).** Phase 1 (Excel reassign tool) and Phase 2
   (in-app rebalance) are done. Remaining: Phase 3 = per-quota **capacity** (ตัน/ไร่, editable yield
   ~10 ตัน/ไร่) + fill bars + **auto-detect overflow** + confirm; Phase 4 = native `.xlsx` export with
   a hidden `_uid` column + persistent undo. Decisions already made by the user: cap configurable in
   tons or rai; auto-detect overflow then confirm; support both in-app + Excel re-import. `quotaFillAll()`
   (count + ไร่ per quota) already exists from Phase 2 as the groundwork.
5. **Remaining UX-review items:** non-color burn cue + on-map legend; collaboration visibility
   (created_by/edited_by are stored but never shown); locate-a-field from the 🔎 search → scroll/flash its table row.

---

## 7. Quota model (changed this session — read before touching quotas)

- Filter is now **multi-select**: `quotaSel` is `'ALL'` or a `Set<qid>`; `passQuota` checks a cached
  `_selKeys` set; `activeQuotaObj()` returns a single quota **only when exactly one is selected**
  (so draw-auto-join and 🏷 assign mode stay single-quota). Persisted as JSON in `fm:activeQuota`
  (with legacy single-value fallback); validated against existing quotas on cloud load.
- **Rebalance (Phase 2):** `⇄ ย้ายโควตา` toolbar menu → `renderRebalance`/`doRebalance`/`undoRebalance`,
  source/target quota + scope (all-in-source vs shown-in-table via `fieldVisible`), one-level undo
  (`lastReassign`). Reuses `setFieldQuota` + `persistFields` (the `doBulkAssign` tail).
- A field belongs to a quota via `quota_name` + `quota_number` (key `"name#number"`). The 8 `team-1`
  quotas: เจ้หมวย, อรรณพ, ชัชรัสย์, ประชิด, ทรงวิทย์, สุภาภรณ์, อภิพล, วันชัย.

---

## 8. Performance notes (the app is tuned for ~2,000+ fields)

- The fields table does **in-place single-row updates** (`buildFieldRow`/`updateFieldRow`/
  `removeFieldRow` + `refreshFieldFooter`), **lazy-populated** village/tambon/quota `<select>`s
  (filled on `focusin`), and `content-visibility:auto` rows. Do **not** reintroduce a full
  `buildFieldsTable()` on single edits.
- Burn detection uses a **spatial hash-grid** over `scHotFeatures` (`buildScHotIndex`, `SC_CELL=0.01`).
  Invalidate it (`scHotGrid=null`) whenever `scHotFeatures` changes.
- The fields table filter/sort lives in `fldFilter`/`fldSort`; `fieldVisible(f)=passQuota(f)&&passFieldFilter(f)`
  drives the table, footer, bulk scope, and in-place updates (map polygons + KPI stats stay on the quota filter only).

---

## 9. How to verify + deploy (the loop used all session)

1. Serve locally: `python -m http.server 8000` from the repo root → `http://localhost:8000/app/field_manager.html`
   (file:// can't `fetch`). The dedicated preview tooling reads `.claude/launch.json` (config name `sichomphu`).
2. Verify with browser tools (no console errors; exercise the changed flow). For data-volume tests,
   inject synthetic fields/hotspots via `eval` and clear `fm:*` localStorage after.
3. Commit on `master` → `git push origin master:main` (production) → `git subtree split`+force-push to `staging`.
4. GitHub Pages rebuilds in ~1–2 min; verify with a cache-busted `WebFetch` (note: WebFetch strips
   `<script>` and HTML attributes, so confirm JS-only changes against `git show origin/main:app/...`).

*Maintained for the next context. The single source of truth for live state is
`git rev-parse origin/main` + this doc's §0.*
