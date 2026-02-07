import json
import unittest
from pathlib import Path

from src.classification.application.use_cases.classify_wiki_pages import (
    ClassifyWikiPagesCommand,
    ClassifyWikiPagesUseCase,
)
from src.classification.application.workflows.classification_pipeline import ClassificationPipeline, PipelineConfig
from src.classification.domain.entities import PageRef
from src.classification.domain.classifier import RuleBasedClassifier
from src.classification.infrastructure.sinks.jsonl_sink import JsonlClassificationSink
from src.classification.infrastructure.sinks.report_sink import JsonReportSink
from src.classification.infrastructure.sources.HtmlPageSource import HtmlPageSource
from tests.utils.tempdir import managed_temp_dir


def _write_page(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class ClassificationPipelineTests(unittest.TestCase):
    def test_pipeline_runs_all_steps(self):
        with managed_temp_dir("pipeline") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            _write_page(
                input_dir / "cat.json",
                {
                    "pageid": 1,
                    "title": "Cat A",
                    "revid": 1,
                    "categories": ["Category:Cat Units", "Category:Uber Rare Cats"],
                    "content": "cat content",
                    "is_redirect": False,
                },
            )
            _write_page(
                input_dir / "stage.json",
                {
                    "pageid": 2,
                    "title": "Stage A",
                    "revid": 2,
                    "categories": ["Category:Event Stages"],
                    "content": "stage content",
                    "is_redirect": False,
                },
            )

            labels_path = tmp_path / "labels.jsonl"
            review_path = tmp_path / "review.jsonl"
            report_path = tmp_path / "report.json"

            use_case = ClassifyWikiPagesUseCase(
                pipeline=ClassificationPipeline(
                    source=HtmlPageSource(str(input_dir)),
                    classifier=RuleBasedClassifier(),
                    sink=JsonlClassificationSink(str(labels_path), str(review_path)),
                    report_sink=JsonReportSink(str(report_path)),
                )
            )
            result = use_case.execute(
                ClassifyWikiPagesCommand(
                    source_mode="html",
                    low_confidence_threshold=0.6,
                    include_redirects=True,
                )
            )

            self.assertEqual(result.total_pages, 2)
            self.assertEqual(result.classified_count, 2)
            self.assertTrue(labels_path.exists())
            self.assertTrue(report_path.exists())
            lines = labels_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)

    def test_pipeline_closes_sink_when_load_raises(self):
        class FailingSource:
            def discover(self):
                return [PageRef(source_id="1", location="memory://broken")]

            def load(self, ref):
                raise RuntimeError("boom")

        class TrackingSink:
            def __init__(self):
                self.closed = False

            def write_label(self, row):
                return None

            def write_review(self, row):
                return None

            def close(self):
                self.closed = True

        class DummyReportSink:
            def write_report(self, report: dict):
                return None

        sink = TrackingSink()
        pipeline = ClassificationPipeline(
            source=FailingSource(),
            classifier=RuleBasedClassifier(),
            sink=sink,
            report_sink=DummyReportSink(),
        )
        with self.assertRaises(RuntimeError):
            pipeline.run(
                PipelineConfig(
                    source_mode="html",
                    low_confidence_threshold=0.5,
                    include_redirects=True,
                )
            )
        self.assertTrue(sink.closed)
