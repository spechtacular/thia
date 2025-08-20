"""
Here is a safe Python renamer that does exactly what you asked:
removes all quoted chunks (both "..." and '...' including curly “…” and ‘…’)
removes all parentheses chunks (handles nested by stripping innermost first)
then converts apostrophes (both ' and ’) and blanks to _
collapses multiple _, trims leading/trailing _, and avoids name collisions
supports dry-run and recursion
"""

import os
import re
from django.core.management.base import BaseCommand, CommandError


# Remove ASCII and curly quoted chunks
QUOTE_RE = re.compile(r'"[^"]*"|\'[^\']*\'|“[^”]*”|‘[^’]*’')

# Remove innermost (...) repeatedly to handle nesting
def strip_parens(text: str) -> str:
    """
    Args:
        text (str): The input string to process.
    Returns:
        str: The string with all parentheses and their contents removed.
    1. Uses a regular expression to find innermost parentheses.
    2. Replaces them with an empty string.
    3. Repeats until no more parentheses are found.
    4. Returns the cleaned string.
    5. If no parentheses are found, returns the original string.
    6. Handles nested parentheses safely by using a loop.
    7. Ensures that all parentheses and their contents are removed.
    8. Returns the modified string without parentheses.
    9. If no parentheses are found, returns the original string.
    """
    while True:
        new, n = re.subn(r"\([^()]*\)", "", text)
        if n == 0:
            return new
        text = new

def sanitize_basename(name: str) -> str:
    """
    Sanitize a filename by removing quoted and parenthesized parts,
    deleting apostrophes and converting spaces to underscores,
    collapsing multiple underscores, and trimming.
    Returns an empty string if the name becomes empty.
    """
    # 1) remove quoted substrings
    name = QUOTE_RE.sub("", name)
    # 2) remove parenthesized substrings (nested safe)
    name = strip_parens(name)
    # 3) ONLY delete apostrophes (join surrounding text with no separator)
    name = re.sub(r"[\'’]", "", name)
    # 4) convert blanks (whitespace) to underscores
    name = re.sub(r"\s+", "_", name)
    # 5) collapse multiple underscores and trim
    name = re.sub(r"_+", "_", name).strip("_")
    return name or ""

def unique_in(dirpath: str, candidate: str) -> str:
    """
    Ensure the candidate filename is unique in the given directory.
    If it exists, appends (1), (2), etc. to the base name.
    Returns the unique filename.
    """
    base, ext = os.path.splitext(candidate)
    out = candidate
    i = 1
    while os.path.exists(os.path.join(dirpath, out)):
        out = f"{base} ({i}){ext}"
        i += 1
    return out


def process_dir(root: str, recursive: bool, dry_run: bool, include_dirs: bool, writer) -> None:
    """
    Process a directory, renaming files and optionally directories.
    Args:
        root (str): The root directory to process.
        recursive (bool): Whether to recurse into subdirectories.
        dry_run (bool): If True, only show changes without renaming.
        include_dirs (bool): If True, also rename directories.
        writer (callable): Function to write output messages.
    """
    walker = os.walk(root) if recursive else [(root, [], os.listdir(root))]

    conversion_count = 0
    file_count = 0
    for dirpath, dirnames, filenames in walker:
        # Files first
        for old in list(filenames):
            if old.startswith("."):
                # Skip hidden files (dotfiles)
                continue

            file_count += 1
            old_path = os.path.join(dirpath, old)
            if not os.path.isfile(old_path):
                continue

            base, ext = os.path.splitext(old)
            new_base = sanitize_basename(base)

            # If sanitize would produce empty, skip (don't nuke the name)
            new_name = (new_base + ext) if new_base else old

            if new_name == old:
                continue

            # Ensure the new name is unique in this directory
            # to avoid collisions with existing files
            # (e.g. if "file.txt" becomes "file (1).txt")
            if not new_name.endswith(ext):
                new_name += ext
            if not new_name:
                writer(f"Skipping empty name for {old_path}")
                continue

            conversion_count += 1
            new_name = unique_in(dirpath, new_name)
            new_path = os.path.join(dirpath, new_name)

            rel_old = os.path.relpath(old_path, root)
            rel_new = os.path.relpath(new_path, root)
            writer(f"file converted {rel_old} -> {rel_new} {conversion_count}/{file_count}")
            if not dry_run:
                os.rename(old_path, new_path)

        # Optionally rename directories (after files to reduce path churn)
        if include_dirs:
            # Longest names first to avoid moving parents before children
            for old in sorted(dirnames, key=len, reverse=True):
                old_path = os.path.join(dirpath, old)
                if not os.path.isdir(old_path):
                    continue

                new_dir = sanitize_basename(old) or old
                if new_dir == old:
                    continue


                new_dir = unique_in(dirpath, new_dir)
                new_path = os.path.join(dirpath, new_dir)

                rel_old = os.path.relpath(old_path, root)
                rel_new = os.path.relpath(new_path, root)
                writer(f"directory converted {rel_old}/ -> {rel_new}/")
                if not dry_run:
                    os.rename(old_path, new_path)


    # Final summary
    writer(f"files converted {conversion_count} of {file_count} total")


class Command(BaseCommand):

    help = (
        "Sanitize filenames: remove quoted/parenthesized parts,"
        "then replace apostrophes and blanks "
        "with underscores. Preserves extensions. Supports --dry-run and recursion."
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
            "-n", "--dry-run",
            action="store_true",
            help="Show planned changes without renaming.",
        )
        parser.add_argument(
            "--include-dirs",
            action="store_true",
            help="Also rename directories (not just files).",
        )

    def handle(self, *args, **options):
        root = os.path.abspath(options["directory"])
        if not os.path.isdir(root):
            raise CommandError(f"Not a directory: {root}")

        def writer(msg: str):
            self.stdout.write(msg)

        process_dir(
            root=root,
            recursive=options["recursive"],
            dry_run=options["dry_run"],
            include_dirs=options["include_dirs"],
            writer=writer,
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run only. No files were renamed."))
        else:
            self.stdout.write(self.style.SUCCESS("Done."))


