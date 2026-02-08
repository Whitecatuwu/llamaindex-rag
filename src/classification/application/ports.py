from typing import Protocol, Sequence, runtime_checkable

from src.classification.application.contracts import (
    ClassificationLabelRecord,
    ClassificationReportRecord,
    LoadedPage,
)
from src.classification.domain.entities import PageRef
from src.classification.domain.incremental_policy import StateFingerprint


@runtime_checkable
class PageSourcePort(Protocol):
    def discover(self) -> Sequence[PageRef]: ...
    """Discover page references without parsing full payload."""

    def load(self, ref: PageRef) -> LoadedPage: ...
    """Load and parse a page from a discovered reference."""


@runtime_checkable
class ClassificationSinkPort(Protocol):
    def write_label(self, row: ClassificationLabelRecord) -> None: ...
    """Write one classified page row."""

    def write_review(self, row: ClassificationLabelRecord) -> None: ...
    """Write one row to review queue."""

    def close(self) -> None: ...
    """Release resources."""


@runtime_checkable
class ReportSinkPort(Protocol):
    def write_report(self, report: ClassificationReportRecord) -> None: ...
    """Persist aggregate run report."""


@runtime_checkable
class ClassificationStatePort(Protocol):
    def get(self, state_key: str) -> StateFingerprint | None: ...

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
    ) -> None: ...

    def close(self) -> None: ...
