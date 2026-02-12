import sqlite3
import json
from pathlib import Path

from src.ingestion.domain.models import RegistryRecord, WikiPageDoc


class SQLiteRegistryRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.init_schema()

    def init_schema(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pages (
                page_id INTEGER PRIMARY KEY,
                title TEXT UNIQUE,
                last_revid INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                categories TEXT
            )
            """
        )
        self.conn.commit()

    def get_local_state(self) -> dict[int, int]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT page_id, last_revid FROM pages")
        return {int(row[0]): int(row[1]) for row in cursor.fetchall()}

    def upsert_page(self, page_doc: WikiPageDoc, file_path: Path) -> RegistryRecord:
        categories = json.dumps(list(page_doc.categories), ensure_ascii=False)
        cursor = self.conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                "SELECT page_id FROM pages WHERE title = ? AND page_id != ?",
                (page_doc.title, page_doc.pageid),
            )
            conflicting_ids = [int(row[0]) for row in cursor.fetchall()]
            for page_id in conflicting_ids:
                cursor.execute("DELETE FROM pages WHERE page_id = ?", (page_id,))

            cursor.execute(
                """
                INSERT INTO pages (page_id, title, last_revid, file_path, categories, last_updated)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(page_id) DO UPDATE SET
                    title = excluded.title,
                    last_revid = excluded.last_revid,
                    file_path = excluded.file_path,
                    categories = excluded.categories,
                    last_updated = CURRENT_TIMESTAMP
                """,
                (page_doc.pageid, page_doc.title, page_doc.revid, str(file_path), categories),
            )
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            raise

        return RegistryRecord(
            page_id=page_doc.pageid,
            title=page_doc.title,
            last_revid=page_doc.revid,
            file_path=str(file_path),
            categories=categories,
        )

    def close(self) -> None:
        self.conn.close()
