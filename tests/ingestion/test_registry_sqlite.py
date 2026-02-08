import tempfile
import unittest
from pathlib import Path

from src.ingestion.domain.models import WikiPageDoc
from src.ingestion.infrastructure.registry_sqlite import SQLiteRegistryRepository


class RegistrySQLiteTests(unittest.TestCase):
    def test_init_get_and_upsert(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "wiki_registry.db"
            repo = SQLiteRegistryRepository(db_path)
            try:
                self.assertEqual(repo.get_local_state(), {})

                page = WikiPageDoc(
                    source="battlecats.miraheze.org",
                    pageid=123,
                    title="Test Page",
                    canonical_url="https://battlecats.miraheze.org/wiki/Test_Page",
                    revid=456,
                    timestamp="2020-01-01T00:00:00Z",
                    content_model="wikitext",
                    categories=("Category:A", "Category:B"),
                    content="content",
                    is_redirect=False,
                    redirect_target=None,
                    fetched_at="2020-01-01T00:00:01Z",
                    http={"status": 200, "etag": "", "last_modified": ""},
                )
                record = repo.upsert_page(page, Path(tmp) / "page_123.json", remote_revid=456)
                self.assertEqual(record.page_id, 123)
                self.assertEqual(record.last_revid, 456)
                self.assertEqual(repo.get_local_state(), {123: 456})
            finally:
                repo.close()

