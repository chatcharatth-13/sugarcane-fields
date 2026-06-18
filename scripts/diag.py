"""Quick diagnostic. Fill in FIRMS_KEY, run, paste the whole output back."""
import requests, pandas as pd, geopandas as gpd
from io import StringIO

FIRMS_KEY = "PUT_YOUR_FIRMS_KEY_HERE"
W, S, E, N = 101.9828, 16.5972, 102.2559, 16.9174   # Si Chomphu bbox

# 1) What does FIRMS actually return for that bbox?
url = (f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_KEY}"
       f"/VIIRS_SNPP_SP/{W},{S},{E},{N}/5/2026-01-15")
r = requests.get(url, timeout=60)
print("FIRMS status:", r.status_code)
print("first 250 chars:", repr(r.text[:250]))
df = pd.read_csv(StringIO(r.text)) if "latitude" in r.text.lower() else pd.DataFrame()
print("rows:", len(df))
if len(df):
    print("lat range:", round(df.latitude.min(), 3), "to", round(df.latitude.max(), 3))
    print("lon range:", round(df.longitude.min(), 3), "to", round(df.longitude.max(), 3))

# 2) Boundary: extent, validity, and a test clip
meta = requests.get("https://www.geoboundaries.org/api/current/gbOpen/THA/ADM2/",
                    timeout=60).json()
open("tha.geojson", "wb").write(requests.get(meta["gjDownloadURL"], timeout=180).content)
b = gpd.read_file("tha.geojson").to_crs(4326)
col = [c for c in b.columns if c.lower() in ("shapename", "name_2", "name")][0]
si = b[b[col].astype(str).str.lower().str.contains("chomphu", na=False)]
print("\ndistrict matched:", si[col].tolist())
print("district bounds:", [round(v, 3) for v in si.total_bounds])
print("geometry valid:", bool(si.geometry.is_valid.all()))
if len(df):
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude),
                           crs=4326)
    n_in = len(gpd.sjoin(pts, si[[si.geometry.name]], predicate="within", how="inner"))
    print("points within district (of this window):", n_in)
