from pathlib import Path

from src.classification.application.use_cases.classify_wiki_pages import (
    ClassifyWikiPagesCommand,
    ClassifyWikiPagesResult,
    ClassifyWikiPagesUseCase,
)
from src.classification.application.workflows.classification_pipeline import ClassificationPipeline
from src.classification.domain.classifier import RuleBasedClassifier
from src.classification.infrastructure.sinks.classified_json_sink import ClassifiedJsonSink
from src.classification.infrastructure.sinks.composite_sink import CompositeClassificationSink
from src.classification.infrastructure.sinks.jsonl_sink import JsonlClassificationSink
from src.classification.infrastructure.sinks.report_sink import JsonReportSink
from src.classification.infrastructure.sources.HtmlPageSource import HtmlPageSource
from src.classification.infrastructure.sources.RegistryPageSource import RegistryPageSource
from src.classification.infrastructure.state.classification_state_store import ClassificationStateStore
from src.config.logger_config import logger


def run_classify(
    enable_classification: bool = False,
    source_mode: str = "html",
    input_dir: str = "artifacts/raw/wiki/page",
    db_path: str = "artifacts/raw/wiki/wiki_registry.db",
    output_labels_path: str = "artifacts/docs/page_labels_ingestion.jsonl",
    output_report_path: str = "artifacts/docs/classification_report_ingestion.json",
    output_review_path: str = "artifacts/docs/review_queue_ingestion.jsonl",
    classified_output_root: str | None = None,
    incremental: bool = True,
    full_rebuild: bool = False,
    state_db_path: str = "artifacts/classified/classification_state.db",
    low_confidence_threshold: float = 0.5,
    include_redirects: bool = True,
    show_progress: bool = True,
) -> ClassifyWikiPagesResult | None:
    if not enable_classification:
        logger.info("Classification adapter is disabled. Set enable_classification=True to run.")
        return None

    if source_mode == "html":
        source = HtmlPageSource(input_dir=input_dir)
    elif source_mode == "db":
        source = RegistryPageSource(db_path=db_path)
    else:
        raise ValueError(f"Unsupported source mode: {source_mode}")

    state_store = None
    state_store_recovered = False
    state_store_recovered_from = None
    state_store_init_error = None
    if incremental or full_rebuild:
        try:
            state_store, state_store_recovered, state_store_recovered_from = ClassificationStateStore.create_with_recovery(
                state_db_path
            )
        except Exception as exc:
            state_store = None
            state_store_init_error = f"{type(exc).__name__}:{exc}"

    jsonl_sink = JsonlClassificationSink(labels_path=output_labels_path, review_path=output_review_path)
    classified_root = classified_output_root or str(Path(input_dir) / "classified")
    classified_sink = ClassifiedJsonSink(classified_root=classified_root)
    sink = CompositeClassificationSink(primary=jsonl_sink, secondary=classified_sink)
    report_sink = JsonReportSink(report_path=output_report_path)
    classifier = RuleBasedClassifier()
    pipeline = ClassificationPipeline(
        source=source,
        classifier=classifier,
        sink=sink,
        report_sink=report_sink,
        state_store=state_store,
        state_store_label=state_db_path,
        state_store_recovered=state_store_recovered,
        state_store_recovered_from=state_store_recovered_from,
        state_store_init_error=state_store_init_error,
    )
    use_case = ClassifyWikiPagesUseCase(pipeline=pipeline)
    return use_case.execute(
        ClassifyWikiPagesCommand(
            source_mode=source_mode,
            low_confidence_threshold=low_confidence_threshold,
            include_redirects=include_redirects,
            incremental=incremental,
            full_rebuild=full_rebuild,
            state_db_path=state_db_path,
            show_progress=show_progress,
        )
    )
