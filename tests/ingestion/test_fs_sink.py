import json
import unittest

from src.ingestion.domain.models import WikiPageDoc
from src.ingestion.infrastructure.fs_sink import JsonFileSink
from tests.utils.tempdir import managed_temp_dir


class JsonFileSinkTests(unittest.TestCase):
    def test_write_page_doc_uses_stable_filename_and_schema(self):
        with managed_temp_dir("fs_sink") as tmp:
            sink = JsonFileSink(tmp)
            page = WikiPageDoc(
                source="battlecats.miraheze.org",
                pageid=8,
                title="A/B Test",
                canonical_url="https://battlecats.miraheze.org/wiki/A_B_Test",
                revid=9,
                timestamp="2020-01-01T00:00:00Z",
                content_model="wikitext",
                categories=("Category:X",),
                description="unit-description",
                content="abc",
                extract="abc-extract",
                is_redirect=False,
                redirect_target=None,
                fetched_at="2020-01-01T00:00:01Z",
                http={"status": 200, "etag": "e", "last_modified": "m"},
            )

            file_path = sink.write_page_doc(page)
            self.assertEqual(file_path.name, "A_B Test_8.json")

            payload = json.loads(file_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["pageid"], 8)
            self.assertEqual(payload["title"], "A/B Test")
            self.assertEqual(payload["description"], "unit-description")
            self.assertEqual(payload["extract"], "abc-extract")
            self.assertIn("http", payload)
            self.assertEqual(payload["redirects_from"], [])
