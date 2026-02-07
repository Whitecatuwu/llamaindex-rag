import json
import re
from pathlib import Path

from src.classification.application.ports import PageSourcePort
from src.classification.domain.entities import PageRef, WikiPage
from src.config.logger_config import logger


class HtmlPageSource(PageSourcePort):
    def __init__(self, input_dir: str) -> None:
        self.input_dir = Path(input_dir)

    def discover(self) -> list[PageRef]:
        refs: list[PageRef] = []
        for path in sorted(self.input_dir.glob("*.json")):
            refs.append(PageRef(source_id=path.stem, location=str(path)))
        logger.info("HTML source discovered {} pages from {}", len(refs), str(self.input_dir))
        return refs

    def load(self, ref: PageRef) -> WikiPage:
        path = Path(ref.location)
        raw = path.read_text(encoding="utf-8", errors="replace")

        try:
            parsed = json.loads(raw)
            return self._from_parsed(path, parsed, parse_warning=None)
        except json.JSONDecodeError as exc:
            # Fault-tolerant path keeps pipeline running for malformed JSON files.
            fallback = self._fallback_extract(raw)
            warning = f"json_decode_error:{exc.msg}"
            logger.warning("Failed to parse JSON file {}, fallback extractor used: {}", str(path), warning)
            return self._from_parsed(path, fallback, parse_warning=warning)

    @staticmethod
    def _from_parsed(path: Path, parsed: dict, parse_warning: str | None) -> WikiPage:
        categories = tuple(sorted({str(c).strip() for c in parsed.get("categories", []) if str(c).strip()}))
        return WikiPage(
            pageid=HtmlPageSource._to_int(parsed.get("pageid")),
            title=str(parsed.get("title", "")),
            revid=HtmlPageSource._to_int(parsed.get("revid")),
            timestamp=parsed.get("timestamp"),
            canonical_url=parsed.get("canonical_url"),
            categories=categories,
            content=str(parsed.get("content", "")),
            is_redirect=bool(parsed.get("is_redirect", False)),
            source_path=str(path),
            parse_warning=parse_warning,
        )

    @staticmethod
    def _to_int(value) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _fallback_extract(raw: str) -> dict:
        def find_str(key: str) -> str | None:
            # This intentionally only captures simple values for fault-tolerance mode.
            match = re.search(rf'"{key}"\s*:\s*"([^"\n]*)"', raw)
            return match.group(1) if match else None

        def find_int(key: str) -> int | None:
            match = re.search(rf'"{key}"\s*:\s*(\d+)', raw)
            return int(match.group(1)) if match else None

        categories_block = re.search(r'"categories"\s*:\s*\[(.*?)\]', raw, re.S)
        categories: list[str] = []
        if categories_block:
            categories = re.findall(r'"(Category:[^"\n]+)"', categories_block.group(1))

        is_redirect_match = re.search(r'"is_redirect"\s*:\s*(true|false)', raw, re.I)
        is_redirect = bool(is_redirect_match and is_redirect_match.group(1).lower() == "true")
        return {
            "pageid": find_int("pageid"),
            "title": find_str("title") or Path("unknown").stem,
            "revid": find_int("revid"),
            "timestamp": find_str("timestamp"),
            "canonical_url": find_str("canonical_url"),
            "categories": categories,
            "content": "",
            "is_redirect": is_redirect,
        }
