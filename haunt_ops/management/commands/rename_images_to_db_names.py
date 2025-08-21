"""
Django management command to rename image files to match 'First Last' names from the database,
optionally label the image with the original filename, and update the model's image_url field.
Handles nickname normalization, alias CSVs, interactive disambiguation,
and various labeling options.
"""
import os
import re
import csv
import unicodedata
from typing import Dict, Iterable, List, Optional, Tuple

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

# Optional fast fuzzy matcher
try:
    from rapidfuzz import process, fuzz  # pip install rapidfuzz
except Exception:  # pragma: no cover
    process = None
    fuzz = None
    import difflib

# Pillow for optional labeling
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError, ImageOps

# Final extension whitelist; also used to strip extra trailing extensions
SUPPORTED_EXTS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".gif", ".heic", ".heif", ".jfif"
}
# For stripping on the basename, use lowercase without dots
EXT_TOKENS = {e.lstrip(".") for e in SUPPORTED_EXTS}

# Strip quoted/parenthesized chunks from filename basenames (no extension)
QUOTE_RE = re.compile(r'"[^"]*"|\'[^\']*\'|“[^”]*”|‘[^’]*’')


# --------------- filename cleaning helpers ----------------

def strip_parens(text: str) -> str:
    """Repeatedly remove innermost (...) to handle nesting."""
    while True:
        new, n = re.subn(r"\([^()]*\)", "", text)
        if n == 0:
            return new
        text = new


def fold_accents_lower(s: str) -> str:
    """Accent-fold and lowercase."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).lower()


def strip_extra_trailing_exts_from_basename(base: str) -> str:
    """
    Remove any trailing .ext segments on the basename where ext is a known image extension.
    Example:
      base='Jane.PNG'         -> 'Jane'
      base='John.photo.png'   -> 'John.photo'
      base='pic.tif.jpeg'     -> 'pic'
    """
    while True:
        m = re.search(r"\.([A-Za-z0-9]+)$", base)
        if not m:
            return base
        ext_token = m.group(1).lower()
        if ext_token in EXT_TOKENS:
            base = base[: m.start()]  # drop the trailing .ext
            continue
        return base


def clean_filename_to_name(basename: str) -> str:
    """
    Remove quoted/parenthesized chunks, delete apostrophes,
    collapse whitespace → 'first last' text for parsing.
    """
    s = QUOTE_RE.sub("", basename)
    s = strip_parens(s)
    s = re.sub(r"[\'’]", "", s)  # delete apostrophes in the source filename only (for parsing)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --------------- nickname & normalization ----------------

# Nickname → canonical first-name map (lowercased)
NICK = {
    "bill": "william", "billy": "william", "will": "william",
    "bob": "robert", "bobby": "robert", "rob": "robert", "robbie": "robert",
    "rick": "richard", "ricky": "richard", "dick": "richard", "rich": "richard",
    "jim": "james", "jimmy": "james",
    "jack": "john", "johnny": "john",
    "mike": "michael", "mikey": "michael",
    "andy": "andrew", "drew": "andrew",
    "tony": "anthony",
    "alex": "alexander",
    "kate": "katherine", "katie": "katherine", "kathy": "katherine",
    "cathy": "catherine",
    "beth": "elizabeth", "liz": "elizabeth", "lizzy": "elizabeth", "betty": "elizabeth",
    "peggy": "margaret", "maggie": "margaret", "meg": "margaret",
    "steve": "steven",
    "pat": "patrick",
    "trish": "patricia", "patti": "patricia",
    "sam": "samuel",
    "chris": "christopher", "kris": "christopher",
    "jen": "jennifer", "jenny": "jennifer",
    "ben": "benjamin",
    "abby": "abigail",
    "nick": "nicholas",
    "tom": "thomas",
    "joe": "joseph", "joey": "joseph",
    "dan": "daniel", "danny": "daniel",
}


def canonical_first_name(name: str) -> str:
    n = fold_accents_lower(name)
    return NICK.get(n, n)


def parse_first_last(name: str) -> Optional[Tuple[str, str]]:
    """
    Extract first/last from a cleaned string.
    If more than two tokens, use first + last token.
    """
    toks = name.split()
    if len(toks) < 2:
        return None
    return toks[0], toks[-1]


def normalized_key(first: str, last: str) -> str:
    """Canonicalize first (nicknames), fold accents, lowercase both."""
    cf = canonical_first_name(first)
    cl = fold_accents_lower(last)
    return f"{cf} {cl}"


def build_db_index(
    qs: Iterable[Tuple[int, str, str]],
) -> Tuple[
    Dict[str, Tuple[str, str]],
    Dict[str, List[str]],
    Dict[str, Tuple[str, str]],
    Dict[str, List[int]],
]:
    """
    Build:
      - exact_map: normalized_key -> (lower_first, lower_last)
      - by_last: normalized_last -> [normalized_keys]
      - pretty_map: normalized_key -> (DB_first_exact_case, DB_last_exact_case)
      - pk_map: normalized_key -> [primary_key, ...]
    """
    exact_map: Dict[str, Tuple[str, str]] = {}
    by_last: Dict[str, List[str]] = {}
    pretty_map: Dict[str, Tuple[str, str]] = {}
    pk_map: Dict[str, List[int]] = {}

    for pk, first, last in qs:
        if not first or not last:
            continue
        nk = normalized_key(first, last)
        exact_map[nk] = (fold_accents_lower(first), fold_accents_lower(last))
        pretty_map[nk] = (first, last)
        by_last.setdefault(fold_accents_lower(last), []).append(nk)
        pk_map.setdefault(nk, []).append(pk)
    return exact_map, by_last, pretty_map, pk_map


# --------------- general helpers ----------------

def is_image_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_EXTS


def unique_in(dirpath: str, candidate: str) -> str:
    """Make 'candidate' unique within dirpath by appending ' (n)' before the extension."""
    base, ext = os.path.splitext(candidate)
    out = candidate
    i = 1
    while os.path.exists(os.path.join(dirpath, out)):
        out = f"{base} ({i}){ext}"
        i += 1
    return out


def best_match(target_key: str, candidates: List[str], threshold: int) -> Optional[Tuple[str, int]]:
    """Return (best_candidate, score) if >= threshold else None."""
    if not candidates:
        return None
    if process and fuzz:
        cand, score, _ = process.extractOne(target_key, candidates, scorer=fuzz.WRatio)
        return (cand, int(score)) if score >= threshold else None
    # fallback difflib
    import difflib
    best = None
    best_score = -1
    for c in candidates:
        score = int(difflib.SequenceMatcher(a=target_key, b=c).ratio() * 100)
        if score > best_score:
            best_score, best = score, c
    return (best, best_score) if best and best_score >= threshold else None


def load_aliases_csv(path: str):
    """
    CSV columns (header required):
      alias_first, target_first[, last]
    - If 'last' present, applies only for that last name.
    - Matching ignores case/accents. 'target_first' is used verbatim in output.
    """
    specific = {}  # (alias_first_norm, last_norm) -> target_first_pretty
    global_ = {}   # alias_first_norm -> target_first_pretty
    with open(path, newline="", encoding="utf-8") as fh:
        rdr = csv.DictReader(fh)
        for row in rdr:
            a = (row.get("alias_first") or "").strip()
            t = (row.get("target_first") or "").strip()
            l = (row.get("last") or "").strip()
            if not a or not t:
                continue
            a_norm = fold_accents_lower(a)
            if l:
                specific[(a_norm, fold_accents_lower(l))] = t
            else:
                global_[a_norm] = t
    return specific, global_


def choose_interactive(target_key: str, candidates: list, pretty_map: dict, topk: int) -> Optional[str]:
    """Prompt user to pick among top-K candidates; return normalized_key or None to skip."""
    scored = []
    if process and fuzz:
        scored = process.extract(target_key, candidates, scorer=fuzz.WRatio, limit=topk)
        scored = [(c, int(s)) for c, s, _ in scored]
    else:
        import difflib
        for c in candidates:
            s = int(difflib.SequenceMatcher(a=target_key, b=c).ratio() * 100)
            scored.append((c, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:topk]

    print("\nAmbiguous match for:", target_key)
    for i, (ck, sc) in enumerate(scored, 1):
        pf, pl = pretty_map[ck]
        print(f"  {i}) {pf} {pl}  (score={sc})")
    print("  s) skip")
    while True:
        ans = input(f"Pick [1-{len(scored)}] or s: ").strip().lower()
        if ans == "s":
            return None
        if ans.isdigit():
            ix = int(ans)
            if 1 <= ix <= len(scored):
                return scored[ix - 1][0]


# --------------- labeling helpers (Pillow) ----------------

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
    title_text: str,
    font_path: Optional[str],
    font_color: Tuple[int, int, int],
    pos_xy: Tuple[int, int],
    size_pct: float,
    suffix: str,
    overwrite: bool,
    stdout_write,
    output_path: Optional[str] = None,   # if set, write here (in-place or custom path)
) -> Optional[str]:
    """
    Open image, EXIF-normalize, draw title_text, save either to output_path (if provided)
    using that path's extension, or to PNG next to original with {suffix}.
    """
    try:
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)

            _, height = img.size
            font_size = max(12, int(height * size_pct))
            font = load_font(font_path, font_size)

            draw = ImageDraw.Draw(img)
            # Slight outline for readability
            draw.text(pos_xy, title_text, font=font, fill=font_color, stroke_width=1, stroke_fill=(0, 0, 0))

            if output_path:
                out_path = output_path
            else:
                basename = os.path.splitext(os.path.basename(image_path))[0]
                dirpath = os.path.dirname(image_path)
                out_name = f"{basename}{suffix}.png"
                out_path = os.path.join(dirpath, out_name)
                if not overwrite:
                    if os.path.abspath(out_path) == os.path.abspath(image_path) or os.path.exists(out_path):
                        out_path = os.path.join(dirpath, unique_in(dirpath, out_name))

            # Save using extension inferred from out_path (if provided), else PNG
            _, ext = os.path.splitext(out_path)
            save_kwargs = {}
            if ext.lower() in {".jpg", ".jpeg"}:
                save_kwargs["quality"] = 95
            img.save(out_path, **save_kwargs)
            stdout_write(f"[label ] Saved: {out_path}")
            return out_path

    except FileNotFoundError:
        stdout_write(f"[WARN ] Not found: {image_path}")
    except UnidentifiedImageError as e:
        stdout_write(f"[SKIP ] Unrecognized image: {image_path} ({e})")
    except Exception as e:
        stdout_write(f"[ERROR] {image_path}: {e}")
    return None


# --------------- command ----------------

class Command(BaseCommand):
    help = (
        "Rename image files to match 'First Last' from the database, optionally label the image with the ORIGINAL filename base, "
        "and (optionally) update the model's image_url field with the modified image filename.\n"
        "- Removes quoted/parenthesized chunks for parsing; deletes apostrophes in OUTPUT filenames; spaces -> underscores.\n"
        "- Handles nicknames, alias CSV, interactive disambiguation.\n"
        "- Preserves the final extension (lowercased); strips extra trailing extensions from the source basename.\n"
        "- Label text uses the EXACT original basename (no extension), unchanged (apostrophes kept)."
    )

    def add_arguments(self, parser):
        # Core rename options
        parser.add_argument("directory", nargs="?", default=".", help="Root directory (default: .)")
        parser.add_argument("-r", "--recursive", action="store_true", help="Recurse into subdirectories")
        parser.add_argument("--commit", action="store_true", help="Actually rename files / write labels / update DB (default: dry-run)")
        parser.add_argument("--threshold", type=int, default=88, help="Fuzzy match threshold 0-100 (default 88)")
        parser.add_argument("--alias-csv", default="", help="CSV with alias mappings (alias_first,target_first[,last])")
        parser.add_argument("--interactive", action="store_true", help="Prompt when ambiguous/no strong match")
        parser.add_argument("--topk", type=int, default=5, help="Top-K options in --interactive (default 5)")

        # DB source options
        parser.add_argument("--model", default="", help="Model label, e.g. 'haunt_ops.AppUser'. Default: auth user.")
        parser.add_argument("--first-field", default="first_name", help="First-name field (default: first_name)")
        parser.add_argument("--last-field", default="last_name", help="Last-name field (default: last_name)")

        # Labeling options
        parser.add_argument("--label", action="store_true",
                            help="Also draw the ORIGINAL filename base (no extension) onto the image.")
        parser.add_argument("--label-inplace", action="store_true",
                            help="If --label is set, draw onto the renamed image IN-PLACE (no separate PNG).")
        parser.add_argument("--label-font-path", default="/System/Library/Fonts/Monaco.ttf",
                            help="Path to a .ttf/.otf font (default Monaco on macOS; falls back to Pillow default).")
        parser.add_argument("--label-pos", default="50,250",
                            help="Text position as 'x,y' in pixels (default: 50,250).")
        parser.add_argument("--label-size-pct", type=float, default=0.05,
                            help="Font size as a fraction of image height (default 0.05 = 5%).")
        parser.add_argument("--label-color", default="255,255,255",
                            help="Font color as 'R,G,B' (default: 255,255,255 = white).")
        parser.add_argument("--label-suffix", default="",
                            help="Suffix appended to basename for labeled PNG if not in-place (default: '').")
        parser.add_argument("--label-overwrite", action="store_true",
                            help="Allow overwriting if labeled output path exists (otherwise unique name is used).")

        # Image URL update options
        parser.add_argument("--update-image-url", action="store_true",
                            help="Update the model's image_url field with the modified image filename (basename only).")
        parser.add_argument("--image-url-field", default="image_url",
                            help="Field name to update (default: image_url).")
        parser.add_argument("--image-url-use-labeled", action="store_true",
                            help="When --label is used (not in-place), store the labeled PNG's filename instead of the renamed file.")
        parser.add_argument("--update-duplicates", action="store_true",
                            help="If multiple users share the matched name, update all their image_url values (default: skip).")

    def handle(self, *args, **opts):
        root = os.path.abspath(opts["directory"])
        if not os.path.isdir(root):
            raise CommandError(f"Not a directory: {root}")

        recursive   = opts["recursive"]
        commit      = opts["commit"]
        threshold   = int(opts["threshold"])
        model_label = opts["model"].strip()
        first_field = opts["first_field"]
        last_field  = opts["last_field"]

        # Label config
        do_label         = opts["label"]
        label_inplace    = opts["label_inplace"]
        label_font_path  = opts["label_font_path"]
        label_suffix     = opts["label_suffix"]
        label_overwrite  = opts["label_overwrite"]

        # Image URL updates
        do_update_image_url     = opts["update_image_url"]
        image_url_field         = opts["image_url_field"]
        image_url_use_labeled   = opts["image_url_use_labeled"]
        update_duplicates       = opts["update_duplicates"]

        try:
            label_pos = tuple(int(v) for v in opts["label_pos"].split(","))
            if len(label_pos) != 2:
                raise ValueError
        except ValueError:
            raise CommandError("--label-pos must be 'x,y' (pixels), e.g. 80,50")

        try:
            label_color = tuple(int(v) for v in opts["label_color"].split(","))
            if len(label_color) != 3 or not all(0 <= c <= 255 for c in label_color):
                raise ValueError
        except ValueError:
            raise CommandError("--label-color must be 'R,G,B' with 0-255 ints, e.g. 255,255,255")

        label_size_pct = float(opts["label_size_pct"])
        if label_size_pct <= 0 or label_size_pct > 1:
            raise CommandError("--label-size-pct must be in (0, 1], e.g. 0.10")

        # Load model & names
        if model_label:
            try:
                Model = apps.get_model(model_label)
            except Exception as e:
                raise CommandError(f"Could not load model '{model_label}': {e}")
        else:
            Model = get_user_model()

        if not hasattr(Model, first_field) or not hasattr(Model, last_field):
            raise CommandError(f"Model {Model.__name__} missing '{first_field}'/'{last_field}'")

        # If updating image_url, make sure the field exists
        if do_update_image_url and not hasattr(Model, image_url_field):
            raise CommandError(f"Model {Model.__name__} has no field '{image_url_field}'")

        db_rows = Model.objects.values_list("pk", first_field, last_field)
        exact_map, by_last, pretty_map, pk_map = build_db_index(db_rows)

        # Aliases
        self.alias_specific, self.alias_global = {}, {}
        if opts["alias_csv"]:
            try:
                self.alias_specific, self.alias_global = load_aliases_csv(opts["alias_csv"])
                self.stdout.write(
                    f"Loaded aliases: specific={len(self.alias_specific)}, global={len(self.alias_global)}"
                )
            except Exception as e:
                raise CommandError(f"Failed to load --alias-csv: {e}")

        self.stdout.write(
            f"Loaded {len(pretty_map)} DB names from {Model.__name__} "
            f"({first_field}/{last_field}). Threshold={threshold}. recursive={recursive}. "
            f"Mode={'COMMIT' if commit else 'DRY-RUN'}. Labeling={'ON' if do_label else 'OFF'} "
            f"({'in-place' if label_inplace else 'separate PNG' if do_label else ''}). "
            f"Update image_url={'ON' if do_update_image_url else 'OFF'}."
        )

        walker = os.walk(root) if recursive else [(root, [], os.listdir(root))]
        total = matched = skipped = 0

        for dirpath, _, files in walker:
            for name in files:
                src = os.path.join(dirpath, name)
                if not os.path.isfile(src) or not is_image_file(src):
                    continue

                total += 1

                # ORIGINAL filename base (strip only the FINAL extension) for label text
                original_label_base = os.path.splitext(name)[0]
                label_text = original_label_base  # exact original base, unmodified

                # Split final extension (to preserve) and strip any extra extensions from the basename for parsing
                base, ext = os.path.splitext(name)
                base = strip_extra_trailing_exts_from_basename(base)

                # Clean and parse "first last" for DB matching
                cleaned = clean_filename_to_name(base)
                parsed = parse_first_last(cleaned)
                if not parsed:
                    self.stdout.write(self.style.WARNING(f"[skip  ] {name}: cannot parse first/last from '{cleaned}'"))
                    skipped += 1
                    continue

                first, last = parsed
                first_norm = fold_accents_lower(first)
                last_norm  = fold_accents_lower(last)

                # Apply alias (specific by last, then global)
                if (first_norm, last_norm) in self.alias_specific:
                    first = self.alias_specific[(first_norm, last_norm)]
                elif first_norm in self.alias_global:
                    first = self.alias_global[first_norm]

                target_key = normalized_key(first, last)

                # Exact or fuzzy (restricted by last name if possible)
                match = None
                if target_key in pretty_map:
                    match = (target_key, 100)
                else:
                    candidates = by_last.get(last_norm) or list(pretty_map.keys())
                    match = best_match(target_key, candidates, threshold)

                if not match and opts["interactive"]:
                    chosen = choose_interactive(target_key, candidates, pretty_map, opts["topk"])
                    if chosen:
                        match = (chosen, 100)

                if not match:
                    self.stdout.write(self.style.WARNING(f"[nohit ] {name} -> '{first} {last}'"))
                    skipped += 1
                    continue

                best_key, score = match
                db_first, db_last = pretty_map[best_key]

                # Build new base from DB names:
                # 1) delete apostrophes in the OUTPUT filename,
                # 2) replace spaces with underscores.
                new_base_text = f"{db_first} {db_last}"
                new_base_text = re.sub(r"[\'’]", "", new_base_text)         # delete apostrophes in final filename only
                new_base = re.sub(r"\s+", "_", new_base_text).strip("_")     # spaces -> underscores
                new_name = f"{new_base}{ext.lower()}"

                # Destination path (rename)
                dst = os.path.join(dirpath, new_name)
                if os.path.exists(dst):
                    dst = os.path.join(dirpath, unique_in(dirpath, new_name))

                rel_src = os.path.relpath(src, root)
                rel_dst = os.path.relpath(dst, root)

                if new_name == name:
                    self.stdout.write(f"[ok    ] {name} already correct (score={score})")
                    # Even if name is already correct, we might still label
                    final_path = src
                else:
                    self.stdout.write(f"[rename] {rel_src}  ->  {rel_dst}  (score={score})")
                    if commit:
                        try:
                            os.rename(src, dst)
                            final_path = dst
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"  !! rename failed: {e}"))
                            skipped += 1
                            continue
                    else:
                        final_path = dst  # what it WOULD be
                    matched += 1

                # Optional: label the (renamed/intended) image with the ORIGINAL basename (no extension), unmodified
                labeled_written_path: Optional[str] = None
                if do_label:
                    title_text = label_text

                    if commit:
                        if label_inplace:
                            # Draw onto the renamed image itself
                            labeled_written_path = label_image(
                                image_path=(final_path if os.path.exists(final_path) else src),
                                title_text=title_text,
                                font_path=label_font_path,
                                font_color=label_color,
                                pos_xy=label_pos,
                                size_pct=label_size_pct,
                                suffix="",                 # ignored when output_path is provided
                                overwrite=True,            # in-place, so overwrite
                                stdout_write=self.stdout.write,
                                output_path=(final_path if os.path.exists(final_path) else src),
                            )
                        else:
                            # Separate PNG next to renamed image
                            labeled_written_path = label_image(
                                image_path=(final_path if os.path.exists(final_path) else src),
                                title_text=title_text,
                                font_path=label_font_path,
                                font_color=label_color,
                                pos_xy=label_pos,
                                size_pct=label_size_pct,
                                suffix=label_suffix,
                                overwrite=label_overwrite,
                                stdout_write=self.stdout.write,
                                output_path=None,
                            )
                    else:
                        # Dry-run messages
                        if label_inplace:
                            self.stdout.write(
                                f"[label*] would draw IN-PLACE on: {os.path.relpath(final_path, root)} "
                                f"(text='{title_text}')"
                            )
                        else:
                            labeled_base = os.path.splitext(os.path.basename(final_path))[0]
                            labeled_name = f"{labeled_base}{label_suffix}.png"
                            # ensure uniqueness preview if not overwriting
                            preview_name = labeled_name
                            if os.path.exists(os.path.join(os.path.dirname(final_path), labeled_name)) and not label_overwrite:
                                preview_name = unique_in(os.path.dirname(final_path), labeled_name)
                            self.stdout.write(
                                f"[label*] would write: {os.path.join(os.path.dirname(rel_dst), preview_name)} "
                                f"(text='{title_text}')"
                            )

                # Update image_url field with modified image filename (basename only)
                if commit and do_update_image_url:
                    # Decide which filename to store
                    if do_label and not label_inplace and image_url_use_labeled and labeled_written_path:
                        image_url_value = os.path.basename(labeled_written_path)
                    else:
                        image_url_value = os.path.basename(final_path)

                    pk_list = pk_map.get(best_key, [])
                    if not pk_list:
                        self.stdout.write(self.style.WARNING(f"[update] No PKs found for key '{best_key}', skip image_url"))
                    elif len(pk_list) > 1 and not update_duplicates:
                        self.stdout.write(self.style.WARNING(
                            f"[update] Multiple users share '{db_first} {db_last}' ({pk_list}); skipping image_url (use --update-duplicates to force)."
                        ))
                    else:
                        try:
                            if len(pk_list) == 1:
                                Model.objects.filter(pk=pk_list[0]).update(**{image_url_field: image_url_value})
                            else:
                                Model.objects.filter(pk__in=pk_list).update(**{image_url_field: image_url_value})
                            self.stdout.write(f"[update] Set {image_url_field}='{image_url_value}' for user PK(s) {pk_list}")
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"[update] Failed to set {image_url_field}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Done. Matched {matched}/{total}. Unmatched {skipped}."))
