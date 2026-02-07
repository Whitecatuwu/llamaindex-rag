import sqlite3
from pathlib import Path

from src.classification.application.ports import PageSourcePort
from src.classification.domain.entities import PageRef, WikiPage
from src.classification.infrastructure.sources.HtmlPageSource import HtmlPageSource


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
            return refs
        finally:
            conn.close()

    def load(self, ref: PageRef) -> WikiPage:
        file_path = ref.location
        if file_path and Path(file_path).exists():
            return HtmlPageSource(input_dir=".").load(PageRef(source_id=ref.source_id, location=file_path))

        raw_categories = str(ref.metadata.get("categories", "") or "")
        categories = tuple(c.strip() for c in raw_categories.split(",") if c.strip())
        return WikiPage(
            pageid=int(ref.metadata["pageid"]) if ref.metadata.get("pageid") is not None else None,
            title=str(ref.metadata.get("title", "")),
            revid=int(ref.metadata["revid"]) if ref.metadata.get("revid") is not None else None,
            timestamp=None,
            canonical_url=None,
            categories=categories,
            content="",
            is_redirect=False,
            source_path=f"registry:{self.db_path}:{ref.source_id}",
            parse_warning="missing_file_path",
        )
