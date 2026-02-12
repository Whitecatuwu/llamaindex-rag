import sqlite3
import unittest

from src.classification.infrastructure.sources.RegistryPageSource import RegistryPageSource
from tests.utils.tempdir import managed_temp_dir


class RegistryPageSourceTests(unittest.TestCase):
    def test_load_fallback_parses_json_categories_first(self):
        with managed_temp_dir("registry_source_json_categories") as tmp:
            db_path = tmp / "wiki_registry.db"
            conn = sqlite3.connect(db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    CREATE TABLE pages (
                        page_id INTEGER PRIMARY KEY,
                        title TEXT UNIQUE,
                        last_revid INTEGER,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        file_path TEXT,
                        categories TEXT
                    )
                    """
                )
                cur.execute(
                    "INSERT INTO pages(page_id, title, last_revid, file_path, categories) VALUES (?, ?, ?, ?, ?)",
                    (10, "Title", 20, "", '["Category:A","Category:B"]'),
                )
                conn.commit()
            finally:
                conn.close()

            source = RegistryPageSource(str(db_path))
            refs = source.discover()
            self.assertEqual(len(refs), 1)
            loaded = source.load(refs[0])
            self.assertEqual(loaded.page.categories, ("Category:A", "Category:B"))

    def test_load_fallback_returns_empty_categories_for_invalid_json(self):
        with managed_temp_dir("registry_source_invalid_categories") as tmp:
            db_path = tmp / "wiki_registry.db"
            conn = sqlite3.connect(db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    CREATE TABLE pages (
                        page_id INTEGER PRIMARY KEY,
                        title TEXT UNIQUE,
                        last_revid INTEGER,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        file_path TEXT,
                        categories TEXT
                    )
                    """
                )
                cur.execute(
                    "INSERT INTO pages(page_id, title, last_revid, file_path, categories) VALUES (?, ?, ?, ?, ?)",
                    (11, "LegacyLike", 21, "", "Category:A, Category:B"),
                )
                conn.commit()
            finally:
                conn.close()

            source = RegistryPageSource(str(db_path))
            refs = source.discover()
            self.assertEqual(len(refs), 1)
            loaded = source.load(refs[0])
            self.assertEqual(loaded.page.categories, ())
