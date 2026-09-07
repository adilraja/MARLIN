#!/usr/bin/env bash

set -e

SOURCE_ROOT="$HOME/kit-app-template/assets/cetacean-models"
DEST_ROOT="$HOME/kit-app-template/assets/cetaceans"
CONVERTER="$HOME/kit-app-template/tools/gltf_to_usd.py"

BLENDER="$HOME/opt/blender-5.0.1-linux-x64/blender"

mkdir -p "$DEST_ROOT"

for ZIP in "$SOURCE_ROOT"/*.zip
do
    BASE=$(basename "$ZIP" .zip)

    echo
    echo "=========================================================="
    echo "PROCESSING: $BASE"
    echo "=========================================================="

    SPECIES_DIR="$DEST_ROOT/$BASE"
    SOURCE_DIR="$SPECIES_DIR/source"
    USD_DIR="$SPECIES_DIR/usd"

    mkdir -p "$SOURCE_DIR"
    mkdir -p "$USD_DIR"

    echo "Extracting..."
    unzip -q -o "$ZIP" -d "$SOURCE_DIR"

    GLTF=$(find "$SOURCE_DIR" -type f -iname "*.gltf" | head -n 1)

    if [ -z "$GLTF" ]; then
        echo "WARNING: No GLTF file found in $ZIP"
        continue
    fi

    echo "Found GLTF:"
    echo "$GLTF"

    OUTPUT="$USD_DIR/${BASE}.usd"

    "$BLENDER" \
        --background \
        --python "$CONVERTER" \
        -- \
        --input "$GLTF" \
        --output "$OUTPUT"

    echo
    echo "Created:"
    ls -lh "$OUTPUT"

done

echo
echo "=========================================================="
echo "ALL CONVERSIONS FINISHED"
echo "=========================================================="
