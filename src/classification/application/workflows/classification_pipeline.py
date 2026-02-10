from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter

from tqdm import tqdm
from src.classification.application.contracts import (
    ClassificationLabelRecord,
    ClassificationReportRecord,
)
from src.classification.application.ports import (
    ClassificationSinkPort,
    ClassificationStatePort,
    PageSourcePort,
    ReportSinkPort,
)
from src.classification.domain.classifier import RuleBasedClassifier
from src.classification.domain.content_hash import compute_content_hash
from src.classification.domain.incremental_policy import PageFingerprint, evaluate_incremental_decision
from src.classification.domain.rules import CLASSIFICATION_STRATEGY_VERSION
from src.config.logger_config import logger


@dataclass(frozen=True)
class PipelineConfig:
    source_mode: str
    low_confidence_threshold: float
    include_redirects: bool
    incremental: bool = True
    full_rebuild: bool = False
    show_progress: bool = True


@dataclass(frozen=True)
class PipelineSummary:
    total_pages: int
    classified_count: int
    misc_count: int
    low_conf_count: int
    ambiguity_count: int
    parse_warning_count: int
    by_entity_type: dict[str, int]
    source_mode: str
    duration_ms: int
    generated_at: str


class ClassificationPipeline:
    def __init__(
        self,
        source: PageSourcePort,
        classifier: RuleBasedClassifier,
        sink: ClassificationSinkPort,
        report_sink: ReportSinkPort,
        state_store: ClassificationStatePort | None = None,
        state_store_label: str | None = None,
        state_store_recovered: bool = False,
        state_store_recovered_from: str | None = None,
        state_store_init_error: str | None = None,
    ) -> None:
        self.source = source
        self.classifier = classifier
        self.sink = sink
        self.report_sink = report_sink
        self.state_store = state_store
        self.state_store_label = state_store_label
        self.state_store_recovered = state_store_recovered
        self.state_store_recovered_from = state_store_recovered_from
        self.state_store_init_error = state_store_init_error

    def run(self, config: PipelineConfig) -> PipelineSummary:
        started = perf_counter()
        refs = self.source.discover()
        state_hit_count = 0
        state_miss_count = 0
        skipped_unchanged_count = 0
        state_recovery_count = 0
        state_tracking_enabled = config.incremental or config.full_rebuild
        incremental_effective = config.incremental and not config.full_rebuild

        if self.state_store_recovered:
            state_recovery_count = 1
            logger.warning(
                "Classification state DB recovered: state_store_label={}, recovered_from={}",
                self.state_store_label,
                self.state_store_recovered_from,
            )

        if state_tracking_enabled and self.state_store is None:
            incremental_effective = False
            logger.warning(
                "Classification state store unavailable, fallback to stateless full classification: state_store_label={}, error={}",
                self.state_store_label,
                self.state_store_init_error or "not_configured",
            )

        logger.info(
            "Classification pipeline started: source_mode={}, discovered_pages={}, include_redirects={}, low_confidence_threshold={}, incremental={}, full_rebuild={}, state_store_label={}",
            config.source_mode,
            len(refs),
            config.include_redirects,
            config.low_confidence_threshold,
            config.incremental,
            config.full_rebuild,
            self.state_store_label,
        )

        classified_count = 0
        misc_count = 0
        low_conf_count = 0
        ambiguity_count = 0
        parse_warning_count = 0
        by_entity_type = {k: 0 for k in ("cat", "enemy", "stage", "update", "mechanic", "list", "misc", "invalid")}

        try:
            for ref in tqdm(
                refs,
                total=len(refs),
                desc="Classification pages",
                unit="page",
                leave=True,
                disable=not config.show_progress,
            ):
                loaded = self.source.load(ref)
                page = loaded.page
                if loaded.meta.parse_warning:
                    parse_warning_count += 1
                    logger.warning("Parse warning on page load: doc_id={}, warning={}", page.doc_id, loaded.meta.parse_warning)
                if page.is_redirect and not config.include_redirects:
                    logger.debug("Skip redirect page: doc_id={}, title={}", page.doc_id, page.title)
                    continue

                if page.pageid is None:
                    invalid_reasons = ["missing_pageid"]
                    if loaded.meta.parse_warning:
                        invalid_reasons.append(f"parse_warning:{loaded.meta.parse_warning}")
                    invalid_row = ClassificationLabelRecord(
                        doc_id=page.doc_id,
                        pageid=page.pageid,
                        title=page.title,
                        revision_id=page.revid,
                        canonical_url=page.canonical_url,
                        entity_type="invalid",
                        subtypes=(),
                        confidence=0.0,
                        reasons=tuple(invalid_reasons),
                        matched_rules=(),
                        strategy_version=CLASSIFICATION_STRATEGY_VERSION,
                        source_path=loaded.meta.source_path,
                        is_redirect=page.is_redirect,
                        parse_warning=loaded.meta.parse_warning,
                        is_ambiguous=False,
                    )
                    self.sink.write_label(invalid_row)
                    self.sink.write_review(invalid_row)
                    classified_count += 1
                    by_entity_type["invalid"] += 1
                    logger.warning(
                        "Invalid page classified due to missing pageid: source_path={}, title={}, revision_id={}, parse_warning={}",
                        loaded.meta.source_path,
                        page.title,
                        page.revid,
                        loaded.meta.parse_warning,
                    )
                    continue

                state_key = str(page.pageid)
                current_hash = compute_content_hash(page.content)
                if incremental_effective and self.state_store is not None:
                    decision = evaluate_incremental_decision(
                        existing=self.state_store.get(state_key),
                        current=PageFingerprint(
                            source_mode=config.source_mode,
                            revid=page.revid,
                            content_hash=current_hash,
                            strategy_version=CLASSIFICATION_STRATEGY_VERSION,
                        ),
                    )
                    if not decision.should_classify:
                        skipped_unchanged_count += 1
                        state_hit_count += 1
                        logger.debug(
                            "Incremental decision: action=skip, reason={}, doc_id={}, state_key={}, source_mode={}, revision_id={}",
                            decision.reason,
                            page.doc_id,
                            state_key,
                            config.source_mode,
                            page.revid,
                        )
                        continue
                    state_miss_count += 1
                    logger.debug(
                        "Incremental decision: action=classify, reason={}, doc_id={}, state_key={}, source_mode={}, revision_id={}",
                        decision.reason,
                        page.doc_id,
                        state_key,
                        config.source_mode,
                        page.revid,
                    )
                elif config.full_rebuild:
                    logger.debug(
                        "Incremental decision: action=classify, reason=full_rebuild, doc_id={}, state_key={}, source_mode={}, revision_id={}",
                        page.doc_id,
                        state_key,
                        config.source_mode,
                        page.revid,
                    )

                result = self.classifier.classify(page)
                row = ClassificationLabelRecord(
                    doc_id=page.doc_id,
                    pageid=page.pageid,
                    title=page.title,
                    revision_id=page.revid,
                    canonical_url=page.canonical_url,
                    entity_type=result.entity_type,
                    subtypes=tuple(result.subtypes),
                    confidence=result.confidence,
                    reasons=tuple(result.reasons),
                    matched_rules=tuple(result.matched_rules),
                    strategy_version=result.strategy_version,
                    source_path=loaded.meta.source_path,
                    is_redirect=page.is_redirect,
                    parse_warning=loaded.meta.parse_warning,
                    is_ambiguous=result.is_ambiguous,
                )
                self.sink.write_label(row)
                classified_count += 1
                by_entity_type[result.entity_type] += 1

                is_low_conf = result.confidence < config.low_confidence_threshold
                is_ambiguous = result.is_ambiguous
                needs_review = result.entity_type == "misc" or is_low_conf or result.is_ambiguous
                if needs_review:
                    self.sink.write_review(row)
                    logger.debug(
                        "Page enqueued for review: doc_id={}, entity_type={}, confidence={}, reasons={}",
                        page.doc_id,
                        result.entity_type,
                        result.confidence,
                        list(result.reasons),
                    )
                    if is_low_conf:
                        low_conf_count += 1
                    if is_ambiguous:
                        ambiguity_count += 1
                if result.entity_type == "misc":
                    misc_count += 1
                if self.state_store is not None:
                    self.state_store.upsert(
                        state_key=state_key,
                        source_mode=config.source_mode,
                        last_revid=page.revid,
                        content_hash=current_hash,
                        strategy_version=result.strategy_version,
                        entity_type=result.entity_type,
                        source_path=loaded.meta.source_path,
                    )
        finally:
            if self.state_store is not None:
                self.state_store.close()
            self.sink.close()

        duration_ms = int((perf_counter() - started) * 1000)
        summary = PipelineSummary(
            total_pages=len(refs),
            classified_count=classified_count,
            misc_count=misc_count,
            low_conf_count=low_conf_count,
            ambiguity_count=ambiguity_count,
            parse_warning_count=parse_warning_count,
            by_entity_type=by_entity_type,
            source_mode=config.source_mode,
            duration_ms=duration_ms,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self.report_sink.write_report(
            ClassificationReportRecord(
                source_mode=summary.source_mode,
                total_discovered=summary.total_pages,
                loaded_ok=summary.classified_count,
                parse_warning_count=summary.parse_warning_count,
                misc_count=summary.misc_count,
                low_conf_count=summary.low_conf_count,
                ambiguity_count=summary.ambiguity_count,
                by_entity_type=summary.by_entity_type,
                duration_ms=summary.duration_ms,
                generated_at=summary.generated_at,
            )
        )
        logger.info(
            "Classification pipeline completed: source_mode={}, duration_ms={}, classified_count={}, skipped_unchanged_count={}, misc_count={}, low_conf_count={}, ambiguity_count={}, parse_warning_count={}, state_hit_count={}, state_miss_count={}, state_recovery_count={}",
            summary.source_mode,
            summary.duration_ms,
            summary.classified_count,
            skipped_unchanged_count,
            summary.misc_count,
            summary.low_conf_count,
            summary.ambiguity_count,
            summary.parse_warning_count,
            state_hit_count,
            state_miss_count,
            state_recovery_count,
        )
        return summary
