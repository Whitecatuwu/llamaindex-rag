import json
import sqlite3
from pathlib import Path

from src.classification.application.contracts import LoadedPage, LoadedPageMeta
from src.classification.application.ports import PageSourcePort
from src.classification.domain.entities import PageRef, WikiPage
from src.classification.infrastructure.sources.HtmlPageSource import HtmlPageSource
from src.config.logger_config import logger


class RegistryPageSource(PageSourcePort):
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def discover(self) -> list[PageRef]:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT page_id, title, last_revid, file_path, categories FROM pages ORDER BY page_id")
            refs = []
            for page_id, title, revid, file_path, categories in cur.fetchall():
                refs.append(
                    PageRef(
                        source_id=str(page_id),
                        location=file_path or "",
                        metadata={
                            "pageid": page_id,
                            "title": title,
                            "revid": revid,
                            "categories": categories,
                        },
                    )
                )
            logger.info("Registry source discovered {} pages from {}", len(refs), self.db_path)
            return refs
        finally:
            conn.close()

    def load(self, ref: PageRef) -> LoadedPage:
        file_path = ref.location
        if file_path and Path(file_path).exists():
            return HtmlPageSource(input_dir=".").load(PageRef(source_id=ref.source_id, location=file_path))

        raw_categories = str(ref.metadata.get("categories", "") or "")
        categories = self._parse_categories(raw_categories)
        logger.warning(
            "Registry page uses metadata fallback due to missing file path: source_id={}, db_path={}",
            ref.source_id,
            self.db_path,
        )
        page = WikiPage(
            pageid=int(ref.metadata["pageid"]) if ref.metadata.get("pageid") is not None else None,
            title=str(ref.metadata.get("title", "")),
            revid=int(ref.metadata["revid"]) if ref.metadata.get("revid") is not None else None,
            timestamp=None,
            canonical_url=None,
            categories=categories,
            content="",
            is_redirect=False,
        )
        return LoadedPage(
            page=page,
            meta=LoadedPageMeta(
                source_path=f"registry:{self.db_path}:{ref.source_id}",
                parse_warning="missing_file_path",
            ),
        )

    @staticmethod
    def _parse_categories(raw_categories: str) -> tuple[str, ...]:
        text = str(raw_categories or "").strip()
        if not text:
            return ()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return tuple(str(item).strip() for item in parsed if str(item).strip())
        except json.JSONDecodeError:
            logger.warning("Invalid JSON categories in registry metadata; returning empty categories.")
            return ()
        return ()
