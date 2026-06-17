"""
Build sugarcane.gpkg from one or more LDD land-use shapefiles.

Put every province's extracted LDD land-use folder under 'landuse/' (e.g.
LU_KKN_2565.shp for Khon Kaen, plus Chaiyaphum and Nong Bua Lamphu). This
combines all of them into one province-wide sugarcane layer; per-district
clipping happens later in firms_sichomphu.py / prep_fields.py.

Run from the project folder:
    python make_sugarcane.py
"""
import geopandas as gpd, pandas as pd, glob, os

LU_DIR = "landuse"        # holds one or more LU_*.shp (any provinces)
OUT    = "sugarcane.gpkg"

shps = glob.glob(os.path.join(LU_DIR, "**", "*.shp"), recursive=True)
if not shps:
    raise SystemExit(f"No .shp under '{LU_DIR}/'. Put the LDD land-use folders there.")
print(f"{len(shps)} land-use shapefile(s):")
for s in shps:
    print("  ", s)

parts = []
for s in shps:
    g = gpd.read_file(s).to_crs(4326)
    en = g["LU_DES_EN"].astype(str) if "LU_DES_EN" in g.columns else pd.Series("", index=g.index)
    mask = en.str.contains(r"sugar[\s-]*cane", case=False, regex=True, na=False)
    if mask.sum() == 0 and "LU_CODE" in g.columns:   # fallback by code
        codes = g["LU_CODE"].astype(str).str.replace(" ", "")
        mask = codes.str.endswith("203") | codes.str.endswith("603")
    sel = g[mask][[c for c in ("LU_CODE", "LU_DES_EN", "geometry") if c in g.columns]]
    print(f"   {os.path.basename(s)}: {len(sel)} sugarcane polygons")
    parts.append(sel)

cane = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326)
print("total sugarcane polygons:", len(cane))
cane.to_file(OUT, driver="GPKG")
print("WROTE:", OUT, "| exists:", os.path.exists(OUT))
