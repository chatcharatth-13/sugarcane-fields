"""
Enrich every district's *_fields.geojson with Thai administrative names and a
representative coordinate, then build manifest.json for field_manager.html.

For each parcel it takes a representative point (guaranteed inside the polygon)
and locates it inside the Thai sub-district boundaries (th_adm3.geojson, which
carries tambon/amphoe/changwat in Thai), adding:
    tambon, amphoe, changwat, village (""), lon, lat
village (หมู่บ้าน) has no open polygon source, so it stays blank for manual entry.

    python enrich_fields.py

Outputs (alongside the inputs):
    <prefix>_fields_enriched.geojson   (one per district)
    manifest.json                      (district list the webapp reads)
"""
import glob
import json
import os
import sys

import geopandas as gpd
import pandas as pd
import requests

ADM3_FILE = "th_adm3.geojson"
# mapthai (piyayut-ch) — ADM1/2/3 with both EN and TH names, single file has the
# full hierarchy so one point-in-polygon yields tambon + amphoe + province.
ADM3_URL = ("https://raw.githubusercontent.com/piyayut-ch/mapthai/master/"
            "data-raw/geojson/th_adm3.geojson")


def ensure_adm3():
    if not os.path.exists(ADM3_FILE):
        print(f"downloading {ADM3_FILE} (Thai sub-district boundaries) ...")
        r = requests.get(ADM3_URL, timeout=180)
        r.raise_for_status()
        with open(ADM3_FILE, "wb") as fh:
            fh.write(r.content)
    adm = gpd.read_file(ADM3_FILE).to_crs(4326)
    keep = {"ADM3_TH": "tambon", "ADM2_TH": "amphoe", "ADM1_TH": "changwat"}
    missing = [c for c in keep if c not in adm.columns]
    if missing:
        raise SystemExit(f"{ADM3_FILE} is missing expected columns: {missing}")
    adm = adm[list(keep) + ["geometry"]].rename(columns=keep)
    return adm


def discover_prefixes():
    out = []
    for path in sorted(glob.glob("*_fields.geojson")):
        if path.endswith("_fields_enriched.geojson"):
            continue
        out.append(path[: -len("_fields.geojson")])
    return out


def pick(prefix, *candidates):
    """Return the first existing file among candidates (basename), else None."""
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def modal(series):
    s = series.dropna()
    s = s[s.astype(str).str.len() > 0]
    return s.mode().iloc[0] if len(s) else ""


def main():
    adm = ensure_adm3()
    prefixes = discover_prefixes()
    if not prefixes:
        raise SystemExit("no *_fields.geojson files found in this folder.")
    print(f"found {len(prefixes)} districts: {', '.join(prefixes)}\n")

    districts = []
    for prefix in prefixes:
        src = f"{prefix}_fields.geojson"
        fields = gpd.read_file(src).to_crs(4326)
        if not len(fields):
            print(f"  {prefix}: 0 features, skipping")
            continue

        # representative point: always inside the polygon (unlike centroid)
        reps = fields.geometry.representative_point()
        pts = gpd.GeoDataFrame(
            {"_row": range(len(fields))}, geometry=reps, crs=4326)

        joined = gpd.sjoin(pts, adm, how="left", predicate="within")
        # sjoin can duplicate rows if a point touches >1 polygon; keep first
        joined = joined.drop_duplicates("_row").set_index("_row").sort_index()

        fields["tambon"] = joined["tambon"].fillna("").values
        fields["amphoe"] = joined["amphoe"].fillna("").values
        fields["changwat"] = joined["changwat"].fillna("").values
        fields["village"] = ""
        fields["lon"] = reps.x.round(6).values
        fields["lat"] = reps.y.round(6).values

        out = f"{prefix}_fields_enriched.geojson"
        fields.to_file(out, driver="GeoJSON")

        amphoe = modal(fields["amphoe"])
        changwat = modal(fields["changwat"])
        matched = (fields["tambon"].astype(str).str.len() > 0).sum()
        print(f"  {prefix}: {len(fields)} fields | {amphoe} {changwat} "
              f"| tambon matched {matched}/{len(fields)} -> {out}")

        districts.append({
            "prefix": prefix,
            "amphoe": amphoe,
            "changwat": changwat,
            "fields": out,
            "hotspots": pick(prefix, f"{prefix}_hotspots.geojson"),
            "sugarcane_hotspots": pick(prefix, f"{prefix}_sugarcane_hotspots.geojson"),
            "patches": pick(prefix, f"{prefix}_burned_patches.geojson"),
        })

    with open("manifest.json", "w", encoding="utf-8") as fh:
        json.dump({"districts": districts}, fh, ensure_ascii=False, indent=2)
    print(f"\nwrote manifest.json ({len(districts)} districts)")


if __name__ == "__main__":
    main()
