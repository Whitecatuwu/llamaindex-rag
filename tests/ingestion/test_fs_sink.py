import json
import tempfile
import unittest
from pathlib import Path

from src.ingestion.domain.models import WikiPageDoc
from src.ingestion.infrastructure.fs_sink import JsonFileSink


class JsonFileSinkTests(unittest.TestCase):
    def test_write_page_doc_uses_stable_filename_and_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = JsonFileSink(Path(tmp))
            page = WikiPageDoc(
                source="battlecats.miraheze.org",
                pageid=8,
                title="A/B Test",
                canonical_url="https://battlecats.miraheze.org/wiki/A_B_Test",
                revid=9,
                timestamp="2020-01-01T00:00:00Z",
                content_model="wikitext",
                categories=("Category:X",),
                content="abc",
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
            self.assertIn("http", payload)

