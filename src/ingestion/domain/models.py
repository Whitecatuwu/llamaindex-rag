from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PageRef:
    pageid: int
    remote_revid: int
    redirects_from: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PageDiscoveryResult:
    canonical_pages: dict[int, int]
    redirects_from: dict[int, tuple[str, ...]]


@dataclass(frozen=True)
class WikiPageDoc:
    source: str
    pageid: int
    title: str
    canonical_url: str
    revid: int
    timestamp: str
    content_model: str | None
    categories: tuple[str, ...]
    description: str
    content: str
    extract: str
    is_redirect: bool
    redirect_target: str | None
    fetched_at: str
    http: dict[str, Any]
    redirects_from: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "pageid": self.pageid,
            "title": self.title,
            "canonical_url": self.canonical_url,
            "revid": self.revid,
            "timestamp": self.timestamp,
            "content_model": self.content_model,
            "categories": list(self.categories),
            "description": self.description,
            "content": self.content,
            "extract": self.extract,
            "is_redirect": self.is_redirect,
            "redirect_target": self.redirect_target,
            "redirects_from": list(self.redirects_from),
            "fetched_at": self.fetched_at,
            "http": self.http,
        }


@dataclass(frozen=True)
class RegistryRecord:
    page_id: int
    title: str
    last_revid: int
    file_path: str
    categories: str


@dataclass(frozen=True)
class CrawlSummary:
    discovered_total: int
    queued_total: int
    processed_total: int
    failed_total: int
    skipped_total: int
