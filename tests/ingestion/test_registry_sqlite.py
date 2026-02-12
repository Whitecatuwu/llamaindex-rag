import json
import unittest

from src.ingestion.domain.models import WikiPageDoc
from src.ingestion.infrastructure.registry_sqlite import SQLiteRegistryRepository
from tests.utils.tempdir import managed_temp_dir


def make_page(pageid: int, title: str, revid: int) -> WikiPageDoc:
    return WikiPageDoc(
        source="battlecats.miraheze.org",
        pageid=pageid,
        title=title,
        canonical_url=f"https://battlecats.miraheze.org/wiki/{title.replace(' ', '_')}",
        revid=revid,
        timestamp="2020-01-01T00:00:00Z",
        content_model="wikitext",
        categories=("Category:A", "Category:B"),
        description="",
        content="content",
        extract="extract",
        is_redirect=False,
        redirect_target=None,
        fetched_at="2020-01-01T00:00:01Z",
        http={"status": 200, "etag": "", "last_modified": ""},
    )


class RegistrySQLiteTests(unittest.TestCase):
    def test_init_get_and_upsert_uses_page_doc_revid(self):
        with managed_temp_dir("registry_basic") as tmp:
            db_path = tmp / "wiki_registry.db"
            repo = SQLiteRegistryRepository(db_path)
            try:
                self.assertEqual(repo.get_local_state(), {})
                page = make_page(123, "Test Page", 456)

                record = repo.upsert_page(page, tmp / "page_123.json")
                self.assertEqual(record.page_id, 123)
                self.assertEqual(record.last_revid, 456)
                self.assertEqual(record.categories, json.dumps(["Category:A", "Category:B"], ensure_ascii=False))
                self.assertEqual(repo.get_local_state(), {123: 456})
            finally:
                repo.close()

    def test_upsert_resolves_title_unique_conflict_by_replacing_old_page_id(self):
        with managed_temp_dir("registry_title_conflict") as tmp:
            db_path = tmp / "wiki_registry.db"
            repo = SQLiteRegistryRepository(db_path)
            try:
                old_page = make_page(1, "Shared Title", 10)
                new_page = make_page(2, "Shared Title", 20)

                repo.upsert_page(old_page, tmp / "old.json")
                record = repo.upsert_page(new_page, tmp / "new.json")

                self.assertEqual(record.page_id, 2)
                self.assertEqual(record.last_revid, 20)
                self.assertEqual(repo.get_local_state(), {2: 20})
            finally:
                repo.close()
