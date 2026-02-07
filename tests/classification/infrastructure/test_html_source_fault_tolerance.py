import unittest

from src.classification.infrastructure.sources.HtmlPageSource import HtmlPageSource
from tests.utils.tempdir import managed_temp_dir


class HtmlPageSourceTests(unittest.TestCase):
    def test_html_source_handles_invalid_json(self):
        with managed_temp_dir("source") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            bad = input_dir / "bad.json"
            bad.write_text(
                '{\n'
                '  "pageid": 42,\n'
                '  "title": "Broken",\n'
                '  "revid": 100,\n'
                '  "categories": ["Category:Enemy Units"],\n'
                '  "content": "broken " quote",\n'
                '  "is_redirect": false\n'
                '}',
                encoding="utf-8",
            )

            source = HtmlPageSource(str(input_dir))
            refs = source.discover()
            self.assertEqual(len(refs), 1)
            loaded = source.load(refs[0])
            self.assertEqual(loaded.page.title, "Broken")
            self.assertIsNotNone(loaded.meta.parse_warning)
            self.assertIn("Category:Enemy Units", loaded.page.categories)
