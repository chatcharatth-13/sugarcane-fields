#!/usr/bin/env bash
# Convenience runner. Edit the variables, then: bash run.sh
set -euo pipefail

MODE="file"                       # "file" or "api"
ARCHIVE_CSV="firms_archive.csv"   # used in file mode
MAP_KEY="YOUR_MAP_KEY"            # used in api mode

# Sugarcane crop filter — pick ONE (or neither):
#   GISTDA_KEY  : auto-fetch from GISTDA   (https://api-gateway.gistda.or.th/v2)
#   SUGARCANE   : your own polygon file
GISTDA_KEY="YOUR_GISTDA_KEY"
SUGARCANE=""                      # e.g. "sugarcane.gpkg"; leave empty to use GISTDA

CROP_ARGS=()
if [ -n "$SUGARCANE" ]; then
  CROP_ARGS=(--sugarcane "$SUGARCANE")
elif [ -n "$GISTDA_KEY" ] && [ "$GISTDA_KEY" != "YOUR_GISTDA_KEY" ]; then
  CROP_ARGS=(--gistda-key "$GISTDA_KEY")
fi

if [ "$MODE" = "api" ]; then
  python firms_sichomphu.py --mode api --map-key "$MAP_KEY" "${CROP_ARGS[@]}"
else
  python firms_sichomphu.py --mode file --in "$ARCHIVE_CSV" "${CROP_ARGS[@]}"
fi
