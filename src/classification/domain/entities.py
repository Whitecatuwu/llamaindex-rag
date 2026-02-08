from dataclasses import dataclass, field
from typing import Any

from src.classification.domain.types import EntityType, SubtypeTag


@dataclass(frozen=True)
class PageRef:
    source_id: str
    location: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WikiPage:
    pageid: int | None
    title: str
    revid: int | None
    timestamp: str | None
    canonical_url: str | None
    categories: tuple[str, ...]
    content: str
    is_redirect: bool

    @property
    def doc_id(self) -> str:
        if self.pageid is not None:
            return str(self.pageid)
        return self.title


@dataclass(frozen=True)
class Classification:
    entity_type: EntityType
    subtypes: tuple[SubtypeTag, ...]
    confidence: float
    reasons: tuple[str, ...]
    matched_rules: tuple[str, ...]
    strategy_version: str
