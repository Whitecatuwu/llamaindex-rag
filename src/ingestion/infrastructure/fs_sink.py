import json
from pathlib import Path

from src.ingestion.domain.models import WikiPageDoc
from src.ingestion.domain.rules import make_filename


class JsonFileSink:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_page_doc(self, page_doc: WikiPageDoc) -> Path:
        filename = make_filename(page_doc.title, page_doc.pageid)
        file_path = self.output_dir / filename
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(page_doc.to_dict(), f, ensure_ascii=False, indent=2)
        return file_path
