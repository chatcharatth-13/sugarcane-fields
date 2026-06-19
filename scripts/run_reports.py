"""
Per-district field-area analysis + report, for every district.

Run AFTER run_districts.py (which gathered work/<prefix>_hotspots.gpkg for each)
and make_sugarcane.py (work/sugarcane.gpkg covering all provinces).

    python scripts/run_reports.py

For each district it runs prep_fields.py, producing:
  work/<prefix>_fields.geojson + work/<prefix>_sugarcane_fields.gpkg
  app/data/<prefix>_{hotspots,sugarcane_hotspots,burned_patches}.geojson
Then run scripts/enrich_fields.py to build app/data/*_enriched + app/manifest.json.
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
    # --- added districts (sugarcane covered) ---
    ("khok_pho_chai", "khok pho chai"), # Khon Kaen
    ("khon_san",      "khon san"),      # Chaiyaphum
    ("kaset_sombun",  "kaset sombun"),  # Chaiyaphum
    ("mancha_khiri",  "mancha khiri"),  # Khon Kaen
    ("na_klang",      "na klang"),      # Nong Bua Lamphu
    # --- added districts (Udon Thani / Maha Sarakham: all-fires only until
    #     their LDD land-use is added to landuse/ + make_sugarcane.py rerun) ---
    ("nam_som",       "nam som"),       # Udon Thani
    ("nong_wua_so",   "nong wua"),      # Udon Thani
    ("kut_chap",      "kut chap"),      # Udon Thani
    ("ban_phue",      "ban phue"),      # Udon Thani
    ("kut_rang",      "kut rang"),      # Maha Sarakham
]

HERE = os.path.dirname(os.path.abspath(__file__))   # scripts/

failed = []
for prefix, match in DISTRICTS:
    if not os.path.exists(os.path.join("work", f"{prefix}_hotspots.gpkg")):
        print(f"\n-- {prefix}: no work/{prefix}_hotspots.gpkg yet (run run_districts.py first); skipping")
        failed.append(prefix); continue
    print(f"\n============== {prefix} ==============")
    ok = subprocess.run([sys.executable, os.path.join(HERE, "prep_fields.py"),
                         "--district", match, "--prefix", prefix]).returncode == 0
    if not ok:
        failed.append(prefix)

print("\n=================== done ===================")
if failed:
    print("issues with:", ", ".join(failed))
print("Now run:  python scripts/enrich_fields.py   (rebuilds app/data + app/manifest.json)")
