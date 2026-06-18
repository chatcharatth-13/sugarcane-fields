#!/usr/bin/env python3
"""
FIRMS sugarcane-burning hotspot pipeline - Si Chomphu, Khon Kaen, Thailand.

Now auto-fetches the district boundary and derives the bounding box, so the
only inputs you must supply are a MAP_KEY (api mode) and, optionally, a
sugarcane parcel layer.

Pipeline:
  1. Resolve the Si Chomphu boundary (auto-download if not supplied).
  2. Acquire VIIRS active-fire hotspots (NASA FIRMS) for a date range.
  3. Clip to the district; (optional) keep only those inside sugarcane parcels.
  4. Export GeoPackage + summary table + optional interactive map.

Run examples:
  # boundary auto-downloaded, archive CSV you already have:
  python firms_sichomphu.py --mode file --in firms_archive.csv --sugarcane sugarcane.gpkg
  # live API, auto boundary:
  python firms_sichomphu.py --mode api --map-key YOURKEY --sugarcane sugarcane.gpkg
"""

import argparse
import os
import sys
import tempfile
import time
from datetime import date, timedelta
from io import StringIO

import pandas as pd

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
START_DATE = "2025-12-01"
END_DATE   = "2026-05-05"

# Used only if boundary auto-download AND --boundary both fail.
FALLBACK_BBOX = (101.95, 16.62, 102.40, 16.98)   # W,S,E,N

API_SOURCES = ["VIIRS_SNPP_SP", "VIIRS_NOAA20_SP", "VIIRS_NOAA21_NRT"]
API_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
MAX_DAY_RANGE = 5

# Free, no-key admin boundaries. ADM2 = district (amphoe).
GEOBOUNDARIES_API = "https://www.geoboundaries.org/api/current/gbOpen/THA/ADM2/"
DISTRICT_MATCH = "chomphu"   # case-insensitive substring of the district name

# GISTDA satellite sugarcane map (40 m, 2-weekly). Query by polygon (area=).
# Get a free key at https://api-gateway.gistda.or.th/v2
GISTDA_ENDPOINT = ("https://api-gateway.gistda.or.th/api/2.0/resources/"
                   "gi-service/v2.2/agriculture/sugarcane-weekly-40m")


# --------------------------------------------------------------------------
# DATE WINDOWING + URL BUILDING
# --------------------------------------------------------------------------
def date_windows(start, end, step=MAX_DAY_RANGE):
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    cur = d0
    while cur <= d1:
        rng = min(step, (d1 - cur).days + 1)
        yield cur.isoformat(), rng
        cur += timedelta(days=rng)


def build_url(map_key, source, bbox, day_range, start):
    w, s, e, n = bbox
    return f"{API_BASE}/{map_key}/{source}/{w},{s},{e},{n}/{day_range}/{start}"


# --------------------------------------------------------------------------
# BOUNDARY (auto-download + bbox)
# --------------------------------------------------------------------------
def _download_district(match=None):
    import requests
    import geopandas as gpd
    match = (match or DISTRICT_MATCH).lower()
    print("   downloading Thailand ADM2 from geoBoundaries ...")
    meta = requests.get(GEOBOUNDARIES_API, timeout=60).json()
    gj = requests.get(meta["gjDownloadURL"], timeout=180).content
    tmp = os.path.join(tempfile.gettempdir(), "tha_adm2.geojson")
    with open(tmp, "wb") as fh:
        fh.write(gj)
    gdf = gpd.read_file(tmp).to_crs(4326)
    name_col = next((c for c in gdf.columns
                     if c.lower() in ("shapename", "name_2", "name")), None)
    if name_col:
        sel = gdf[gdf[name_col].astype(str).str.lower()
                  .str.contains(match, na=False)]
        if len(sel):
            print(f"   matched district: {sel[name_col].tolist()}")
            return sel.reset_index(drop=True)
    print(f"   ! could not match '{match}' by name; using full country layer",
          file=sys.stderr)
    return gdf


def get_boundary(path, match=None):
    import geopandas as gpd
    if path:
        return gpd.read_file(path).to_crs(4326)
    return _download_district(match)


def bbox_from_boundary(gdf, pad=0.02):
    minx, miny, maxx, maxy = gdf.total_bounds
    return (round(minx - pad, 4), round(miny - pad, 4),
            round(maxx + pad, 4), round(maxy + pad, 4))


def _parse_geojson(text):
    """Pull a FeatureCollection out of a response that may be raw GeoJSON,
    a single Feature, or wrapped in an envelope. Returns a dict or None."""
    import json
    text = (text or "").strip()
    try:
        obj = json.loads(text)
    except Exception:                                      # noqa: BLE001
        return None
    if not isinstance(obj, dict):
        return None
    if obj.get("type") == "FeatureCollection":
        return obj
    if obj.get("type") == "Feature":
        return {"type": "FeatureCollection", "features": [obj]}
    for v in obj.values():
        if isinstance(v, dict) and v.get("type") in ("FeatureCollection", "Feature"):
            return _parse_geojson(json.dumps(v))
        if (isinstance(v, list) and v and isinstance(v[0], dict)
                and v[0].get("type") == "Feature"):
            return {"type": "FeatureCollection", "features": v}
    return None


def fetch_sugarcane_gistda(api_key, boundary_gdf,
                           out_path="sugarcane_gistda.geojson", cell_deg=0.035):
    """Pull GISTDA sugarcane polygons for the district.

    GISTDA's geometry endpoint rejects any query area larger than 20 km^2, so
    the district is tiled into small cells (~14 km^2 at this latitude); only
    cells overlapping the district are queried, and the results are merged.
    """
    import json
    import time
    import requests
    import geopandas as gpd
    from shapely.geometry import box
    from shapely.ops import unary_union

    b = boundary_gdf.to_crs(4326)
    district = unary_union(list(b.geometry.values))
    minx, miny, maxx, maxy = b.total_bounds

    cells, y = [], miny
    while y < maxy:
        x = minx
        while x < maxx:
            c = box(x, y, min(x + cell_deg, maxx), min(y + cell_deg, maxy))
            if c.intersects(district):
                cells.append(c)
            x += cell_deg
        y += cell_deg
    print(f"   GISTDA: {len(cells)} cells (<20 km^2 each) to query ...")

    feats, errors = [], 0
    for i, c in enumerate(cells, 1):
        x0, y0, x1, y1 = c.bounds
        area = {"type": "Feature", "properties": {},
                "geometry": {"type": "Polygon", "coordinates": [[
                    [x0, y0], [x0, y1], [x1, y1], [x1, y0], [x0, y0]]]}}
        try:
            r = requests.get(GISTDA_ENDPOINT,
                             params={"api_key": api_key, "area": json.dumps(area)},
                             timeout=120)
            gj = _parse_geojson(r.text)
            if gj and gj.get("features"):
                feats.extend(gj["features"])
            elif gj is None and "20" not in r.text:        # unexpected error text
                errors += 1
                if errors <= 2:
                    print(f"      ! cell {i}: {r.text[:120]}", file=sys.stderr)
        except Exception as exc:                           # noqa: BLE001
            errors += 1
        time.sleep(0.2)
        if i % 10 == 0:
            print(f"      {i}/{len(cells)} cells · {len(feats)} polygons so far")

    if not feats:
        raise ValueError(f"GISTDA returned no sugarcane across {len(cells)} cells "
                         f"({errors} request errors). Check key/period/area.")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": feats}, fh)
    gdf = gpd.read_file(out_path)
    gdf = (gdf.set_crs(4326) if gdf.crs is None else gdf).to_crs(4326)
    # Cells overlap at edges; drop duplicate geometries.
    gdf["_wkb"] = gdf.geometry.to_wkb()
    gdf = gdf.drop_duplicates("_wkb").drop(columns="_wkb").reset_index(drop=True)
    gdf.to_file(out_path, driver="GeoJSON")
    print(f"   GISTDA sugarcane polygons: {len(gdf)}")
    return out_path


# --------------------------------------------------------------------------
# ACQUISITION
# --------------------------------------------------------------------------
def fetch_api(map_key, sources, bbox, start, end):
    import requests
    frames = []
    for source in sources:
        for win_start, rng in date_windows(start, end):
            url = build_url(map_key, source, bbox, rng, win_start)
            try:
                r = requests.get(url, timeout=60)
                r.raise_for_status()
            except Exception as exc:                       # noqa: BLE001
                print(f"  ! {source} {win_start}: {exc}", file=sys.stderr)
                continue
            text = r.text.strip()
            if not text or text.lower().startswith(("no data", "invalid")):
                continue
            try:
                df = pd.read_csv(StringIO(text))
            except Exception:                              # noqa: BLE001
                continue
            if len(df):
                df["source"] = source
                frames.append(df)
            time.sleep(0.3)
        print(f"  fetched {source}")
    if not frames:
        sys.exit("No data returned from API. Check MAP_KEY, dates, and bbox.")
    return pd.concat(frames, ignore_index=True)


def load_file(path):
    if path.lower().endswith((".shp", ".gpkg", ".geojson", ".json")):
        import geopandas as gpd
        gdf = gpd.read_file(path)
        return pd.DataFrame(gdf.drop(columns=gdf.geometry.name)).assign(
            latitude=gdf.geometry.y, longitude=gdf.geometry.x)
    return pd.read_csv(path)


# --------------------------------------------------------------------------
# CLEAN
# --------------------------------------------------------------------------
def clean(df, min_conf=None, min_frp=None):
    df.columns = [c.lower() for c in df.columns]
    keys = [k for k in ["latitude", "longitude", "acq_date", "acq_time",
                        "satellite"] if k in df.columns]
    df = df.drop_duplicates(subset=keys).reset_index(drop=True)
    if min_conf and "confidence" in df.columns:
        c = df["confidence"].astype(str).str.lower()
        if c.isin(["l", "n", "h"]).any():
            order = {"l": 0, "n": 1, "h": 2}
            df = df[c.map(order).fillna(-1) >= order[min_conf]]
        else:
            df = df[pd.to_numeric(df["confidence"], errors="coerce")
                    >= float(min_conf)]
    if min_frp and "frp" in df.columns:
        df = df[pd.to_numeric(df["frp"], errors="coerce") >= float(min_frp)]
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------
# SPATIAL
# --------------------------------------------------------------------------
def to_gdf(df):
    import geopandas as gpd
    df = df.copy()
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    return gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326")


def clip_to(gdf, boundary_gdf):
    """Keep points inside the district. Uses a vectorized within against a
    single validated polygon, avoiding sjoin/index edge cases."""
    from shapely.ops import unary_union
    b = boundary_gdf.to_crs(4326)
    poly = unary_union(list(b.geometry.values))
    if not poly.is_valid:
        poly = poly.buffer(0)
    return gdf[gdf.geometry.within(poly)].reset_index(drop=True)


def tag_sugarcane(gdf, sugarcane_path):
    import geopandas as gpd
    cane = gpd.read_file(sugarcane_path).to_crs(4326)
    gdf = gdf.reset_index(drop=True).copy()
    gdf["_uid"] = range(len(gdf))
    joined = gpd.sjoin(gdf, cane[[cane.geometry.name]], predicate="within",
                       how="left")
    hit = joined.groupby("_uid")["index_right"].apply(lambda s: s.notna().any())
    gdf["is_sugarcane"] = gdf["_uid"].map(hit).fillna(False)
    return gdf.drop(columns="_uid")


# --------------------------------------------------------------------------
# OUTPUTS
# --------------------------------------------------------------------------
def summarise(gdf):
    out = gdf.copy()
    out["month"] = pd.to_datetime(out["acq_date"]).dt.to_period("M").astype(str)
    cols = ["month"] + (["is_sugarcane"] if "is_sugarcane" in out else [])
    return (out.groupby(cols).size().rename("hotspots")
               .reset_index().sort_values(cols))


def make_map(gdf, path):
    import folium
    m = folium.Map(location=[gdf["latitude"].mean(), gdf["longitude"].mean()],
                   zoom_start=11, tiles="OpenStreetMap")
    for _, r in gdf.iterrows():
        cane = bool(r.get("is_sugarcane", False))
        folium.CircleMarker([r["latitude"], r["longitude"]], radius=3,
                            color="red" if cane else "gray", fill=True,
                            fill_opacity=0.7,
                            popup=f'{r.get("acq_date","")} FRP={r.get("frp","")}'
                            ).add_to(m)
    m.save(path)


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["api", "file"], required=True)
    p.add_argument("--map-key")
    p.add_argument("--in", dest="infile")
    p.add_argument("--boundary", help="optional; auto-downloaded if omitted")
    p.add_argument("--district", default=DISTRICT_MATCH,
                   help="district-name substring to match in geoBoundaries")
    p.add_argument("--sugarcane")
    p.add_argument("--gistda-key", help="auto-fetch sugarcane from GISTDA if "
                                        "--sugarcane not given")
    p.add_argument("--start", default=START_DATE)
    p.add_argument("--end", default=END_DATE)
    p.add_argument("--min-conf")
    p.add_argument("--min-frp", type=float)
    p.add_argument("--out-prefix", default="sichomphu")
    args = p.parse_args()

    print("1. Resolving boundary ...")
    try:
        boundary = get_boundary(args.boundary, args.district)
        bbox = bbox_from_boundary(boundary)
    except Exception as exc:                               # noqa: BLE001
        print(f"   ! boundary failed ({exc}); using fallback bbox", file=sys.stderr)
        boundary, bbox = None, FALLBACK_BBOX
    print(f"   bbox = {bbox}")

    print("2. Acquiring hotspots ...")
    if args.mode == "api":
        if not args.map_key:
            sys.exit("--map-key required in api mode")
        raw = fetch_api(args.map_key, API_SOURCES, bbox, args.start, args.end)
    else:
        if not args.infile:
            sys.exit("--in required in file mode")
        raw = load_file(args.infile)
    print(f"   {len(raw)} raw detections")

    print("3. Cleaning ...")
    df = clean(raw, args.min_conf, args.min_frp)
    gdf = to_gdf(df)
    if len(gdf):
        print(f"   data extent  lat {gdf.geometry.y.min():.3f}..{gdf.geometry.y.max():.3f}"
              f"  lon {gdf.geometry.x.min():.3f}..{gdf.geometry.x.max():.3f}")
    if boundary is not None:
        gdf = clip_to(gdf, boundary)
    print(f"   {len(gdf)} inside the district")
    if boundary is not None and len(gdf) == 0:
        print("   ! 0 in-district. If the extent above is not ~lon 102.0-102.2 /"
              " lat 16.6-16.9, FIRMS returned a different area than requested.",
              file=sys.stderr)

    # Resolve the sugarcane layer: explicit file wins; else auto-fetch GISTDA.
    sugarcane_path = args.sugarcane
    if not sugarcane_path and args.gistda_key:
        if boundary is None:
            print("   ! GISTDA fetch needs a boundary; skipping", file=sys.stderr)
        else:
            print("4. Fetching sugarcane from GISTDA ...")
            try:
                sugarcane_path = fetch_sugarcane_gistda(args.gistda_key, boundary)
            except Exception as exc:                       # noqa: BLE001
                print(f"   ! GISTDA fetch failed ({exc}); continuing without "
                      "crop filter", file=sys.stderr)

    if sugarcane_path:
        print("5. Tagging sugarcane ...")
        gdf = tag_sugarcane(gdf, sugarcane_path)
        print(f"   {int(gdf['is_sugarcane'].sum())} inside sugarcane")

    os.makedirs("work", exist_ok=True)
    op = os.path.join("work", args.out_prefix)   # all firms outputs live under work/
    gdf.to_file(f"{op}_hotspots.gpkg", driver="GPKG")
    if sugarcane_path:
        gdf[gdf["is_sugarcane"]].to_file(
            f"{op}_sugarcane_hotspots.gpkg", driver="GPKG")
    summarise(gdf).to_csv(f"{op}_summary.csv", index=False)
    print(summarise(gdf).to_string(index=False))
    try:
        make_map(gdf, f"{op}_map.html")
    except Exception as exc:                               # noqa: BLE001
        print(f"   (skipped map: {exc})")
    print("Done.")


if __name__ == "__main__":
    main()
