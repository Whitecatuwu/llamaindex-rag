from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter

from src.classification.application.ports import (
    ClassificationSinkPort,
    PageSourcePort,
    ReportSinkPort,
)
from src.classification.domain.classifier import RuleBasedClassifier
from src.config.logger_config import logger


@dataclass(frozen=True)
class PipelineConfig:
    source_mode: str
    low_confidence_threshold: float
    include_redirects: bool


@dataclass(frozen=True)
class PipelineSummary:
    total_pages: int
    classified_count: int
    misc_count: int
    low_conf_count: int
    conflict_count: int
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
    ) -> None:
        self.source = source
        self.classifier = classifier
        self.sink = sink
        self.report_sink = report_sink

    def run(self, config: PipelineConfig) -> PipelineSummary:
        started = perf_counter()
        refs = self.source.discover()
        logger.info(
            "Classification pipeline started: source_mode={}, discovered_pages={}, include_redirects={}, low_confidence_threshold={}",
            config.source_mode,
            len(refs),
            config.include_redirects,
            config.low_confidence_threshold,
        )

        classified_count = 0
        misc_count = 0
        low_conf_count = 0
        conflict_count = 0
        parse_warning_count = 0
        by_entity_type = {k: 0 for k in ("cat", "enemy", "stage", "update", "mechanic", "list", "misc")}

        try:
            for ref in refs:
                page = self.source.load(ref)
                if page.parse_warning:
                    parse_warning_count += 1
                    logger.warning("Parse warning on page load: doc_id={}, warning={}", page.doc_id, page.parse_warning)
                if page.is_redirect and not config.include_redirects:
                    logger.debug("Skip redirect page: doc_id={}, title={}", page.doc_id, page.title)
                    continue

                result = self.classifier.classify(page)
                # Row is the persisted contract for labels/review artifacts.
                row = {
                    "doc_id": page.doc_id,
                    "pageid": page.pageid,
                    "title": page.title,
                    "revision_id": page.revid,
                    "canonical_url": page.canonical_url,
                    "entity_type": result.entity_type,
                    "subtypes": list(result.subtypes),
                    "confidence": result.confidence,
                    "reasons": list(result.reasons),
                    "matched_rules": list(result.matched_rules),
                    "strategy_version": result.strategy_version,
                    "source_path": page.source_path,
                    "is_redirect": page.is_redirect,
                    "parse_warning": page.parse_warning,
                }
                self.sink.write_label(row)
                classified_count += 1
                by_entity_type[result.entity_type] += 1

                is_low_conf = result.confidence < config.low_confidence_threshold
                is_conflict = any("low_margin_conflict" in reason for reason in result.reasons)
                needs_review = result.entity_type == "misc" or is_low_conf or is_conflict
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
                    if is_conflict:
                        conflict_count += 1
                if result.entity_type == "misc":
                    misc_count += 1
        finally:
            self.sink.close()

        duration_ms = int((perf_counter() - started) * 1000)
        summary = PipelineSummary(
            total_pages=len(refs),
            classified_count=classified_count,
            misc_count=misc_count,
            low_conf_count=low_conf_count,
            conflict_count=conflict_count,
            parse_warning_count=parse_warning_count,
            by_entity_type=by_entity_type,
            source_mode=config.source_mode,
            duration_ms=duration_ms,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self.report_sink.write_report(
            {
                "source_mode": summary.source_mode,
                "total_discovered": summary.total_pages,
                "loaded_ok": summary.classified_count,
                "parse_warning_count": summary.parse_warning_count,
                "misc_count": summary.misc_count,
                "low_conf_count": summary.low_conf_count,
                "conflict_count": summary.conflict_count,
                "by_entity_type": summary.by_entity_type,
                "duration_ms": summary.duration_ms,
                "generated_at": summary.generated_at,
            }
        )
        logger.info(
            "Classification pipeline completed: source_mode={}, duration_ms={}, classified_count={}, misc_count={}, low_conf_count={}, conflict_count={}, parse_warning_count={}",
            summary.source_mode,
            summary.duration_ms,
            summary.classified_count,
            summary.misc_count,
            summary.low_conf_count,
            summary.conflict_count,
            summary.parse_warning_count,
        )
        return summary
