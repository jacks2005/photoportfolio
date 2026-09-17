"""Generator regression checks; all generated fixture files stay in a temp directory."""
from contextlib import redirect_stdout
from html.parser import HTMLParser
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import build


def read_html(path):
    return path.read_text(encoding='utf-8')


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        self.tags.append((tag, dict(attributes)))

    def photos(self):
        return [attrs for tag, attrs in self.tags if tag == 'a' and 'data-photo' in attrs]


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.photos = self.root / 'photos'
        self.photos.mkdir()
        self.output = self.root / 'site'
        self.overrides = self.root / 'collections.json'
        self.photo_patch = patch.object(build, 'PHOTOS_ROOT', self.photos)
        self.photo_patch.start()

    def tearDown(self):
        self.photo_patch.stop()
        self.temp.cleanup()

    def photo(self, slug, filename, size=(80, 60), date=None, exported=None):
        exif = Image.Exif()
        exif[271] = 'FUJIFILM'
        exif[272] = 'X-T2'
        details = {33434: 0.002, 33437: 8.0, 34855: 200, 42036: 'A "lens" & more'}
        if date:
            details[36867] = date
        if exported:
            exif[306] = exported
        exif[34665] = details
        for folder in ('full', 'thumbs'):
            path = self.photos / slug / folder / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            image = Image.new('RGB', size, '#667788')
            if folder == 'thumbs':
                image.thumbnail((40, 40))
            image.save(path, exif=exif)

    def raw_photo(self, slug, filename, date=None):
        exif = Image.Exif()
        if date:
            exif[34665] = {36867: date}
        path = self.photos / slug / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (80, 60), '#667788').save(path, exif=exif)

    def generate(self):
        with redirect_stdout(StringIO()):
            return build.build_site(self.output, self.overrides)

    def test_converter_numbers_raw_photos_by_capture_date(self):
        self.raw_photo('berlin', 'a-latest.jpg', '2024:04:30 10:00:00')
        self.raw_photo('berlin', 'm-undated.jpg')
        self.raw_photo('berlin', 'z-earliest.jpg', '2024:04:29 10:00:00')

        with redirect_stdout(StringIO()):
            build.convert_photos()

        images = [
            build.read_photo('berlin', self.photos / f'berlin/thumbs/image-{number}.webp')
            for number in range(1, 4)
        ]
        self.assertEqual([photo['date'] for photo in images], [
            None,
            build.capture_date('2024:04:29 10:00:00'),
            build.capture_date('2024:04:30 10:00:00'),
        ])
        self.assertFalse(any((self.photos / 'berlin').glob('*.jpg')))

    def test_inventory_order_dates_and_all_are_separate(self):
        self.photo('all', 'image-1.webp', date='2020:06:16 10:00:00')
        self.photo('berlin', 'image-2.webp', date='2024:04:29 10:00:00')
        self.photo('berlin', 'image-10.webp', date='2024:04:30 10:00:00')
        self.photo('camden', 'image-1.webp', date='2024:05:18 10:00:00')
        collections = self.generate()
        berlin = collections[1]
        self.assertEqual([c['number'] for c in collections], ['ALL', '001', '002'])
        self.assertEqual([p['name'] for p in berlin['images']], ['image-10.webp', 'image-2.webp'])
        self.assertEqual(berlin['cover']['name'], 'image-10.webp')
        self.assertEqual(berlin['dates'], '29.04.2024 — 30.04.2024')
        self.assertIn('1/500 s / f/8 / ISO 200', berlin['images'][0]['metadata'])
        home = Page(read_html(self.output / 'index.html'))
        self.assertEqual(sum('data-project' in a for _, a in home.tags), 2)
        self.assertEqual(sum('data-theme-toggle' in a for _, a in home.tags), 1)
        home_images = [attributes for tag, attributes in home.tags if tag == 'img']
        self.assertTrue(home_images)
        self.assertTrue(all('/thumbs/' in image['src'] for image in home_images))
        self.assertTrue(all('srcset' not in image for image in home_images))
        self.assertEqual(len(Page(read_html(self.output / 'all/index.html')).photos()), 1)

    def test_undated_and_invalid_capture_dates_ignore_export_time(self):
        self.photo('ghosts', 'image-1.webp', exported='2026:09:01 12:00:00')
        self.photo('ghosts', 'image-2.webp', date='invalid')
        c = self.generate()[0]
        self.assertIsNone(c['year'])
        self.assertEqual(c['dates'], 'Undated')
        self.assertNotIn('2026', c['images'][0]['metadata'])
        self.assertIn('<h2>Undated</h2>', read_html(self.output / 'archive/index.html'))

    def test_overrides_escape_text_and_leave_photo_order_intact(self):
        self.photo('berlin', 'image-1.webp')
        self.photo('berlin', 'image-2.webp')
        title = '<script>alert("x")</script> & $title'
        self.overrides.write_text(json.dumps({'berlin': {'title': title, 'location': 'A & B', 'dates': ['2025-01-01', '2025-02-02'], 'cover': 'image-1.webp'}}))
        c = self.generate()[0]
        self.assertEqual(c['year'], 2025)
        self.assertEqual(c['cover']['name'], 'image-1.webp')
        home = read_html(self.output / 'index.html')
        self.assertNotIn('<script>alert', home)
        self.assertIn('&lt;script&gt;', home)
        self.assertIn('$title', home)
        page = Page(read_html(self.output / 'berlin/index.html'))
        self.assertTrue(page.photos()[0]['href'].endswith('image-2.webp'))
        self.assertEqual(page.photos()[0]['data-title'], title + ' — photograph 001')
        self.assertIn('A "lens" & more', page.photos()[0]['data-metadata'])

    def test_invalid_overrides_fail_clearly(self):
        self.photo('berlin', 'image-1.webp')
        self.overrides.write_text(json.dumps({'berlin': {'cover': 'missing.webp'}}))
        with self.assertRaisesRegex(ValueError, 'Unknown cover'):
            self.generate()
        self.overrides.write_text(json.dumps({'berlin': {'dates': ['2026-01-01', '2025-01-01']}}))
        with self.assertRaisesRegex(ValueError, 'Reversed date range'):
            self.generate()

    def test_empty_collections_and_empty_site(self):
        (self.photos / 'empty/thumbs').mkdir(parents=True)
        self.assertEqual(self.generate(), [])
        self.assertIn('No projects', read_html(self.output / 'index.html'))
        self.assertFalse((self.output / 'empty').exists())
        self.assertFalse((self.output / 'info/index.html').exists())

    def test_empty_config_keeps_mixed_orientations_on_separate_rows(self):
        for i, size in [(5, (80, 60)), (4, (40, 60)), (3, (40, 60)), (2, (60, 60)), (1, (80, 60))]:
            self.photo('mixed', f'image-{i}.webp', size=size)
        self.overrides.write_text('{}')
        self.generate()
        html = read_html(self.output / 'mixed/index.html')
        self.assertNotIn('class="portrait-pair"', html)
        self.assertEqual(html.count('class="editorial-row"'), 5)
        page = Page(html)
        self.assertEqual([a['data-filename'] for a in page.photos()], [f'image-{i}.webp' for i in range(5, 0, -1)])
        self.assertEqual(sum(tag == 'figcaption' for tag, _ in page.tags), 5)
        for tag, attrs in page.tags:
            if tag == 'img' and 'srcset' in attrs:
                self.assertIn('width', attrs)
                self.assertIn('height', attrs)
                self.assertIn('sizes', attrs)

    def test_repeat_generation_is_identical_and_preserves_assets(self):
        self.photo('berlin', 'image-1.webp', date='2024:04:29 10:00:00')
        self.photo('all', 'image-1.webp')
        assets = {p: p.read_bytes() for p in self.photos.rglob('*.webp')}
        self.generate()
        pages = {p: p.read_bytes() for p in self.output.rglob('*.html')}
        self.generate()
        self.assertEqual(pages, {p: p.read_bytes() for p in self.output.rglob('*.html')})
        self.assertEqual(assets, {p: p.read_bytes() for p in self.photos.rglob('*.webp')})

    def test_missing_full_image_has_actionable_error(self):
        self.photo('berlin', 'image-1.webp')
        (self.photos / 'berlin/full/image-1.webp').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing full image'):
            self.generate()

    def test_per_photo_layouts_preserve_order_and_captions(self):
        for i in range(1, 7):
            self.photo('custom', f'image-{i}.webp', size=(40, 60))
        self.overrides.write_text(json.dumps({'custom': {
            'default_layout': 'solo',
            'photo_layouts': {'image-5.webp': 'pair-next', 'image-3.webp': 'left', 'image-2.webp': 'right'}
        }}))
        self.generate()
        html = read_html(self.output / 'custom/index.html')
        page = Page(html)
        self.assertEqual([a['data-filename'] for a in page.photos()], [f'image-{i}.webp' for i in range(6, 0, -1)])
        self.assertEqual(html.count('class="portrait-pair"'), 1)
        self.assertEqual(html.count('class="editorial-row"'), 4)
        self.assertEqual(sum(t == 'figcaption' for t, _ in page.tags), 6)

    def test_explicit_solo_keeps_portraits_separate(self):
        for i in range(1, 4):
            self.photo('custom', f'image-{i}.webp', size=(40, 60))
        self.overrides.write_text(json.dumps({'custom': {'photo_layouts': {'image-1.webp': 'solo'}}}))
        self.generate()
        html = read_html(self.output / 'custom/index.html')
        self.assertNotIn('class="portrait-pair"', html)
        self.assertEqual(html.count('class="editorial-row"'), 3)

    def test_automatic_single_photos_are_centered(self):
        for i in range(1, 7):
            self.photo('custom', f'image-{i}.webp')
        self.generate()
        page = Page(read_html(self.output / 'custom/index.html'))
        classes = [attrs['class'].split() for tag, attrs in page.tags if tag == 'figure']
        self.assertEqual(len(classes), 6)
        self.assertTrue(all('wide' in value or 'centered' in value for value in classes))
        self.assertTrue(all('left' not in value and 'right' not in value for value in classes))

    def test_manual_pair_supports_landscapes_and_first_photo(self):
        for i in range(1, 3):
            self.photo('custom', f'image-{i}.webp')
        self.overrides.write_text(json.dumps({'custom': {'photo_layouts': {'image-2.webp': 'pair-next'}}}))
        self.generate()
        html = read_html(self.output / 'custom/index.html')
        self.assertEqual(html.count('class="portrait-pair"'), 1)
        self.assertEqual(len(Page(html).photos()), 2)

    def test_invalid_layouts_fail_before_writing_pages(self):
        for i in range(1, 4):
            self.photo('custom', f'image-{i}.webp')
        cases = [({'missing.webp': 'solo'}, 'unknown photo'),
                 ({'image-1.webp': 'huge'}, 'unknown layout'),
                 ({'image-1.webp': 'pair-next'}, 'following photo'),
                 ({'image-3.webp': 'pair-next', 'image-2.webp': 'solo'}, 'conflicts'),
                 ({'image-3.webp': 'pair-next', 'image-2.webp': 'pair-next'}, 'conflicts')]
        for layouts, message in cases:
            with self.subTest(layouts=layouts):
                self.overrides.write_text(json.dumps({'custom': {'photo_layouts': layouts}}))
                with self.assertRaisesRegex(ValueError, message):
                    self.generate()
                self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
