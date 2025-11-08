#!/bin/bash
# rotate_videos.command — rotates all .mp4 files in a folder 90° clockwise (to the right)
# Usage: double-click, or drag a folder of .mp4s onto this script

# Ensure ffmpeg is installed
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "❌ ffmpeg not found. Install it first with: brew install ffmpeg"
  exit 1
fi

# If a folder was dropped, use it; otherwise prompt
TARGET="$1"
if [ -z "$TARGET" ]; then
  echo "Enter path to folder containing .mp4 files:"
  read TARGET
fi

# Normalize path
cd "$TARGET" || { echo "❌ Can't access folder: $TARGET"; exit 1; }

echo "🎬 Rotating all .mp4 files in: $TARGET"
echo "🎬 Using Apples native HEVC hardware decoder"

for f in *.mp4; do
  [ -e "$f" ] || { echo "⚠️ No .mp4 files found."; exit 0; }
  out="rotated_$f"
  echo "➡️  Rotating: $f → $out"
  #ffmpeg -i "$f" -vf "transpose=1" -c:a copy -y "$out"
  ffmpeg -hide_banner -loglevel error -i "$f" -vf "transpose=1" -c:v libx264 -crf 20 -preset fast -c:a copy -y "rotated_$f"
  #ffmpeg -hide_banner -loglevel warning -hwaccel videotoolbox -i "$f" \
  #   -vf "transpose=1" -c:v h264_videotoolbox -b:v 5M -c:a copy -y "rotated_$f"
done

echo "✅ Done. Rotated files saved as rotated_*.mp4"
exit 0

