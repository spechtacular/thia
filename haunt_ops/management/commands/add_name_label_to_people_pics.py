"""

"""
import os
from typing import Optional, Tuple

from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError, ImageOps

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def parse_staff_name(basename: str) -> str:
    """
    Your original logic: take first two underscore-separated chunks as 'First Last'.
    Falls back to the whole basename if not enough parts.
    """
    parts = [p.strip() for p in basename.split("_") if p.strip()]
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return basename.strip()


def ensure_unique_path(path: str) -> str:
    """Append ' (n)' to filename if path already exists."""
    if not os.path.exists(path):
        return path
    d, fn = os.path.split(path)
    base, ext = os.path.splitext(fn)
    i = 1
    while True:
        candidate = os.path.join(d, f"{base} ({i}){ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1


def load_font(font_path: Optional[str], font_size: int) -> ImageFont.FreeTypeFont:
    """
    Try truetype if a path is provided, else fall back to default bitmap font.
    Note: ImageFont.load_default() ignores size.
    """
    if font_path:
        try:
            return ImageFont.truetype(font_path, font_size)
        except OSError:
            pass
    return ImageFont.load_default()


def label_image(
    image_path: str,
    font_path: Optional[str],
    font_color: Tuple[int, int, int],
    pos_xy: Tuple[int, int],
    size_pct: float,
    suffix: str,
    overwrite: bool,
    stdout_write,
) -> Optional[str]:
    """
    Open image, EXIF-normalize, draw title, save as PNG next to original.
    Returns new file path (or None on failure).
    """
    try:
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)

            width, height = img.size
            basename = os.path.splitext(os.path.basename(image_path))[0]
            dirpath = os.path.dirname(image_path)

            staffname = parse_staff_name(basename)
            font_size = max(12, int(height * size_pct))  # e.g. 0.10 = 10% of height
            font = load_font(font_path, font_size)

            draw = ImageDraw.Draw(img)
            # Optional: slight outline for readability (stroke)
            draw.text(pos_xy, staffname, font=font, fill=font_color, stroke_width=1, stroke_fill=(0, 0, 0))

            # Output path: basename{suffix}.png (avoid overwriting original)
            out_name = f"{basename}{suffix}.png"
            out_path = os.path.join(dirpath, out_name)

            # If overwrite requested and source is exactly same as out_path, allow it (rare).
            # Otherwise, avoid collisions.
            if not overwrite:
                # If output equals input (e.g., original already basename.png), make unique
                if os.path.abspath(out_path) == os.path.abspath(image_path) or os.path.exists(out_path):
                    out_path = ensure_unique_path(os.path.join(dirpath, f"{basename}{suffix}.png"))

            img.save(out_path)
            stdout_write(f"Saved: {out_path}")
            return out_path

    except FileNotFoundError:
        stdout_write(f"[WARN] Not found: {image_path}")
    except UnidentifiedImageError as e:
        stdout_write(f"[SKIP] Unrecognized image: {image_path} ({e})")
    except Exception as e:
        stdout_write(f"[ERROR] {image_path}: {e}")
    return None


def is_image_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_EXTS


class Command(BaseCommand):
    help = (
        "Iterate a directory (recursively), add the filename-derived title onto each image, "
        "and save the modified image as PNG next to the original."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "directory",
            nargs="?",
            default=".",
            help="Directory to process (default: current directory).",
        )
        parser.add_argument(
            "-r", "--recursive",
            action="store_true",
            help="Recurse into subdirectories.",
        )
        parser.add_argument(
            "--font-path",
            default="/System/Library/Fonts/Monaco.ttf",
            help="Path to a .ttf/.otf font (e.g., /System/Library/Fonts/Monaco.ttf). Defaults to Pillow's built-in font.",
        )
        parser.add_argument(
            "--pos",
            default="50,250",
            help="Text position as 'x,y' in pixels (default:50,250).",
        )
        parser.add_argument(
            "--size-pct",
            type=float,
            default=0.05,
            help="Font size as a fraction of image height (default: 0.05 = 5%%).",
        )
        parser.add_argument(
            "--color",
            default="255,255,255",
            help="Font color as 'R,G,B' (default: 255,255,255 = white).",
        )
        parser.add_argument(
            "--suffix",
            default="",
            help="Suffix to append to basename for output file (default: '' → 'basename.png'). "
                 "Example: '--suffix _titled' → 'basename_titled.png'.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Allow overwriting if output path conflicts (otherwise a unique name is used).",
        )

    def handle(self, *args, **opts):
        root = os.path.abspath(opts["directory"])
        if not os.path.isdir(root):
            raise CommandError(f"Not a directory: {root}")

        try:
            pos = tuple(int(v) for v in opts["pos"].split(","))
            if len(pos) != 2:
                raise ValueError
        except ValueError:
            raise CommandError("--pos must be 'x,y' (pixels), e.g. 80,50")

        try:
            color = tuple(int(v) for v in opts["color"].split(","))
            if len(color) != 3 or not all(0 <= c <= 255 for c in color):
                raise ValueError
        except ValueError:
            raise CommandError("--color must be 'R,G,B' with 0-255 ints, e.g. 255,255,255")

        size_pct = float(opts["size_pct"])
        if size_pct <= 0 or size_pct > 1:
            raise CommandError("--size-pct must be in (0, 1], e.g. 0.10")

        font_path = opts["font_path"]
        recursive = opts["recursive"]
        suffix = opts["suffix"]
        overwrite = opts["overwrite"]

        self.stdout.write(f"Scanning: {root} (recursive={recursive})")

        if recursive:
            walker = os.walk(root)
        else:
            walker = [(root, [], os.listdir(root))]

        count_total = 0
        count_done = 0

        for dirpath, _, files in walker:
            for name in files:
                src = os.path.join(dirpath, name)
                if not os.path.isfile(src):
                    continue
                if not is_image_file(src):
                    continue

                count_total += 1
                out = label_image(
                    image_path=src,
                    font_path=font_path,
                    font_color=color,
                    pos_xy=pos,
                    size_pct=size_pct,
                    suffix=suffix,
                    overwrite=overwrite,
                    stdout_write=self.stdout.write,
                )
                if out:
                    count_done += 1

        self.stdout.write(self.style.SUCCESS(f"Processed {count_done}/{count_total} images."))
