from dataclasses import dataclass
from typing import Any

from src.classification.domain.entities import WikiPage


@dataclass(frozen=True)
class LoadedPageMeta:
    source_path: str
    parse_warning: str | None = None


@dataclass(frozen=True)
class LoadedPage:
    page: WikiPage
    meta: LoadedPageMeta


@dataclass(frozen=True)
class ClassificationLabelRecord:
    doc_id: str
    pageid: int | None
    title: str
    revision_id: int | None
    canonical_url: str | None
    entity_type: str
    subtypes: tuple[str, ...]
    confidence: float
    reasons: tuple[str, ...]
    matched_rules: tuple[str, ...]
    strategy_version: str
    source_path: str
    is_redirect: bool
    parse_warning: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "pageid": self.pageid,
            "title": self.title,
            "revision_id": self.revision_id,
            "canonical_url": self.canonical_url,
            "entity_type": self.entity_type,
            "subtypes": list(self.subtypes),
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "matched_rules": list(self.matched_rules),
            "strategy_version": self.strategy_version,
            "source_path": self.source_path,
            "is_redirect": self.is_redirect,
            "parse_warning": self.parse_warning,
        }


@dataclass(frozen=True)
class ClassificationReportRecord:
    source_mode: str
    total_discovered: int
    loaded_ok: int
    parse_warning_count: int
    misc_count: int
    low_conf_count: int
    conflict_count: int
    by_entity_type: dict[str, int]
    duration_ms: int
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_mode": self.source_mode,
            "total_discovered": self.total_discovered,
            "loaded_ok": self.loaded_ok,
            "parse_warning_count": self.parse_warning_count,
            "misc_count": self.misc_count,
            "low_conf_count": self.low_conf_count,
            "conflict_count": self.conflict_count,
            "by_entity_type": self.by_entity_type,
            "duration_ms": self.duration_ms,
            "generated_at": self.generated_at,
        }
