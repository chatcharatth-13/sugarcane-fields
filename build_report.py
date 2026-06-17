"""
Build a standalone, shareable report from the field picker.

Reads field_picker.html + your three GeoJSON files and embeds the data, so the
output 'sichomphu_report.html' opens with everything already loaded -- no file
buttons. Anyone you send it to just double-clicks it.

Run from the project folder (after prep_fields.py):
    python build_report.py
"""
import json, os

TEMPLATE = "field_picker.html"
OUT      = "sichomphu_report.html"
# Prefer the sugarcane-only fires for the report's red dots; fall back to all.
HOTSPOTS = "sugarcane_hotspots.geojson" if os.path.exists("sugarcane_hotspots.geojson") else "hotspots.geojson"
FILES    = {"fields": "fields.geojson",
            "hotspots": HOTSPOTS,
            "patches": "burned_patches.geojson"}
print("hotspots layer:", HOTSPOTS)

def load(path):
    if not os.path.exists(path):
        print(f"  (skipping {path} - not found)")
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)

html = open(TEMPLATE, encoding="utf-8").read()
if "<!-- EMBEDDED_DATA -->" not in html:
    raise SystemExit("Template has no EMBEDDED_DATA marker - use the latest field_picker.html.")

data = {k: load(v) for k, v in FILES.items()}
if not data["fields"]:
    raise SystemExit("fields.geojson is required. Run prep_fields.py first.")

# json.dumps with </ escaped so a stray '</script>' inside data can't break the page
payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
inject = "<script>window.__DATA__=" + payload + ";</script>"
html = html.replace("<!-- EMBEDDED_DATA -->", inject)

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(html)

mb = os.path.getsize(OUT) / 1e6
print(f"wrote {OUT}  ({mb:.1f} MB) - open it directly or send it to anyone")
