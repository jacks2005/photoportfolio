"""Regression checks for sorting existing WebP photo pairs."""
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from build import capture_date
from sort_existing_photos import sort_existing_photos


class ExistingPhotoSorterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.photos = self.root / "photos"
        self.photos.mkdir()
        self.overrides = self.root / "collections.json"

    def tearDown(self):
        self.temp.cleanup()

    def photo(self, name, date=None, slug="berlin"):
        exif = Image.Exif()
        if date:
            exif[34665] = {36867: date}
        for folder in ("full", "thumbs"):
            path = self.photos / slug / folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (80, 60), "#667788").save(path, exif=exif)

    def dates(self, slug="berlin"):
        result = []
        paths = sorted(
            (self.photos / slug / "full").glob("*.webp"),
            key=lambda item: int(item.stem.split("-")[-1]),
        )
        for path in paths:
            with Image.open(path) as image:
                result.append(capture_date(image.getexif().get_ifd(34665).get(36867)))
        return result

    def test_renumbers_pairs_and_updates_filename_overrides(self):
        self.photo("image-1.webp", "2024:04:30 10:00:00")
        self.photo("image-2.webp")
        self.photo("image-3.webp", "2024:04:29 10:00:00")
        self.overrides.write_text(json.dumps({
            "berlin": {
                "cover": "image-1.webp",
                "photo_layouts": {"image-2.webp": "solo", "image-3.webp": "wide"},
            }
        }), encoding="utf-8")

        sort_existing_photos(self.photos, self.overrides)

        self.assertEqual(self.dates(), [
            None,
            capture_date("2024:04:29 10:00:00"),
            capture_date("2024:04:30 10:00:00"),
        ])
        config = json.loads(self.overrides.read_text(encoding="utf-8"))
        self.assertEqual(config["berlin"]["cover"], "image-3.webp")
        self.assertEqual(config["berlin"]["photo_layouts"], {
            "image-1.webp": "solo",
            "image-2.webp": "wide",
        })
        first_result = {path: path.read_bytes() for path in self.photos.rglob("*.webp")}
        sort_existing_photos(self.photos, self.overrides)
        self.assertEqual(first_result, {path: path.read_bytes() for path in self.photos.rglob("*.webp")})

    def test_rejects_unmatched_pairs_before_renaming(self):
        self.photo("image-1.webp")
        (self.photos / "berlin/thumbs/image-1.webp").unlink()
        with self.assertRaisesRegex(ValueError, "missing thumbnail"):
            sort_existing_photos(self.photos, self.overrides)
        self.assertTrue((self.photos / "berlin/full/image-1.webp").is_file())

    def test_dry_run_does_not_change_files_or_overrides(self):
        self.photo("image-1.webp", "2024:04:30 10:00:00")
        self.photo("image-2.webp", "2024:04:29 10:00:00")
        self.overrides.write_text('{"berlin": {"cover": "image-1.webp"}}', encoding="utf-8")
        before = {path: path.read_bytes() for path in self.photos.rglob("*.webp")}

        sort_existing_photos(self.photos, self.overrides, dry_run=True)

        self.assertEqual(before, {path: path.read_bytes() for path in self.photos.rglob("*.webp")})
        self.assertEqual(self.overrides.read_text(encoding="utf-8"), '{"berlin": {"cover": "image-1.webp"}}')


if __name__ == "__main__":
    unittest.main()
