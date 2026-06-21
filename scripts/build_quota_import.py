#!/usr/bin/env python3
# Read the gov-form xlsx files in "แยกโควต้า" (one per quota holder, grouped by depot
# folder) and emit a JSON the browser import tool consumes. Each row has a centroid
# (X/Y) + area in ไร่ — we synthesize a square placeholder polygon sized to that area
# (the real boundary isn't in the data). Quota = filename; depot = folder (kept as a prop).
# Stdlib only (this machine has no openpyxl): xlsx is read via its zip/XML structure.
import zipfile, xml.etree.ElementTree as ET, re, glob, json, math, uuid, os, sys

SRC = r"C:\Users\WINDOWS\Downloads\แยกโควต้า"
OUT_DATA = os.path.join(os.path.dirname(__file__), "..", "tools", "quota_2568_data.json")
OUT_SAMPLE = os.path.join(os.path.dirname(__file__), "..", "tools", "quota_2568_sample.geojson")
DEFAULT_WS = "quota-2568"
QUOTA_COLORS = ['#36a2ff','#ff7ad9','#ffd23f','#7af0a0','#b388ff','#ff8c42','#4dd0e1','#f06292','#aed581','#ba68c8']
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

def col_idx(ref):
    s = re.match(r'([A-Z]+)', ref).group(1); n = 0
    for ch in s: n = n*26 + (ord(ch)-64)
    return n-1

def read_rows(path):
    z = zipfile.ZipFile(path); shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        r = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in r.findall(f'{NS}si'):
            shared.append(''.join(t.text or '' for t in si.iter(f'{NS}t')))
    sx = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    rows = []
    for row in sx.iter(f'{NS}row'):
        cells = {}
        for c in row.findall(f'{NS}c'):
            ref = c.get('r'); t = c.get('t'); v = c.find(f'{NS}v'); isn = c.find(f'{NS}is'); val = ''
            if t == 's' and v is not None: val = shared[int(v.text)]
            elif t == 'inlineStr' and isn is not None: val = ''.join(x.text or '' for x in isn.iter(f'{NS}t'))
            elif v is not None: val = v.text
            cells[col_idx(ref)] = val
        rows.append([cells.get(i, '') for i in range(max(cells)+1)] if cells else [])
    return rows

def num(x):
    try:
        if x is None or str(x).strip() == '': return None
        return float(str(x).strip())
    except Exception:
        return None

def square(lon, lat, area_rai):
    """Square polygon centered on (lon,lat) whose area == area_rai*1600 m²."""
    a_m2 = max(area_rai, 0.0) * 1600.0
    if a_m2 <= 0: a_m2 = 1600.0          # fallback: 1 ไร่ so it's visible
    side = math.sqrt(a_m2); half = side/2.0
    dlat = half/111320.0
    dlon = half/(111320.0*max(math.cos(math.radians(lat)), 1e-6))
    return [[
        [round(lon-dlon,7), round(lat-dlat,7)],
        [round(lon+dlon,7), round(lat-dlat,7)],
        [round(lon+dlon,7), round(lat+dlat,7)],
        [round(lon-dlon,7), round(lat+dlat,7)],
        [round(lon-dlon,7), round(lat-dlat,7)],
    ]]

def main():
    files = sorted(glob.glob(os.path.join(SRC, "*", "*.xlsx")))
    if not files:
        print("No xlsx found under", SRC); sys.exit(1)
    quotas, qkey_to_name = [], {}
    fields = []
    fid = 0
    stats = []
    bad_coord = 0; area_fallback = 0
    LONMIN, LONMAX, LATMIN, LATMAX = 100.0, 104.0, 14.0, 19.0
    for qi, path in enumerate(files):
        depot = os.path.basename(os.path.dirname(path))
        stem = os.path.splitext(os.path.basename(path))[0]
        qname = stem
        # guard against duplicate quota names across folders (would merge quotas)
        if qname in qkey_to_name:
            qname = f"{stem} ({depot})"
        qid = qi+1
        quotas.append({"qid": qid, "name": qname, "number": "", "color": QUOTA_COLORS[qi % len(QUOTA_COLORS)]})
        qkey_to_name[stem] = qname
        rows = read_rows(path)
        cnt = 0; rai_sum = 0.0
        for r in rows:
            if not r or not re.match(r'^\d+$', (r[0] or '').strip()):
                continue                                   # not a data row (header/form lines)
            def g(i): return r[i] if len(r) > i else ''
            lon = num(g(6)); lat = num(g(7))
            if lon is None or lat is None:                 # no coordinate → can't place; skip
                bad_coord += 1; continue
            if not (LONMIN <= lon <= LONMAX and LATMIN <= lat <= LATMAX):
                bad_coord += 1; continue
            area = num(g(5))
            if area is None or area <= 0: area = 1.0; area_fallback += 1
            tons = num(g(8))
            fid += 1
            props = {
                "field_id": fid, "_uid": str(uuid.uuid4()), "_mine": True,
                "quota_name": qname, "quota_number": "",
                "village": (g(1) or '').strip(), "tambon": (g(2) or '').strip(),
                "amphoe": (g(3) or '').strip(), "changwat": (g(4) or '').strip(),
                "lon": round(lon, 6), "lat": round(lat, 6),
                "depot": depot, "area_rai": round(area, 4),
            }
            if tons is not None: props["tons"] = round(tons, 4)
            feature = {"type": "Feature", "properties": props,
                       "geometry": {"type": "Polygon", "coordinates": square(lon, lat, area)}}
            fields.append({"uid": props["_uid"], "fid": fid, "feature": feature})
            cnt += 1; rai_sum += area
        stats.append((depot, qname, cnt, rai_sum))

    out = {"default_ws": DEFAULT_WS, "generated_from": "แยกโควต้า",
           "quota_count": len(quotas), "field_count": len(fields),
           "quotas": quotas, "fields": fields}
    os.makedirs(os.path.dirname(OUT_DATA), exist_ok=True)
    with open(OUT_DATA, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    # small sample for a quick visual check in the app (first 60 features)
    sample = {"type": "FeatureCollection", "features": [x["feature"] for x in fields[:60]]}
    with open(OUT_SAMPLE, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False)

    print(f"OK  files={len(files)}  quotas={len(quotas)}  fields={len(fields)}")
    print(f"    skipped_no/bad_coord={bad_coord}  area_fallback(1rai)={area_fallback}")
    print(f"    wrote {os.path.relpath(OUT_DATA)} ({os.path.getsize(OUT_DATA)//1024} KB)")
    print(f"    wrote {os.path.relpath(OUT_SAMPLE)}")
    print("    per quota (depot / name / fields / total ไร่):")
    for depot, qname, cnt, rai in stats:
        print(f"      {depot:10s} {qname:22s} {cnt:5d}  {rai:10.1f}")
    # sanity: re-derive area of one synthesized square and compare to reported
    s = fields[0]["feature"]; c = s["geometry"]["coordinates"][0]
    latc = s["properties"]["lat"]
    w_m = (c[1][0]-c[0][0]) * 111320.0 * math.cos(math.radians(latc))
    h_m = (c[2][1]-c[1][1]) * 111320.0
    print(f"    geom check: field#1 reported={s['properties']['area_rai']} ไร่  "
          f"square≈{(w_m*h_m)/1600.0:.3f} ไร่ ({w_m:.1f}m x {h_m:.1f}m)")

if __name__ == "__main__":
    main()
