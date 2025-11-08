#!/bin/bash
# fix_reolink_mp4s.sh
# Rewrap or rotate Reolink H.265/hvc1 MP4s for QuickTime / ffmpeg compatibility
#
# Usage:
#   ./fix_reolink_mp4s.sh /path/to/folder            # rewrap only (fast, lossless)
#   ./fix_reolink_mp4s.sh /path/to/folder --rotate   # also rotate 90° right (re-encode)

set -euo pipefail
shopt -s nullglob

# --- Parse arguments ---
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/folder [--rotate]"
  exit 1
fi

SRC_DIR="$1"
ROTATE=false
[[ "${2:-}" == "--rotate" ]] && ROTATE=true

if [[ ! -d "$SRC_DIR" ]]; then
  echo "❌ Directory not found: $SRC_DIR"
  exit 1
fi

cd "$SRC_DIR"

echo "📂 Scanning for .mp4 files in $SRC_DIR ..."
for f in *.mp4; do
  [[ -f "$f" ]] || continue
  echo "🔍 Checking codec for: $f"

  codec_tag=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_tag_string \
              -of default=noprint_wrappers=1:nokey=1 "$f" || echo "none")

  if [[ "$codec_tag" == "hvc1" || "$codec_tag" == "hev1" ]]; then
    base="${f%.*}"

    # Skip if output already exists
    if [[ -f "${base}.fixed.mp4" || -f "${base}.rotated.mp4" ]]; then
      echo "⏭️  Already processed: $f"
      continue
    fi

    if [[ "$ROTATE" == false ]]; then
      echo "🧩 Rewrapping (lossless) $f → ${base}.fixed.mp4"
      ffmpeg -hide_banner -y -fflags +genpts -i "$f" \
        -map 0 -c copy -movflags +faststart -tag:v hvc1 "${base}.fixed.mp4" 2>&1
      echo "✅ Done: ${base}.fixed.mp4"
    else
      echo "🔁 Rotating 90° right (transcoding to H.264): $f"
      ffmpeg -hide_banner -y -hwaccel videotoolbox -i "$f" \
        -vf "transpose=1" -c:v h264_videotoolbox -b:v 8M \
        -c:a aac -b:a 192k "${base}.rotated.mp4" 2>&1
      echo "✅ Done: ${base}.rotated.mp4"
    fi
  else
    echo "⚪ Skipping non-hvc1 file: $f"
  fi
done

echo "🏁 All done."

