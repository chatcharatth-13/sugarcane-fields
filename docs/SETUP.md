# Si Chomphu sugarcane-burning project

Toolkit for mapping sugarcane field burning in Si Chomphu, Khon Kaen, from
NASA FIRMS fire detections + LDD land use. This zip is the **code and tools**.
Your **data files** (the LDD shapefile, the .gpkg / .geojson you generated) are
not included — see "Moving your data" at the bottom.

## What's in here
- `firms_sichomphu.py` — pulls VIIRS hotspots, clips to the district, tags sugarcane
- `make_sugarcane.py`  — builds `sugarcane.gpkg` from the LDD land-use shapefile
- `prep_fields.py`     — splits sugarcane into parcels, measures burned/not-burned area,
                         writes `fields.geojson`, `hotspots.geojson`, `burned_patches.geojson`
- `field_picker.html`  — interactive map: curate ownership, see burned area, export CSV/PDF/GeoJSON
- `how_to_run.html`    — visual step-by-step guide
- `diag.py`            — diagnostics if the API/clip misbehaves
- `requirements.txt`, `run.sh`

## Setup on a new machine
1. Install Python 3.10+ then:  `pip install -r requirements.txt`
   (if geopandas fights pip: `conda install -c conda-forge geopandas folium requests pandas shapely`)
2. Keys: a free NASA FIRMS MAP_KEY (https://firms.modaps.eosdis.nasa.gov/api/map_key/).
3. Land use: download the **Khon Kaen** land-use shapefile from
   https://tswc.ldd.go.th/DownloadGIS/Index_Lu.html , extract it into a folder
   named `landuse/` beside these scripts (should contain `LU_KKN_2565.shp`).

## Run order (from the project folder)
```
python firms_sichomphu.py --mode api --map-key YOUR_FIRMS_KEY      # -> sichomphu_hotspots.gpkg, summary
python make_sugarcane.py                                           # -> sugarcane.gpkg
python firms_sichomphu.py --mode api --map-key YOUR_FIRMS_KEY --sugarcane sugarcane.gpkg   # adds the sugarcane-hotspot split
python prep_fields.py                                              # -> fields.geojson, hotspots.geojson, burned_patches.geojson
```
Then open `field_picker.html` in a browser and load the three GeoJSON files.

That regenerates the entire project on any machine — you only need your FIRMS
key and the LDD shapefile.

## Moving your data (separate from this zip)
This zip can't carry your local data folder. To open the project on your laptop:
- **Easiest:** put the whole `mapping` folder in **OneDrive** (built into Windows)
  or **Google Drive / Dropbox**, then sign in on the laptop and open it there.
- **Or:** zip your `mapping` folder, upload to Drive / copy to a USB stick.
- **Or:** just copy these scripts to the laptop and re-run them (above) — the
  hotspots and boundary download fresh; you only re-download the LDD shapefile.

Note the LDD land-use folder is ~289 MB, so cloud sync or USB is the practical
way to carry it; everything else is small.
