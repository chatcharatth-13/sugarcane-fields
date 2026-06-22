"""
Per-district field-area analysis. Run AFTER firms (which makes <prefix>_hotspots.gpkg)
and make_sugarcane (which makes sugarcane.gpkg covering the province).

Splits sugarcane into parcels inside the district, measures burned vs not-burned
AREA via the VIIRS pixel footprint, and writes the layers the picker/report use.

    python scripts/prep_fields.py --district "ban phai" --prefix ban_phai
    python scripts/prep_fields.py              # defaults: Si Chomphu / sichomphu
"""
import argparse, os
import geopandas as gpd
import requests
from shapely.geometry import box
from shapely.ops import unary_union

# Project layout: heavy/intermediate files in work/ and raw/, the app's geojson
# in app/data/. Run from the project ROOT so these relative paths resolve.
WORK, RAW, DATA = "work", "raw", os.path.join("app", "data")
os.makedirs(WORK, exist_ok=True); os.makedirs(DATA, exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument("--district", default="chomphu", help="name substring for geoBoundaries")
ap.add_argument("--prefix",   default="sichomphu", help="input/output filename prefix")
ap.add_argument("--sugarcane", default=os.path.join(WORK, "sugarcane.gpkg"))
ap.add_argument("--burnarea", help="burned-area polygon geojson; if given, real burn scars drive "
                                   "burned_rai/patches instead of the VIIRS 375 m pixel footprints")
args = ap.parse_args()

PIXEL_M, METRIC_CRS = 375, 32648
HOTSPOTS = os.path.join(WORK, f"{args.prefix}_hotspots.gpkg")

# 1. district boundary (cached so a batch doesn't re-download each time)
cache = os.path.join(RAW, "_tha_adm2.geojson")
if not os.path.exists(cache):
    print("downloading Thailand ADM2 ...")
    meta = requests.get("https://www.geoboundaries.org/api/current/gbOpen/THA/ADM2/",
                        timeout=60).json()
    with open(cache, "wb") as fh:
        fh.write(requests.get(meta["gjDownloadURL"], timeout=180).content)
b = gpd.read_file(cache).to_crs(4326)
col = next(c for c in b.columns if c.lower() in ("shapename", "name_2", "name"))
district = b[b[col].astype(str).str.lower().str.contains(args.district.lower(), na=False)]
print("district matched:", district[col].tolist())
if not len(district):
    raise SystemExit(f"no district matched '{args.district}'")

# 2. hotspots + the burn "fire" layer — computed first so HOTSPOTS-ONLY districts (a province not in
#    our LDD land-use, e.g. Loei) still get hotspots + real burn scars even with no sugarcane parcels.
hot = gpd.read_file(HOTSPOTS).to_crs(METRIC_CRS)
bs = None
if args.burnarea:
    bs = gpd.read_file(args.burnarea); bs = bs.set_crs(4326) if bs.crs is None else bs.to_crs(4326)
    bs = gpd.clip(bs, district).to_crs(METRIC_CRS)
    fire = unary_union(list(bs.geometry.values)) if len(bs) else None
    print(f"  burn source: {len(bs)} real burn-scar polygons clipped to district")
else:
    H = PIXEL_M / 2
    fire = unary_union([box(pt.x - H, pt.y - H, pt.x + H, pt.y + H) for pt in hot.geometry]) \
           if len(hot) else None
hot.to_crs(4326).to_file(os.path.join(DATA, f"{args.prefix}_hotspots.geojson"), driver="GeoJSON")
# With real burn scars the burned-area layer = those scars clipped to the district (all burned area).
if bs is not None and len(bs):
    p = bs.reset_index(drop=True).explode(index_parts=False); p = p[p.geometry.area > 0]
    if len(p):
        p[["geometry"]].to_crs(4326).to_file(os.path.join(DATA, f"{args.prefix}_burned_patches.geojson"), driver="GeoJSON")

# 3. sugarcane parcels in this district -> clip -> split -> metric CRS -> area
fields = gpd.read_file(args.sugarcane).to_crs(4326)
fields = gpd.clip(fields, district).explode(index_parts=False).reset_index(drop=True).to_crs(METRIC_CRS)
fields = fields[fields.geometry.area > 100].reset_index(drop=True)
if not len(fields):
    print("  no sugarcane parcels — HOTSPOTS-ONLY district (hotspots + burn scars written, no fields)")
    raise SystemExit(0)
fields["field_id"] = range(1, len(fields) + 1)
fields["area_rai"] = (fields.geometry.area / 1600).round(2)
fields["area_ha"]  = (fields.geometry.area / 10000).round(3)
print(f"{len(fields)} parcels (largest {fields['area_rai'].max():.0f} rai, "
      f"median {fields['area_rai'].median():.1f} rai)")

# burned AREA per parcel (field ∩ fire)
binter = fields.geometry.intersection(fire) if fire is not None else fields.geometry.iloc[:0]
fields["burned_rai"]   = (binter.area / 1600).round(2) if fire is not None else 0.0
fields["unburned_rai"] = (fields["area_rai"] - fields["burned_rai"]).clip(lower=0).round(2)
fields["burned_frac"]  = (fields["burned_rai"] / fields["area_rai"]).clip(upper=1).round(3)
fields["burned"]       = fields["burned_rai"] > 0
tot=fields["area_rai"].sum(); bd=fields["burned_rai"].sum(); ub=fields["unburned_rai"].sum()
print(f"  total {tot:.0f} rai | burned {bd:.0f} rai ({(100*bd/tot if tot else 0):.1f}%) "
      f"| not burned {ub:.0f} rai")

# 4. export: parcels -> work/ ; sugarcane_hotspots -> app/data/ (hotspots + burned_patches already written)
keep=["field_id","area_rai","area_ha","burned","burned_rai","unburned_rai","burned_frac","geometry"]
out=fields[keep]
out.to_file(os.path.join(WORK, f"{args.prefix}_sugarcane_fields.gpkg"), driver="GPKG")
out.to_crs(4326).to_file(os.path.join(WORK, f"{args.prefix}_fields.geojson"), driver="GeoJSON")
cane=unary_union(list(fields.geometry.values))
hot[hot.geometry.within(cane)].to_crs(4326).to_file(os.path.join(DATA, f"{args.prefix}_sugarcane_hotspots.geojson"), driver="GeoJSON")
# VIIRS fallback only: burned_patches = burns on sugarcane (cane ∩ footprints). --burnarea already wrote scars.
if not args.burnarea and fire is not None:
    patches=gpd.GeoDataFrame(geometry=[cane.intersection(fire)], crs=METRIC_CRS).explode(index_parts=False)
    patches=patches[patches.geometry.area>0]
    patches.to_crs(4326).to_file(os.path.join(DATA, f"{args.prefix}_burned_patches.geojson"), driver="GeoJSON")
print(f"wrote app/data/{args.prefix}_{{hotspots,sugarcane_hotspots,burned_patches}} (+ work/{args.prefix}_fields)")
