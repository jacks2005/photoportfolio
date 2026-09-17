"""Generate the static photographic archive from the existing WebP library."""
from collections import defaultdict
from datetime import datetime
from html import escape
import json
from pathlib import Path
from string import Template
from urllib.parse import quote

from PIL import Image

PHOTOS_ROOT = Path("photos")
TEMPLATE_ROOT = Path(__file__).resolve().parent
RAW_PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".tif", ".tiff")
FULL_QUALITY = 80
THUMB_LONG_EDGE = 600
THUMB_QUALITY = 60


def get_collections():
    return sorted(d for d in PHOTOS_ROOT.iterdir() if d.is_dir() and not d.name.startswith("_"))


def sorted_thumbs(thumbs_dir):
    def key(path):
        number = path.stem.split("-")[-1]
        return (1, int(number)) if number.isdigit() else (0, path.stem)
    return sorted((f for f in thumbs_dir.iterdir() if f.is_file() and f.suffix.lower() == ".webp"), key=key, reverse=True)


def raw_photo_sort_key(path):
    with Image.open(path) as img:
        date = capture_date(img.getexif().get_ifd(34665).get(36867))
    # Imported photos receive ascending numbers, which the galleries display in
    # reverse. Put undated files first so they appear after dated photographs.
    return (date is not None, date or datetime.min, path.name.casefold(), path.name)


def convert_photos():
    for collection_dir in get_collections():
        raw_files = sorted(
            (f for f in collection_dir.iterdir()
             if f.is_file() and f.suffix.lower() in RAW_PHOTO_EXTENSIONS),
            key=raw_photo_sort_key,
        )
        if not raw_files:
            continue

        full_dir = collection_dir / "full"
        thumbs_dir = collection_dir / "thumbs"
        full_dir.mkdir(exist_ok=True)
        thumbs_dir.mkdir(exist_ok=True)

        existing_numbers = [
            int(p.stem.split('-')[-1])
            for p in full_dir.glob("image-*.webp")
            if p.stem.split('-')[-1].isdigit()
        ]
        next_number = max(existing_numbers, default=0) + 1

        for raw_file in raw_files:
            name = f"image-{next_number}.webp"

            with Image.open(raw_file) as img:
                icc_profile = img.info.get("icc_profile")
                exif = img.getexif().tobytes()
                img = img.convert("RGB")

                full_img = img.copy()
                full_img.save(full_dir / name, "webp", quality=FULL_QUALITY, icc_profile=icc_profile, exif=exif)

                thumb_img = img.copy()
                thumb_img.thumbnail((THUMB_LONG_EDGE, THUMB_LONG_EDGE), Image.LANCZOS)
                thumb_img.save(thumbs_dir / name, "webp", quality=THUMB_QUALITY, icc_profile=icc_profile, exif=exif)

            raw_file.unlink()
            print(f"Converted {collection_dir.name}/{raw_file.name} -> {name}")
            next_number += 1


def e(value):
    return escape(str(value), quote=True)


def capture_date(value):
    try:
        return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def number(value):
    try:
        result = float(value)
        return result if 0 < result < float("inf") else None
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def read_photo(slug, thumb):
    full = PHOTOS_ROOT / slug / "full" / thumb.name
    if not full.is_file():
        raise ValueError(f"Missing full image: {full}")
    with Image.open(full) as img:
        width, height = img.size
        exif = img.getexif()
        details = exif.get_ifd(34665)
        date = capture_date(details.get(36867))
        camera = " ".join(str(exif.get(key, "")).strip() for key in (271, 272)).strip()
        lens = str(details.get(42036, "")).strip()
        exposure, aperture, iso = (number(details.get(key)) for key in (33434, 33437, 34855))
    with Image.open(thumb) as img:
        thumb_width, thumb_height = img.size
    settings = []
    if exposure:
        settings.append(f"1/{round(1 / exposure)} s" if exposure < 1 else f"{exposure:g} s")
    if aperture:
        settings.append(f"f/{aperture:g}")
    if iso:
        settings.append(f"ISO {iso:g}")
    metadata = []
    if date:
        metadata.append("Recorded capture: " + date.strftime("%d.%m.%Y / %H:%M"))
    if camera:
        metadata.append(camera)
    if lens:
        metadata.append(lens)
    if settings:
        metadata.append(" / ".join(settings))
    base = f"/photos/{quote(slug)}/"
    return dict(name=thumb.name, full=base + "full/" + quote(thumb.name),
                thumb=base + "thumbs/" + quote(thumb.name), width=width, height=height,
                thumb_width=thumb_width, thumb_height=thumb_height, date=date,
                camera=camera, lens=lens, metadata=metadata, settings=" / ".join(settings))


def inventory(overrides_path=Path("collections.json")):
    overrides = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else {}
    collections = []
    project_number = 0
    for directory in get_collections():
        thumbs = directory / "thumbs"
        if not thumbs.is_dir():
            continue
        images = [read_photo(directory.name, thumb) for thumb in sorted_thumbs(thumbs)]
        if not images:
            continue
        slug = directory.name
        custom = overrides.get(slug, {})
        layouts = custom.get("photo_layouts", {})
        default_layout = custom.get("default_layout", "auto")
        allowed = {"auto", "solo", "wide", "centered", "left", "right", "pair-next"}
        if default_layout not in {"auto", "solo"}:
            raise ValueError(f"{slug}: default_layout must be auto or solo")
        if not isinstance(layouts, dict):
            raise ValueError(f"{slug}: photo_layouts must map filenames to layouts")
        names = [photo["name"] for photo in images]
        for name, layout in layouts.items():
            if name not in names:
                raise ValueError(f"{slug}: unknown photo in photo_layouts: {name}")
            if not isinstance(layout, str) or layout not in allowed:
                raise ValueError(f"{slug}/{name}: unknown layout {layout!r}")
            if layout == "pair-next":
                position = names.index(name)
                if position + 1 == len(names):
                    raise ValueError(f"{slug}/{name}: pair-next requires a following photo")
                following = names[position + 1]
                if layouts.get(following, "auto") != "auto":
                    raise ValueError(f"{slug}/{name}: pair-next conflicts with the layout for {following}")
        if slug == "all" and (layouts or default_layout != "auto"):
            raise ValueError("all: photo layouts apply to project pages only")
        dates = [photo["date"] for photo in images if photo["date"]]
        first, last = (min(dates), max(dates)) if dates else (None, None)
        date_label = "Undated"
        if dates:
            date_label = first.strftime("%d.%m.%Y")
            if first.date() != last.date():
                date_label += " — " + last.strftime("%d.%m.%Y")
        # A curated ISO date range also determines the archive's year group.
        if "dates" in custom:
            first, last = [datetime.strptime(value, "%Y-%m-%d") for value in custom["dates"]]
            if first > last:
                raise ValueError(f"Reversed date range for {slug}")
            date_label = first.strftime("%d.%m.%Y")
            if first != last:
                date_label += " — " + last.strftime("%d.%m.%Y")
        cover = images[0]
        if "cover" in custom:
            cover = next((photo for photo in images if photo["name"] == custom["cover"]), None)
            if cover is None:
                raise ValueError(f"Unknown cover for {slug}: {custom['cover']}")
        is_all = slug == "all"
        if not is_all:
            project_number += 1
        collections.append(dict(slug=slug, url=f"/{quote(slug)}/", title=custom.get("title", "All Photos" if is_all else slug.replace("_", " ").title()),
                                location=custom.get("location", ""), images=images, cover=cover,
                                photo_layouts=layouts, default_layout=default_layout,
                                number=f"{project_number:03}" if not is_all else "ALL",
                                dates=date_label, date_heading="Capture dates" if "dates" in custom else "Recorded capture dates",
                                year=last.year if last else None, first=first, last=last))
    return collections


def image_tag(photo, alt, *, eager=False, sizes="(max-width: 899px) calc(100vw - 40px), 50vw", css="", thumbnail_only=False):
    responsive = (f'srcset="{e(photo["thumb"])} {photo["thumb_width"]}w, {e(photo["full"])} {photo["width"]}w" '
                  f'sizes="{e(sizes)}" ') if not thumbnail_only else ""
    width = photo["thumb_width"] if thumbnail_only else photo["width"]
    height = photo["thumb_height"] if thumbnail_only else photo["height"]
    return (f'<img class="{e(css)}" src="{e(photo["thumb"])}" {responsive}'
            f'width="{width}" height="{height}" '
            f'alt="{e(alt)}" loading="{"eager" if eager else "lazy"}" decoding="async">')


def photo_figure(photo, collection, index, *, layout="", caption=False, compact=False):
    label = f'{collection["title"]} — photograph {index + 1:03}'
    metadata = " · ".join(photo["metadata"])
    sizes = "(max-width: 599px) 45vw, (max-width: 899px) 30vw, 22vw" if compact else "(max-width: 899px) calc(100vw - 40px), 90vw"
    content = image_tag(photo, label, eager=index == 0 and not compact, sizes=sizes)
    caption_html = ""
    if caption:
        capture = photo["date"].strftime("%d.%m.%Y / %H:%M") if photo["date"] else ""
        details = " / ".join(filter(None, [capture, photo["settings"]]))
        caption_html = f'<figcaption><span>{e(photo["name"])}</span>' + (f'<span>{e(details)}</span>' if details else '') + '</figcaption>'
    portrait = not compact and photo["height"] > photo["width"]
    orientation = ' portrait' if portrait else ''
    ratio = f' style="--photo-ratio: {photo["width"] / photo["height"]:.6f}"' if not compact else ''
    return (f'<figure class="photo {layout}{orientation}"{ratio}><a class="photo-link" href="{e(photo["full"])}" '
            f'data-photo data-title="{e(label)}" data-filename="{e(photo["name"])}" data-metadata="{e(metadata)}" '
            f'aria-label="View {e(label)}">{content}</a>{caption_html}</figure>')


def render(template, **values):
    return Template((TEMPLATE_ROOT / template).read_text(encoding="utf-8")).substitute(values)


def write_page(output_root, route, title, content, *, active="", lightbox=False, page_class=""):
    navigation = "".join(f'<a href="{url}"' + (' aria-current="page"' if active == label.lower() else '') + f'>{label}</a>'
                         for label, url in [("Index", "/"), ("Archive", "/archive/")])
    navigation += '<a href="https://www.instagram.com/jgs259/" target="_blank" rel="noopener noreferrer">Instagram ↗</a>'
    page = render("base_template.html", title=e(title), description=e(f"{title}. Photographic work by Jack Simpson."),
                  navigation=navigation, content=content, page_class=e(page_class),
                  lightbox=render("lightbox_template.html") if lightbox else "")
    destination = output_root / route / "index.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(line.rstrip() for line in page.splitlines()) + "\n", encoding="utf-8")


def build_home(collections, output_root):
    projects = [c for c in collections if c["slug"] != "all"]
    rows = []
    for index, c in enumerate(projects):
        photo = c["cover"]
        rows.append(f'<a class="project-row" href="{e(c["url"])}" data-project '
                    f'data-number="{c["number"]}" data-title="{e(c["title"])}" data-date="{e(c["dates"])}" '
                    f'data-count="{len(c["images"]):03}" data-filename="{e(photo["name"])}">'
                    f'<span class="project-number">{c["number"]}</span><span class="project-name">{e(c["title"])}</span>'
                    f'<span class="project-year">{c["year"] or "Undated"}</span><span class="project-arrow" aria-hidden="true">↗</span>'
                    + image_tag(photo, c["title"], eager=index == 0, css="mobile-preview", thumbnail_only=True) + '</a>')
    preview = '<p class="empty-state">No projects in the archive yet.</p>'
    if projects:
        c, photo = projects[0], projects[0]["cover"]
        preview = (f'<a class="preview-image" id="preview-link" href="{e(c["url"])}" aria-label="Open {e(c["title"])}">'
                   + image_tag(photo, c["title"], eager=True, css="preview-photo", thumbnail_only=True) + '</a>'
                   f'<div class="preview-caption"><span id="preview-number">PROJECT_{c["number"]}</span><span id="preview-filename">{e(photo["name"])}</span></div>'
                   f'<h2 id="preview-title">{e(c["title"])}</h2><div class="preview-meta"><span id="preview-date">{e(c["dates"])}</span>'
                   f'<span id="preview-count">{len(c["images"]):03} photographs</span></div>')
    years = [date.year for c in collections for date in (c["first"], c["last"]) if date]
    period = str(min(years)) + "—" + str(max(years)) if years else "Selected work"
    all_collection = next((c for c in collections if c["slug"] == "all"), None)
    all_link = f'<a class="text-link" href="/all/">All photographs <span>{len(all_collection["images"]):03} files ↗</span></a>' if all_collection else ""
    content = render("home_template.html", period=e(period), count=f"{len(projects):02}", rows="\n".join(rows), preview=preview, all_link=all_link)
    write_page(output_root, "", "Photographic Archive | Jack Simpson", content, active="index", page_class="home-page")


def build_gallery(c, output_root):
    compact = c["slug"] == "all"
    figures = []
    images = c["images"]
    index = 0
    while index < len(images):
        photo = images[index]
        caption = not compact
        choice = c["photo_layouts"].get(photo["name"], c["default_layout"])
        if not compact and choice == "pair-next":
            figures.append('<div class="portrait-pair">' + ''.join(photo_figure(images[j], c, j, caption=True) for j in (index, index + 1)) + '</div>')
            index += 2
            continue
        layout = "" if compact else "wide"
        if not compact and choice != "auto":
            layout = "centered" if choice == "solo" else choice
        figure = photo_figure(photo, c, index, layout=layout, caption=caption, compact=compact)
        # A dedicated row prevents CSS auto-placement from making accidental pairs.
        figures.append(figure if compact else '<div class="editorial-row">' + figure + '</div>')
        index += 1
    metadata = f'<div><dt>{e(c["date_heading"])}</dt><dd>{e(c["dates"])}</dd></div><div><dt>Photographs</dt><dd>{len(images):03}</dd></div>'
    if c["location"]:
        metadata += f'<div><dt>Location</dt><dd>{e(c["location"])}</dd></div>'
    cameras = sorted(set(p["camera"] for p in images if p["camera"]))
    if cameras and not compact:
        metadata += f'<div><dt>Recorded cameras</dt><dd>{e(" / ".join(cameras))}</dd></div>'
    content = render("gallery_template.html", label="CONTACT SHEET" if compact else f'PROJECT_{c["number"]}',
                     title=e(c["title"]), metadata=metadata, gallery_class="contact-sheet" if compact else "editorial-gallery",
                     photos="\n".join(figures))
    write_page(output_root, c["slug"], c["title"] + " | Jack Simpson", content, lightbox=True)


def build_archive(collections, output_root):
    groups = defaultdict(list)
    for c in collections:
        if c["slug"] != "all":
            groups[c["year"]].append(c)
    content = '<section class="page-heading"><p class="eyebrow">COLLECTION DIRECTORY</p><h1>Archive</h1></section>'
    content += '<div class="archive-directory">'
    for year in sorted(groups, key=lambda y: y or 0, reverse=True):
        content += f'<section class="archive-year"><h2>{year or "Undated"}</h2><div>'
        for c in groups[year]:
            content += (f'<details class="archive-collection"><summary><span class="disclosure" aria-hidden="true">+</span><span class="archive-name">{e(c["title"])}</span>'
                        f'<span class="archive-count">{len(c["images"]):03} files</span></summary><div class="archive-content">'
                        f'<div class="archive-heading"><span>{e(c["dates"])}</span><a class="text-link" href="{e(c["url"])}">Open project ↗</a></div><div class="contact-sheet">')
            content += ''.join(photo_figure(photo, c, i, compact=True) for i, photo in enumerate(c["images"]))
            content += '</div></div></details>'
        content += '</div></section>'
    content += '</div>'
    if any(c["slug"] == "all" for c in collections):
        content += '<a href="/all/" class="archive-all text-link">Browse all photographs <span>Contact sheet ↗</span></a>'
    write_page(output_root, "archive", "Archive | Jack Simpson", content, active="archive", lightbox=True)


def build_site(output_root=Path("."), overrides_path=Path("collections.json")):
    collections = inventory(overrides_path)
    build_home(collections, output_root)
    for collection in collections:
        build_gallery(collection, output_root)
    build_archive(collections, output_root)
    print(f"Built index, archive, and {len(collections)} galleries")
    return collections


if __name__ == "__main__":
    convert_photos()
    build_site()
