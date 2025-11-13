#!/bin/bash

# Exit on any error
set -e

# Host source (symlinks live here)
SOURCE="/Users/tedspecht/Public/scp"

# Docker-friendly destination
DEST="./docker_media/videos"

echo "🔁 Preparing media files by resolving symlinks..."
mkdir -p "$DEST"

# Copy files, resolving symlinks (-L)
rsync -Lrt "$SOURCE"/ "$DEST"/

echo "✅ Media copied to: $DEST"

