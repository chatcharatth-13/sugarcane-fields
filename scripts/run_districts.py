"""
Gather sugarcane hotspots for many districts in one go.

Prereqs (run once):
  - have your FIRMS MAP_KEY
  - build a multi-province sugarcane.gpkg with make_sugarcane.py
    (drop Khon Kaen + Chaiyaphum + Nong Bua Lamphu land-use folders in landuse/)

Then:  python run_districts.py

Each district produces:
  <prefix>_hotspots.gpkg            all fires in the district
  <prefix>_sugarcane_hotspots.gpkg  fires on sugarcane
  <prefix>_summary.csv              monthly counts (sugarcane vs not)

Check each district's printed 'matched district:' line. geoBoundaries uses
romanized names, so if a district doesn't match (or matches the wrong one),
tweak its substring below.
"""
import subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))   # scripts/
FIRMS_KEY = "4618c426f3fbe281ec72f0ebfd26be3e"
SUGARCANE = os.path.join("work", "sugarcane.gpkg")  # must cover every province in DISTRICTS

# (output prefix, district-name substring to match in geoBoundaries)
DISTRICTS = [
    ("si_bun_rueang", "bun ru"),      # Nong Bua Lamphu
    ("phu_wiang",     "phu wiang"),   # Khon Kaen
    ("kaeng_khro",    "kaeng kh"),    # Chaiyaphum
    ("phu_pha_man",   "pha man"),     # Khon Kaen
    ("ban_phai",      "ban phai"),    # Khon Kaen
    ("phu_khiao",     "phu khi"),     # Chaiyaphum
    ("chum_phae",     "chum ph"),     # Khon Kaen
    ("waeng_yai",     "waeng yai"),   # Khon Kaen
    ("waeng_noi",     "waeng noi"),   # Khon Kaen
    ("suwannakhuha",  "suwan"),       # Nong Bua Lamphu
    # --- added districts ---
    ("khok_pho_chai", "khok pho chai"),  # Khon Kaen      (sugarcane covered)
    ("khon_san",      "khon san"),       # Chaiyaphum      (sugarcane covered)
    ("na_klang",      "na klang"),       # Nong Bua Lamphu (sugarcane covered)
    ("nam_som",       "nam som"),        # Udon Thani      (all-fires only*)
    ("nong_wua_so",   "nong wua"),       # Udon Thani      (all-fires only*)
    ("kut_chap",      "kut chap"),       # Udon Thani      (all-fires only*)
    ("ban_phue",      "ban phue"),       # Udon Thani      (all-fires only*)
    ("kut_rang",      "kut rang"),       # Maha Sarakham   (all-fires only*)
    ("kaset_sombun",  "kaset sombun"),   # Chaiyaphum      (sugarcane covered)
    ("mancha_khiri",  "mancha khiri"),   # Khon Kaen       (sugarcane covered)
    # * no sugarcane parcels until Udon Thani + Maha Sarakham LDD land-use is
    #   added to landuse/ and make_sugarcane.py is rerun. Check each printed
    #   "matched district:" line — geoBoundaries uses romanized names.
]

failed = []
for prefix, match in DISTRICTS:
    print(f"\n============== {prefix}  (match: '{match}') ==============")
    cmd = [sys.executable, os.path.join(HERE, "firms_sichomphu.py"), "--mode", "api",
           "--map-key", FIRMS_KEY, "--district", match,
           "--sugarcane", SUGARCANE, "--out-prefix", prefix]
    if subprocess.run(cmd).returncode != 0:
        failed.append(prefix)

print("\n=================== done ===================")
if failed:
    print("FAILED:", ", ".join(failed), "- check the messages above.")
print("Outputs per district: <prefix>_hotspots.gpkg, "
      "<prefix>_sugarcane_hotspots.gpkg, <prefix>_summary.csv")
