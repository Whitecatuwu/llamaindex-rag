import shutil
import unittest
import uuid
from pathlib import Path

from src.classification.infrastructure.sources.HtmlPageSource import HtmlPageSource


class HtmlPageSourceTests(unittest.TestCase):
    def test_html_source_handles_invalid_json(self):
        base_tmp = Path("data/tmp-tests")
        base_tmp.mkdir(parents=True, exist_ok=True)
        tmp_path = base_tmp / f"source_{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
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
            page = source.load(refs[0])
            self.assertEqual(page.title, "Broken")
            self.assertIsNotNone(page.parse_warning)
            self.assertIn("Category:Enemy Units", page.categories)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)
