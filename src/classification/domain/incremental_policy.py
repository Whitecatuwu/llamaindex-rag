from dataclasses import dataclass


@dataclass(frozen=True)
class StateFingerprint:
    source_mode: str
    last_revid: int | None
    content_hash: str | None
    strategy_version: str


@dataclass(frozen=True)
class PageFingerprint:
    source_mode: str
    revid: int | None
    content_hash: str | None
    strategy_version: str


@dataclass(frozen=True)
class IncrementalDecision:
    should_classify: bool
    reason: str


def evaluate_incremental_decision(existing: StateFingerprint | None, current: PageFingerprint) -> IncrementalDecision:
    if existing is None:
        return IncrementalDecision(should_classify=True, reason="state_miss")
    if existing.source_mode != current.source_mode:
        return IncrementalDecision(should_classify=True, reason="source_mode_changed")
    if existing.strategy_version != current.strategy_version:
        return IncrementalDecision(should_classify=True, reason="strategy_version_changed")
    if current.content_hash is None:
        return IncrementalDecision(should_classify=True, reason="hash_missing")
    if current.revid is not None:
        if existing.last_revid is None:
            return IncrementalDecision(should_classify=True, reason="existing_revid_missing")
        if int(existing.last_revid) != int(current.revid):
            return IncrementalDecision(should_classify=True, reason="revid_changed")
        if existing.content_hash is None:
            return IncrementalDecision(should_classify=True, reason="existing_hash_missing")
        if existing.content_hash != current.content_hash:
            return IncrementalDecision(should_classify=True, reason="content_hash_changed_same_revid")
        return IncrementalDecision(should_classify=False, reason="revid_and_hash_hit")
    if existing.content_hash != current.content_hash:
        return IncrementalDecision(should_classify=True, reason="content_hash_changed")
    return IncrementalDecision(should_classify=False, reason="content_hash_hit")
