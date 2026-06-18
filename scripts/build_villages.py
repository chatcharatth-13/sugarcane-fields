"""
Build app/villages.json (the village dropdown source) from DOPA's open
village dataset on data.go.th (gis-01), for the provinces we work in.

Each DOPA record has: mname (village), tname (ตำบล), aname (อำเภอ),
pname (จังหวัด). We map those to the app's {changwat, amphoe, tambon, village}
and validate the Thai names against app/th_adm3.geojson (the same boundaries the
app uses for auto-detect) so villages line up with each field's detected ตำบล.

    python scripts/build_villages.py

Writes:  app/villages.json   (array, deduped)
"""
import json
import os
import urllib3
import requests
import geopandas as gpd

urllib3.disable_warnings()

PROVINCES = ["ขอนแก่น", "ชัยภูมิ", "หนองบัวลำภู", "อุดรธานี", "มหาสารคาม"]
ROMAN = {"ขอนแก่น": "Khon Kaen", "ชัยภูมิ": "Chaiyaphum",
         "หนองบัวลำภู": "Nong Bua Lamphu", "อุดรธานี": "Udon Thani",
         "มหาสารคาม": "Maha Sarakham"}
PKG = "https://data.go.th/api/3/action/package_show?id=gis-01"
ADM3 = os.path.join("app", "th_adm3.geojson")
OUT = os.path.join("app", "villages.json")


def norm(s):
    return (s or "").strip()


def main():
    # 1) valid (changwat, amphoe, tambon) tuples from th_adm3 (what the app uses)
    adm = gpd.read_file(ADM3)
    valid = set(zip(adm["ADM1_TH"].map(norm), adm["ADM2_TH"].map(norm),
                    adm["ADM3_TH"].map(norm)))
    print(f"th_adm3: {len(valid)} tambons nationwide")

    # 2) resource URL per province (resource name contains the province name)
    res = requests.get(PKG, timeout=60, verify=False).json()["result"]["resources"]
    url_for = {}
    for prov in PROVINCES:
        hit = next((r for r in res if prov in (r.get("name") or "")), None)
        if hit:
            url_for[prov] = hit["url"]
        else:
            print(f"  ! no resource found for {ROMAN[prov]}")

    # 3) download + map + validate
    out, seen = [], set()
    for prov, url in url_for.items():
        raw = requests.get(url, timeout=180, verify=False).content
        rows = json.loads(raw.decode("utf-8"))
        if isinstance(rows, dict):
            rows = rows.get("result") or rows.get("data") or []
        matched = 0
        for r in rows:
            cw, am, ta = norm(r.get("pname")), norm(r.get("aname")), norm(r.get("tname"))
            v = norm(r.get("mname"))
            if not v:
                continue
            key = (cw, am, ta, v)
            if key in seen:
                continue
            seen.add(key)
            if (cw, am, ta) in valid:
                matched += 1
            entry = {"changwat": cw, "amphoe": am, "tambon": ta, "village": v}
            try:                                  # lat/long → nearest-village auto-suggest
                lat = round(float(r.get("oct_side15_lat")), 5)
                lon = round(float(r.get("oct_side15_lon")), 5)
                if -90 <= lat <= 90 and 90 <= lon <= 110:   # sane Thailand bounds
                    entry["lat"], entry["lon"] = lat, lon
            except (TypeError, ValueError):
                pass
            out.append(entry)
        total = sum(1 for k in seen if k[0] == prov)
        pct = (100 * matched / total) if total else 0
        print(f"  {ROMAN[prov]:16} {total:5} villages | {matched:5} match th_adm3 ({pct:.1f}%)")

    os.makedirs("app", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    mb = os.path.getsize(OUT) / 1e6
    print(f"\nwrote {OUT}  ({len(out)} villages, {mb:.2f} MB)")


if __name__ == "__main__":
    main()
