"""Renumber existing WebP photo pairs in EXIF capture-date order."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from PIL import Image

from build import capture_date


def filename_key(name):
    number = Path(name).stem.split("-")[-1]
    return (0, int(number)) if number.isdigit() else (1, name.casefold(), name)


def photo_sort_key(path):
    with Image.open(path) as image:
        date = capture_date(image.getexif().get_ifd(34665).get(36867))
    # Galleries display descending image numbers, so undated photographs are
    # numbered first and consequently appear after all dated photographs.
    return (date is not None, date or datetime.min, filename_key(path.name))


def collection_plan(collection_dir):
    full_dir = collection_dir / "full"
    thumbs_dir = collection_dir / "thumbs"
    if not full_dir.is_dir() and not thumbs_dir.is_dir():
        return {}
    if not full_dir.is_dir() or not thumbs_dir.is_dir():
        raise ValueError(f"{collection_dir.name}: both full and thumbs directories are required")

    full_names = {path.name for path in full_dir.iterdir() if path.is_file() and path.suffix.lower() == ".webp"}
    thumb_names = {path.name for path in thumbs_dir.iterdir() if path.is_file() and path.suffix.lower() == ".webp"}
    if full_names != thumb_names:
        missing_full = sorted(thumb_names - full_names, key=filename_key)
        missing_thumbs = sorted(full_names - thumb_names, key=filename_key)
        details = []
        if missing_full:
            details.append("missing full: " + ", ".join(missing_full))
        if missing_thumbs:
            details.append("missing thumbnail: " + ", ".join(missing_thumbs))
        raise ValueError(f"{collection_dir.name}: unmatched WebP pairs ({'; '.join(details)})")

    ordered = sorted((full_dir / name for name in full_names), key=photo_sort_key)
    mapping = {path.name: f"image-{index}.webp" for index, path in enumerate(ordered, 1)}
    source_names = set(mapping)
    for folder in (full_dir, thumbs_dir):
        for target_name in mapping.values():
            target = folder / target_name
            if target.exists() and target_name not in source_names:
                raise ValueError(f"Refusing to overwrite {target}")
    return mapping


def updated_overrides(overrides, plans):
    result = json.loads(json.dumps(overrides))
    for slug, mapping in plans.items():
        custom = result.get(slug)
        if not isinstance(custom, dict):
            continue
        if custom.get("cover") in mapping:
            custom["cover"] = mapping[custom["cover"]]
        layouts = custom.get("photo_layouts")
        if isinstance(layouts, dict):
            custom["photo_layouts"] = {mapping.get(name, name): layout for name, layout in layouts.items()}
    return result


def apply_plan(collection_dir, mapping):
    changes = {old: new for old, new in mapping.items() if old != new}
    if not changes:
        return
    token = uuid4().hex
    staged = []
    for folder_name in ("full", "thumbs"):
        folder = collection_dir / folder_name
        for index, (old_name, new_name) in enumerate(changes.items()):
            temporary = folder / f".__photo_sort_{token}_{index}.webp"
            (folder / old_name).rename(temporary)
            staged.append((temporary, folder / new_name))
    for temporary, destination in staged:
        temporary.rename(destination)


def sort_existing_photos(photos_root=Path("photos"), overrides_path=Path("collections.json"), dry_run=False):
    collections = sorted(
        directory for directory in photos_root.iterdir()
        if directory.is_dir() and not directory.name.startswith("_")
    )
    plans = {directory.name: collection_plan(directory) for directory in collections}
    plans = {slug: mapping for slug, mapping in plans.items() if mapping}

    overrides = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else {}
    revised_overrides = updated_overrides(overrides, plans)
    for directory in collections:
        mapping = plans.get(directory.name, {})
        changes = [(old, new) for old, new in mapping.items() if old != new]
        if changes:
            print(f"{directory.name}: {len(changes)} file pairs will be renamed")
            for old, new in changes:
                print(f"  {old} -> {new}")
        if not dry_run:
            apply_plan(directory, mapping)

    if not dry_run and revised_overrides != overrides:
        overrides_path.write_text(json.dumps(revised_overrides, indent=2) + "\n", encoding="utf-8")
        print(f"Updated filename references in {overrides_path}")
    return plans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photos-root", type=Path, default=Path("photos"))
    parser.add_argument("--overrides", type=Path, default=Path("collections.json"))
    parser.add_argument("--dry-run", action="store_true", help="show renames without changing files")
    args = parser.parse_args()
    sort_existing_photos(args.photos_root, args.overrides, args.dry_run)


if __name__ == "__main__":
    main()
