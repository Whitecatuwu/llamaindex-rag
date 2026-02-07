from typing import Protocol, Sequence, runtime_checkable

from src.classification.domain.entities import PageRef, WikiPage

@runtime_checkable
class PageSourcePort(Protocol):
    def discover(self) -> Sequence[PageRef]: ...
    """Discover page references without parsing full payload."""

    def load(self, ref: PageRef) -> WikiPage: ...
    """Load and parse a page from a discovered reference."""


@runtime_checkable
class ClassificationSinkPort(Protocol):
    def write_label(self, row: dict) -> None: ...
    """Write one classified page row."""

    def write_review(self, row: dict) -> None: ...
    """Write one row to review queue."""

    def close(self) -> None: ...
    """Release resources."""


@runtime_checkable
class ReportSinkPort(Protocol):
    def write_report(self, report: dict) -> None: ...
    """Persist aggregate run report."""
