/* ============================================================================
   Sentinel-2 dNBR burn scars — NE Thailand sugarcane provinces, season 2025/26
   ----------------------------------------------------------------------------
   Produces ACTUAL burn-scar polygons (not VIIRS 375 m pixel boxes) to feed the
   field manager's burn layer + prep_fields.py burned/not-burned calculation.

   HOW TO RUN (no local install needed):
     1. Sign up for Google Earth Engine (free): https://earthengine.google.com/signup
        (it now requires a Google Cloud project — the signup walks you through it).
     2. Open the Code Editor: https://code.earthengine.google.com
     3. Paste this whole file, press Run.
     4. In the "Tasks" tab, run the export → a GeoJSON lands in your Google Drive
        folder "sugarcane_burnscar". Download it and hand it to prep_fields.py
        (see scripts/prep_fields.py integration in the plan).

   Method: NBR = (NIR B8 - SWIR2 B12)/(NIR + SWIR2). dNBR = preNBR - postNBR.
   High dNBR = vegetation burned away. Threshold → burned pixels → vectorize.
   ============================================================================ */

// ---- 1. AOI: the 5 working provinces (verify the ADM1_NAME spellings on first run) ----
var thai = ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level1').filter(ee.Filter.eq('ADM0_NAME', 'Thailand'));
var aoi = thai.filter(ee.Filter.or(
  ee.Filter.inList('ADM1_NAME', ['Khon Kaen', 'Chaiyaphum', 'Maha Sarakham', 'Udon Thani']),
  ee.Filter.stringContains('ADM1_NAME', 'Nong Bua')   // robust to GAUL's Nong Bua Lamphu spelling
));
print('AOI province count (want 5):', aoi.size());                                          // sanity-check
print('AOI provinces matched:', aoi.reduceColumns(ee.Reducer.toList(), ['ADM1_NAME']).get('list'));
// Diagnostic: if the count is not 5, this lists every Thailand province name so we can fix the spelling.
print('ALL Thailand provinces (for reference):',
  ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level1')
    .filter(ee.Filter.eq('ADM0_NAME', 'Thailand'))
    .reduceColumns(ee.Reducer.toList(), ['ADM1_NAME']).get('list'));
Map.setCenter(102.5, 16.8, 7);   // center on NE Thailand (avoids the centerObject centroid quirk)

// ---- 2. Season windows (from your FIRMS hotspots: fires Dec 2025 → May 2026) ----
//   pre  = before harvest burning starts; post = after peak burning, before regrowth.
var preStart = '2025-11-01', preEnd = '2025-11-30';
var postStart = '2026-04-15', postEnd = '2026-05-31';
var THRESH = 0.27;     // dNBR burn threshold (USGS moderate–high). Tune 0.20–0.35 to your data.
var MIN_RAI = 1;       // drop burn polygons smaller than ~1 ไร่ (speck removal)

// ---- 3. Cloud-masked Sentinel-2 SR composites → NBR ----
function maskS2(img) {
  var scl = img.select('SCL');
  // drop: 3 shadow, 8 cloud-medium, 9 cloud-high, 10 cirrus, 11 snow/ice
  var clear = scl.neq(3).and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10)).and(scl.neq(11));
  return img.updateMask(clear).divide(10000);
}
function nbr(img) { return img.normalizedDifference(['B8', 'B12']).rename('NBR'); }
function seasonNBR(start, end) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(aoi).filterDate(start, end)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60))
    .map(maskS2).map(nbr)
    .median().clip(aoi);
}
var preNBR = seasonNBR(preStart, preEnd);
var postNBR = seasonNBR(postStart, postEnd);

// ---- 4. dNBR → burned mask ----
var dnbr = preNBR.subtract(postNBR).rename('dNBR');
var burned = dnbr.gt(THRESH).selfMask();

// ---- 5. (optional) restrict to sugarcane only ----
//   Upload your sugarcane parcels (work/sugarcane.gpkg → a GEE FeatureCollection asset),
//   then uncomment to keep only burns on cane:
// var cane = ee.FeatureCollection('projects/<your-project>/assets/sugarcane_parcels');
// burned = burned.updateMask(ee.Image().byte().paint(cane, 1));

// ---- 6. Vectorize to polygons + drop tiny specks ----
var vectors = burned.reduceToVectors({
  geometry: aoi, scale: 20, geometryType: 'polygon',
  eightConnected: true, labelProperty: 'burn', maxPixels: 1e10
}).map(function (f) {
  return f.set('area_rai', f.geometry().area(10).divide(1600)).set('season', '2025/26');
}).filter(ee.Filter.gte('area_rai', MIN_RAI));

Map.addLayer(dnbr, { min: -0.2, max: 0.6, palette: ['white', 'yellow', 'orange', 'red'] }, 'dNBR');
Map.addLayer(vectors, { color: 'red' }, 'burn scars');
print('burn-scar polygon count:', vectors.size());
print('total burned ไร่ (approx):', vectors.reduceColumns(ee.Reducer.sum(), ['area_rai']).get('sum'));

// ---- 7. Export GeoJSON to Drive (WGS84) ----
Export.table.toDrive({
  collection: vectors,
  description: 'burnscar_2025_26',
  fileFormat: 'GeoJSON',
  folder: 'sugarcane_burnscar'
});
