import os
import argparse

def rename_files(directory, dry_run=False):
    if not os.path.isdir(directory):
        print(f"❌ Directory not found: {directory}")
        return

    renamed_count = 0

    for filename in os.listdir(directory):
        new_name = filename.replace("_updated", "_pic").replace(" ", "_")
        if new_name != filename:
            old_path = os.path.join(directory, filename)
            new_path = os.path.join(directory, new_name)
            if dry_run:
                print(f"[DRY-RUN] Would rename: {filename} → {new_name}")
            else:
                os.rename(old_path, new_path)
                print(f"Renamed: {filename} → {new_name}")
            renamed_count += 1

    print(f"\n✅ {renamed_count} file(s) {'would be renamed' if dry_run else 'renamed'}.")

def main():
    parser = argparse.ArgumentParser(description="Batch rename files in a directory.")
    parser.add_argument("directory", help="Path to the target directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be renamed without making changes")
    args = parser.parse_args()

    rename_files(args.directory, dry_run=args.dry_run)

if __name__ == "__main__":
    main()

