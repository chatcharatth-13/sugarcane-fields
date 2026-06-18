"""
Enrich every district's fields with Thai administrative names + a representative
coordinate, then build the web app's manifest.json.

Project layout (run from the project ROOT):
    work/<prefix>_fields.geojson          intermediate input (from prep_fields.py)
    app/data/<prefix>_*hotspots/_patches  app-fetched layers (from prep_fields.py)
    app/th_adm3.geojson                   Thai sub-district boundaries (tambon/amphoe/changwat)
  ->
    app/data/<prefix>_fields_enriched.geojson
    app/manifest.json                     (paths stored relative to app/, e.g. "data/...")

    python scripts/enrich_fields.py
"""
import glob
import json
import os

import geopandas as gpd

APP  = "app"
DATA = os.path.join(APP, "data")
WORK = "work"
ADM3_FILE = os.path.join(APP, "th_adm3.geojson")
# mapthai (piyayut-ch) — ADM1/2/3 with both EN and TH names, single file has the
# full hierarchy so one point-in-polygon yields tambon + amphoe + province.
ADM3_URL = ("https://raw.githubusercontent.com/piyayut-ch/mapthai/master/"
            "data-raw/geojson/th_adm3.geojson")


def ensure_adm3():
    if not os.path.exists(ADM3_FILE):
        import requests
        print(f"downloading {ADM3_FILE} (Thai sub-district boundaries) ...")
        os.makedirs(APP, exist_ok=True)
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
    """Every district that has fields (work/) OR just hotspots (app/data/)."""
    out = set()
    for path in glob.glob(os.path.join(WORK, "*_fields.geojson")):
        out.add(os.path.basename(path)[: -len("_fields.geojson")])
    for path in glob.glob(os.path.join(DATA, "*_hotspots.geojson")):
        b = os.path.basename(path)
        if b.endswith("_sugarcane_hotspots.geojson"):
            continue
        out.add(b[: -len("_hotspots.geojson")])
    return sorted(out)


def data_ref(name):
    """Manifest path (relative to app/) for a file in app/data/, else None."""
    return f"data/{name}" if os.path.exists(os.path.join(DATA, name)) else None


def modal(series):
    s = series.dropna()
    s = s[s.astype(str).str.len() > 0]
    return s.mode().iloc[0] if len(s) else ""


def main():
    os.makedirs(DATA, exist_ok=True)
    adm = ensure_adm3()
    prefixes = discover_prefixes()
    if not prefixes:
        raise SystemExit("no inputs found in work/ or app/data/.")
    print(f"found {len(prefixes)} districts: {', '.join(prefixes)}\n")

    def admin_from_points(gdf):
        """Modal amphoe/changwat for a set of points (used for fields-less districts)."""
        pts = gpd.GeoDataFrame(geometry=gdf.geometry, crs=4326)
        j = gpd.sjoin(pts, adm, how="left", predicate="within")
        return modal(j["amphoe"]), modal(j["changwat"])

    districts = []
    for prefix in prefixes:
        src = os.path.join(WORK, f"{prefix}_fields.geojson")

        # hotspot-only district (no sugarcane parcels, e.g. uncovered province):
        # no enriched fields, but still list it so the webapp dropdown shows it.
        if not os.path.exists(src):
            hot = data_ref(f"{prefix}_hotspots.geojson") or data_ref(f"{prefix}_sugarcane_hotspots.geojson")
            amphoe = changwat = ""
            if hot:
                try:
                    amphoe, changwat = admin_from_points(
                        gpd.read_file(os.path.join(APP, hot)).to_crs(4326))
                except Exception as e:
                    print(f"  {prefix}: admin lookup failed ({e})")
            print(f"  {prefix}: hotspots-only | {amphoe} {changwat}")
            districts.append({
                "prefix": prefix, "amphoe": amphoe, "changwat": changwat,
                "fields": None,
                "hotspots": data_ref(f"{prefix}_hotspots.geojson"),
                "sugarcane_hotspots": data_ref(f"{prefix}_sugarcane_hotspots.geojson"),
                "patches": data_ref(f"{prefix}_burned_patches.geojson"),
            })
            continue

        fields = gpd.read_file(src).to_crs(4326)
        if not len(fields):
            print(f"  {prefix}: 0 features, skipping")
            continue

        # representative point: always inside the polygon (unlike centroid)
        reps = fields.geometry.representative_point()
        pts = gpd.GeoDataFrame({"_row": range(len(fields))}, geometry=reps, crs=4326)

        joined = gpd.sjoin(pts, adm, how="left", predicate="within")
        # sjoin can duplicate rows if a point touches >1 polygon; keep first
        joined = joined.drop_duplicates("_row").set_index("_row").sort_index()

        fields["tambon"] = joined["tambon"].fillna("").values
        fields["amphoe"] = joined["amphoe"].fillna("").values
        fields["changwat"] = joined["changwat"].fillna("").values
        fields["village"] = ""
        fields["lon"] = reps.x.round(6).values
        fields["lat"] = reps.y.round(6).values

        out_name = f"{prefix}_fields_enriched.geojson"
        fields.to_file(os.path.join(DATA, out_name), driver="GeoJSON")

        amphoe = modal(fields["amphoe"])
        changwat = modal(fields["changwat"])
        matched = (fields["tambon"].astype(str).str.len() > 0).sum()
        print(f"  {prefix}: {len(fields)} fields | {amphoe} {changwat} "
              f"| tambon matched {matched}/{len(fields)} -> app/data/{out_name}")

        districts.append({
            "prefix": prefix,
            "amphoe": amphoe,
            "changwat": changwat,
            "fields": f"data/{out_name}",
            "hotspots": data_ref(f"{prefix}_hotspots.geojson"),
            "sugarcane_hotspots": data_ref(f"{prefix}_sugarcane_hotspots.geojson"),
            "patches": data_ref(f"{prefix}_burned_patches.geojson"),
        })

    with open(os.path.join(APP, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({"districts": districts}, fh, ensure_ascii=False, indent=2)
    print(f"\nwrote app/manifest.json ({len(districts)} districts)")


if __name__ == "__main__":
    main()
