from pathlib import Path

PHOTOS_ROOT = Path("photos")
HOME_TEMPLATE = Path("home_template.html")
GALLERY_TEMPLATE = Path("gallery_template.html")
HOME_PAGE = Path("index.html")

RAW_PHOTO_EXTENSIONS = ('.jpg', '.jpeg', '.tif', '.tiff')
FULL_LONG_EDGE = 2400
FULL_QUALITY = 80
THUMB_LONG_EDGE = 600
THUMB_QUALITY = 60


def get_collections():
    return sorted(
        d for d in PHOTOS_ROOT.iterdir()
        if d.is_dir() and not d.name.startswith('_')
    )


def sorted_thumbs(thumbs_dir):
    return sorted(
        (f for f in thumbs_dir.iterdir() if f.is_file() and f.suffix.lower() == '.webp'),
        key=lambda f: int(f.stem.split('-')[-1]) if f.stem.split('-')[-1].isdigit() else f.stem,
        reverse=True,
    )


def convert_photos():
    from PIL import Image

    for collection_dir in get_collections():
        raw_files = sorted(
            f for f in collection_dir.iterdir()
            if f.is_file() and f.suffix.lower() in RAW_PHOTO_EXTENSIONS
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
                full_img.thumbnail((FULL_LONG_EDGE, FULL_LONG_EDGE), Image.LANCZOS)
                full_img.save(full_dir / name, "webp", quality=FULL_QUALITY, icc_profile=icc_profile, exif=exif)

                thumb_img = img.copy()
                thumb_img.thumbnail((THUMB_LONG_EDGE, THUMB_LONG_EDGE), Image.LANCZOS)
                thumb_img.save(thumbs_dir / name, "webp", quality=THUMB_QUALITY, icc_profile=icc_profile, exif=exif)

            raw_file.unlink()
            print(f"Converted {collection_dir.name}/{raw_file.name} -> {name}")
            next_number += 1


def build_home():
    page_links = []

    for collection_dir in get_collections():
        thumbs_dir = collection_dir / "thumbs"
        if not thumbs_dir.is_dir():
            continue

        images = sorted_thumbs(thumbs_dir)
        if not images:
            continue

        cover = images[0]
        page_links.append(f'''<div class="container">
                <div class="banner" id="{collection_dir.name}" style="background-image: url('/photos/{collection_dir.name}/full/{cover.name}'); background-size: cover; background-position: center;" onclick="location.href='/{collection_dir.name}'"></div>
                <div class="banner-text">{collection_dir.name.title()}</div>
            </div>''')

    pages = "\n".join(page_links)

    template = HOME_TEMPLATE.read_text()
    output = template.replace('<!-- PAGES_INJECT -->', pages)
    HOME_PAGE.write_text(output)

    print("Built home page successfully")


def build_gallery(collection_dir):
    thumbs_dir = collection_dir / "thumbs"
    if not thumbs_dir.is_dir():
        return

    images = sorted_thumbs(thumbs_dir)
    if not images:
        return

    image_elements = []
    for image in images:
        image_elements.append(f'''    <div class="photoGrid">
            <a href="/photos/{collection_dir.name}/full/{image.name}">
                <picture>
                    <source srcset="/photos/{collection_dir.name}/full/{image.name}" media="(max-width: 500px)">
                    <img src="/photos/{collection_dir.name}/thumbs/{image.name}" alt="" loading="lazy">
                </picture>
            </a>
        </div>''')

    grid = "\n".join(image_elements)

    template = GALLERY_TEMPLATE.read_text()
    output = template.replace('<!-- PHOTOS_INJECT -->', grid)

    output_dir = Path(collection_dir.name)
    output_dir.mkdir(exist_ok=True)
    (output_dir / "index.html").write_text(output)

    print(f"Built gallery page for {collection_dir.name}")


if __name__ == "__main__":
    convert_photos()
    build_home()
    for collection_dir in get_collections():
        build_gallery(collection_dir)
