from dataclasses import dataclass

from src.classification.application.workflows.classification_pipeline import (
    ClassificationPipeline,
    PipelineConfig,
    PipelineSummary,
)


@dataclass(frozen=True)
class ClassifyWikiPagesCommand:
    source_mode: str
    low_confidence_threshold: float = 0.5
    include_redirects: bool = True


@dataclass(frozen=True)
class ClassifyWikiPagesResult:
    total_pages: int
    classified_count: int
    misc_count: int
    low_conf_count: int
    conflict_count: int
    parse_warning_count: int
    by_entity_type: dict[str, int]


class ClassifyWikiPagesUseCase:
    def __init__(self, pipeline: ClassificationPipeline) -> None:
        self.pipeline = pipeline

    def execute(self, command: ClassifyWikiPagesCommand) -> ClassifyWikiPagesResult:
        summary: PipelineSummary = self.pipeline.run(
            PipelineConfig(
                source_mode=command.source_mode,
                low_confidence_threshold=command.low_confidence_threshold,
                include_redirects=command.include_redirects,
            )
        )
        return ClassifyWikiPagesResult(
            total_pages=summary.total_pages,
            classified_count=summary.classified_count,
            misc_count=summary.misc_count,
            low_conf_count=summary.low_conf_count,
            conflict_count=summary.conflict_count,
            parse_warning_count=summary.parse_warning_count,
            by_entity_type=summary.by_entity_type,
        )

