"""
Per-district field-area analysis + report, for every district.

Run AFTER run_districts.py (which gathered <prefix>_hotspots.gpkg for each)
and make_sugarcane.py (sugarcane.gpkg covering all provinces).

    python run_reports.py

For each district it runs prep_fields.py then build_report.py, producing:
  <prefix>_fields.geojson / _sugarcane_hotspots.geojson / _burned_patches.geojson
  <prefix>_sugarcane_fields.gpkg
  <prefix>_report.html      <- the shareable report
"""
import subprocess, sys, os

# (output prefix, district-name substring) -- keep in sync with run_districts.py
DISTRICTS = [
    ("sichomphu",     "chomphu"),       # Khon Kaen (the original)
    ("si_bun_rueang", "bun ru"),        # Nong Bua Lamphu
    ("phu_wiang",     "phu wiang"),     # Khon Kaen
    ("kaeng_khro",    "kaeng kh"),      # Chaiyaphum
    ("phu_pha_man",   "pha man"),       # Khon Kaen
    ("ban_phai",      "ban phai"),      # Khon Kaen
    ("phu_khiao",     "phu khi"),       # Chaiyaphum
    ("chum_phae",     "chum ph"),       # Khon Kaen
    ("waeng_yai",     "waeng yai"),     # Khon Kaen
    ("waeng_noi",     "waeng noi"),     # Khon Kaen
    ("suwannakhuha",  "suwan"),         # Nong Bua Lamphu
]

failed = []
for prefix, match in DISTRICTS:
    if not os.path.exists(f"{prefix}_hotspots.gpkg"):
        print(f"\n-- {prefix}: no {prefix}_hotspots.gpkg yet (run run_districts.py first); skipping")
        failed.append(prefix); continue
    print(f"\n============== {prefix} ==============")
    ok = subprocess.run([sys.executable, "prep_fields.py",
                         "--district", match, "--prefix", prefix]).returncode == 0
    if ok:
        ok = subprocess.run([sys.executable, "build_report.py",
                             "--prefix", prefix]).returncode == 0
    if not ok:
        failed.append(prefix)

print("\n=================== done ===================")
if failed:
    print("issues with:", ", ".join(failed))
print("Open each <prefix>_report.html, or load <prefix>_fields.geojson etc. in field_picker.html")
