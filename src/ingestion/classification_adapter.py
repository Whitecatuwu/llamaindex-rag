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
from src.config.logger_config import logger


def run(
    enable_classification: bool = False,
    source_mode: str = "html",
    input_dir: str = "data/raw/wiki/html",
    db_path: str = "data/raw/wiki/wiki_registry.db",
    output_labels_path: str = "artifacts/docs/page_labels_ingestion.jsonl",
    output_report_path: str = "artifacts/docs/classification_report_ingestion.json",
    output_review_path: str = "artifacts/docs/review_queue_ingestion.jsonl",
    classified_output_root: str | None = None,
    low_confidence_threshold: float = 0.5,
    include_redirects: bool = True,
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

    jsonl_sink = JsonlClassificationSink(labels_path=output_labels_path, review_path=output_review_path)
    classified_root = classified_output_root or str(Path(input_dir) / "classified")
    classified_sink = ClassifiedJsonSink(classified_root=classified_root)
    sink = CompositeClassificationSink(primary=jsonl_sink, secondary=classified_sink)
    report_sink = JsonReportSink(report_path=output_report_path)
    classifier = RuleBasedClassifier()
    pipeline = ClassificationPipeline(source=source, classifier=classifier, sink=sink, report_sink=report_sink)
    use_case = ClassifyWikiPagesUseCase(pipeline=pipeline)
    return use_case.execute(
        ClassifyWikiPagesCommand(
            source_mode=source_mode,
            low_confidence_threshold=low_confidence_threshold,
            include_redirects=include_redirects,
        )
    )

if __name__ == "__main__":
    run(
        enable_classification=True,
        source_mode="html",
        input_dir="artifacts/raw/wiki/html",
        db_path="artifacts/raw/wiki/wiki_registry.db",
        output_labels_path="artifacts/classified/page_labels_ingestion.jsonl",
        output_report_path="artifacts/classified/classification_report_ingestion.json",
        output_review_path="artifacts/classified/review_queue_ingestion.jsonl",
        classified_output_root="artifacts/classified/wiki",
        low_confidence_threshold=0.5,
        include_redirects=True,
    )
