from dataclasses import dataclass

from src.classification.application.workflows.classification_pipeline import (
    ClassificationPipeline,
    PipelineConfig,
    PipelineSummary,
)
from src.config.logger_config import logger


@dataclass(frozen=True)
class ClassifyWikiPagesCommand:
    source_mode: str
    low_confidence_threshold: float = 0.5
    include_redirects: bool = True
    incremental: bool = True
    full_rebuild: bool = False
    show_progress: bool = True
    # Kept for backward compatibility; infrastructure adapter is responsible for consuming this.
    state_db_path: str = "artifacts/classified/classification_state.db"


@dataclass(frozen=True)
class ClassifyWikiPagesResult:
    total_pages: int
    classified_count: int
    misc_count: int
    low_conf_count: int
    ambiguity_count: int
    parse_warning_count: int
    by_entity_type: dict[str, int]


class ClassifyWikiPagesUseCase:
    def __init__(self, pipeline: ClassificationPipeline) -> None:
        self.pipeline = pipeline

    def execute(self, command: ClassifyWikiPagesCommand) -> ClassifyWikiPagesResult:
        logger.info(
            "Classification use case started: source_mode={}, low_confidence_threshold={}, include_redirects={}, incremental={}, full_rebuild={}, state_db_path={}",
            command.source_mode,
            command.low_confidence_threshold,
            command.include_redirects,
            command.incremental,
            command.full_rebuild,
            command.state_db_path,
        )
        summary: PipelineSummary = self.pipeline.run(
            PipelineConfig(
                source_mode=command.source_mode,
                low_confidence_threshold=command.low_confidence_threshold,
                include_redirects=command.include_redirects,
                incremental=command.incremental,
                full_rebuild=command.full_rebuild,
                show_progress=command.show_progress,
            )
        )
        logger.info(
            "Classification use case completed: total_pages={}, classified_count={}, misc_count={}, low_conf_count={}, ambiguity_count={}, parse_warning_count={}",
            summary.total_pages,
            summary.classified_count,
            summary.misc_count,
            summary.low_conf_count,
            summary.ambiguity_count,
            summary.parse_warning_count,
        )
        return ClassifyWikiPagesResult(
            total_pages=summary.total_pages,
            classified_count=summary.classified_count,
            misc_count=summary.misc_count,
            low_conf_count=summary.low_conf_count,
            ambiguity_count=summary.ambiguity_count,
            parse_warning_count=summary.parse_warning_count,
            by_entity_type=summary.by_entity_type,
        )
