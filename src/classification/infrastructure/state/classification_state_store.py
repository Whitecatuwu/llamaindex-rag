from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

from src.classification.application.ports import ClassificationStatePort
from src.classification.domain.incremental_policy import StateFingerprint


@dataclass(frozen=True)
class ClassificationStateRow:
    state_key: str
    source_mode: str
    last_revid: int | None
    content_hash: str | None
    strategy_version: str
    entity_type: str
    source_path: str
    last_classified_at: str


class ClassificationStateStore(ClassificationStatePort):
    RECOVERY_SUFFIX: ClassVar[str] = ".corrupt"

    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        try:
            self._ensure_schema()
        except Exception:
            self._conn.close()
            raise

    @classmethod
    def create_with_recovery(cls, db_path: str) -> tuple[ClassificationStateStore, bool, str | None]:
        try:
            return cls(db_path), False, None
        except sqlite3.DatabaseError:
            original = Path(db_path)
            if not original.exists():
                raise
            backup = original.with_suffix(
                f"{original.suffix}{cls.RECOVERY_SUFFIX}.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            )
            original.replace(backup)
            store = cls(db_path)
            return store, True, str(backup)

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS classification_state (
                doc_id TEXT PRIMARY KEY,
                source_mode TEXT NOT NULL,
                last_revid INTEGER,
                content_hash TEXT,
                strategy_version TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                source_path TEXT NOT NULL,
                last_classified_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_class_state_source_mode
            ON classification_state(source_mode)
            """
        )
        self._conn.commit()

    def _get_row(self, state_key: str) -> ClassificationStateRow | None:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT doc_id, source_mode, last_revid, content_hash, strategy_version, entity_type, source_path, last_classified_at
            FROM classification_state
            WHERE doc_id = ?
            """,
            (state_key,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return ClassificationStateRow(
            state_key=str(row[0]),
            source_mode=str(row[1]),
            last_revid=int(row[2]) if row[2] is not None else None,
            content_hash=str(row[3]) if row[3] is not None else None,
            strategy_version=str(row[4]),
            entity_type=str(row[5]),
            source_path=str(row[6]),
            last_classified_at=str(row[7]),
        )

    def get(self, state_key: str) -> StateFingerprint | None:
        row = self._get_row(state_key)
        if row is None:
            return None
        return StateFingerprint(
            source_mode=row.source_mode,
            last_revid=row.last_revid,
            content_hash=row.content_hash,
            strategy_version=row.strategy_version,
        )

    def upsert(
        self,
        *,
        state_key: str,
        source_mode: str,
        last_revid: int | None,
        content_hash: str | None,
        strategy_version: str,
        entity_type: str,
        source_path: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO classification_state (
                doc_id, source_mode, last_revid, content_hash, strategy_version, entity_type, source_path, last_classified_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                source_mode = excluded.source_mode,
                last_revid = excluded.last_revid,
                content_hash = excluded.content_hash,
                strategy_version = excluded.strategy_version,
                entity_type = excluded.entity_type,
                source_path = excluded.source_path,
                last_classified_at = excluded.last_classified_at
            """,
            (
                state_key,
                source_mode,
                last_revid,
                content_hash,
                strategy_version,
                entity_type,
                source_path,
                now,
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
