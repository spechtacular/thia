#!/bin/bash

set -e

# Source directory on host (symlinks live here)
SOURCE="/Users/tedspecht/Public/scp"

# Docker-friendly destination (where symlinks are resolved to real files)
DEST="./docker_media/videos"

# Additional required paths
THIA_VIDEOS="./thia/videos"
MEDIA_DIR="./media"

echo "🔁 Preparing media directories and resolving symlinks..."

# Ensure destination exists
mkdir -p "$DEST"

# Ensure thia/videos and media/ exist
mkdir -p "$THIA_VIDEOS"
mkdir -p "$MEDIA_DIR"

# Clean old content safely (optional)
# echo "🧹 Cleaning existing resolved files in $DEST..."
# rm -rf "$DEST"/*

# Copy content from symlinked SOURCE to DEST, resolving symlinks
if [ -d "$SOURCE" ]; then
    echo "📥 Resolving symlinks from $SOURCE to $DEST"
    rsync -Lrt "$SOURCE"/ "$DEST"/
else
    echo "❌ ERROR: Source directory '$SOURCE' not found!"
    exit 1
fi

# Create media/videos symlink if not present
if [ ! -e "$MEDIA_DIR/videos" ]; then
    echo "🔗 Linking $MEDIA_DIR/videos → ../docker_media/videos"
    ln -s ../docker_media/videos "$MEDIA_DIR/videos"
fi

# Ensure directory permissions are accessible for Docker user
chmod -R a+rwx "$MEDIA_DIR" "$DEST" "$THIA_VIDEOS"

echo "✅ Media preparation complete."

