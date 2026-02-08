import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.classification.application.use_cases.classify_wiki_pages import (
    ClassifyWikiPagesCommand,
    ClassifyWikiPagesUseCase,
)
from src.classification.application.workflows.classification_pipeline import ClassificationPipeline, PipelineConfig
from src.classification.domain.entities import PageRef
from src.classification.domain.classifier import RuleBasedClassifier
from src.classification.infrastructure.state.classification_state_store import ClassificationStateStore
from src.classification.infrastructure.sinks.jsonl_sink import JsonlClassificationSink
from src.classification.infrastructure.sinks.report_sink import JsonReportSink
from src.classification.infrastructure.sources.HtmlPageSource import HtmlPageSource
from tests.utils.tempdir import managed_temp_dir


def _write_page(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class ClassificationPipelineTests(unittest.TestCase):
    @staticmethod
    def _run_html_pipeline(tmp_path: Path, input_dir: Path, labels_name: str, *, incremental: bool, full_rebuild: bool, state_db: Path):
        state_store = None
        state_store_recovered = False
        state_store_recovered_from = None
        state_store_init_error = None
        if incremental or full_rebuild:
            try:
                state_store, state_store_recovered, state_store_recovered_from = ClassificationStateStore.create_with_recovery(
                    str(state_db)
                )
            except Exception as exc:
                state_store = None
                state_store_init_error = f"{type(exc).__name__}:{exc}"
        use_case = ClassifyWikiPagesUseCase(
            pipeline=ClassificationPipeline(
                source=HtmlPageSource(str(input_dir)),
                classifier=RuleBasedClassifier(),
                sink=JsonlClassificationSink(str(tmp_path / labels_name), str(tmp_path / f"review_{labels_name}")),
                report_sink=JsonReportSink(str(tmp_path / f"report_{labels_name}.json")),
                state_store=state_store,
                state_store_label=str(state_db),
                state_store_recovered=state_store_recovered,
                state_store_recovered_from=state_store_recovered_from,
                state_store_init_error=state_store_init_error,
            )
        )
        return use_case.execute(
            ClassifyWikiPagesCommand(
                source_mode="html",
                include_redirects=True,
                incremental=incremental,
                full_rebuild=full_rebuild,
                state_db_path=str(state_db),
            )
        )

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
                    incremental=False,
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

    def test_pipeline_incremental_by_revid_skips_unchanged_pages(self):
        with managed_temp_dir("pipeline_incremental_revid") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            state_db = tmp_path / "classification_state.db"

            _write_page(
                input_dir / "stage.json",
                {
                    "pageid": 10,
                    "title": "Stage X",
                    "revid": 10,
                    "categories": ["Category:Event Stages"],
                    "content": "same content",
                    "is_redirect": False,
                },
            )

            first = self._run_html_pipeline(tmp_path, input_dir, "labels_1.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            second = self._run_html_pipeline(tmp_path, input_dir, "labels_2.jsonl", incremental=True, full_rebuild=False, state_db=state_db)

            self.assertEqual(first.classified_count, 1)
            self.assertEqual(second.classified_count, 0)

            _write_page(
                input_dir / "stage.json",
                {
                    "pageid": 10,
                    "title": "Stage X",
                    "revid": 11,
                    "categories": ["Category:Event Stages"],
                    "content": "same content",
                    "is_redirect": False,
                },
            )
            third = self._run_html_pipeline(tmp_path, input_dir, "labels_3.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            self.assertEqual(third.classified_count, 1)

    def test_pipeline_incremental_by_hash_when_revid_missing(self):
        with managed_temp_dir("pipeline_incremental_hash") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            state_db = tmp_path / "classification_state.db"

            _write_page(
                input_dir / "mechanic.json",
                {
                    "pageid": 20,
                    "title": "Mechanic X",
                    "revid": None,
                    "categories": ["Category:Mechanic"],
                    "content": "a\nb\n",
                    "is_redirect": False,
                },
            )

            first = self._run_html_pipeline(tmp_path, input_dir, "labels_a.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            second = self._run_html_pipeline(tmp_path, input_dir, "labels_b.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            self.assertEqual(first.classified_count, 1)
            self.assertEqual(second.classified_count, 0)

            _write_page(
                input_dir / "mechanic.json",
                {
                    "pageid": 20,
                    "title": "Mechanic X",
                    "revid": None,
                    "categories": ["Category:Mechanic"],
                    "content": "a\nc\n",
                    "is_redirect": False,
                },
            )
            third = self._run_html_pipeline(tmp_path, input_dir, "labels_c.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            self.assertEqual(third.classified_count, 1)

    def test_pipeline_incremental_reclassifies_when_revid_same_but_content_changes(self):
        with managed_temp_dir("pipeline_incremental_revid_hash") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            state_db = tmp_path / "classification_state.db"

            _write_page(
                input_dir / "cat.json",
                {
                    "pageid": 30,
                    "title": "Cat Y",
                    "revid": 100,
                    "categories": ["Category:Cat Units"],
                    "content": "first body",
                    "is_redirect": False,
                },
            )

            first = self._run_html_pipeline(tmp_path, input_dir, "labels_hash_1.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            second = self._run_html_pipeline(tmp_path, input_dir, "labels_hash_2.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            self.assertEqual(first.classified_count, 1)
            self.assertEqual(second.classified_count, 0)

            _write_page(
                input_dir / "cat.json",
                {
                    "pageid": 30,
                    "title": "Cat Y",
                    "revid": 100,
                    "categories": ["Category:Cat Units"],
                    "content": "second body",
                    "is_redirect": False,
                },
            )
            third = self._run_html_pipeline(tmp_path, input_dir, "labels_hash_3.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            self.assertEqual(third.classified_count, 1)

    def test_pipeline_full_rebuild_refreshes_state_for_next_incremental(self):
        with managed_temp_dir("pipeline_full_rebuild_state") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            state_db = tmp_path / "classification_state.db"

            _write_page(
                input_dir / "stage.json",
                {
                    "pageid": 40,
                    "title": "Stage Z",
                    "revid": 1,
                    "categories": ["Category:Event Stages"],
                    "content": "v1",
                    "is_redirect": False,
                },
            )
            first = self._run_html_pipeline(tmp_path, input_dir, "labels_rebuild_1.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            self.assertEqual(first.classified_count, 1)

            _write_page(
                input_dir / "stage.json",
                {
                    "pageid": 40,
                    "title": "Stage Z",
                    "revid": 2,
                    "categories": ["Category:Event Stages"],
                    "content": "v2",
                    "is_redirect": False,
                },
            )
            rebuild = self._run_html_pipeline(tmp_path, input_dir, "labels_rebuild_2.jsonl", incremental=True, full_rebuild=True, state_db=state_db)
            self.assertEqual(rebuild.classified_count, 1)

            after = self._run_html_pipeline(tmp_path, input_dir, "labels_rebuild_3.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            self.assertEqual(after.classified_count, 0)

    def test_pipeline_strategy_version_change_triggers_reclassification(self):
        with managed_temp_dir("pipeline_strategy_version") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            state_db = tmp_path / "classification_state.db"

            _write_page(
                input_dir / "enemy.json",
                {
                    "pageid": 50,
                    "title": "Enemy S",
                    "revid": 5,
                    "categories": ["Category:Enemies"],
                    "content": "enemy body",
                    "is_redirect": False,
                },
            )

            first = self._run_html_pipeline(tmp_path, input_dir, "labels_strategy_1.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            self.assertEqual(first.classified_count, 1)

            with patch(
                "src.classification.application.workflows.classification_pipeline.CLASSIFICATION_STRATEGY_VERSION",
                "9.9.9",
            ):
                second = self._run_html_pipeline(tmp_path, input_dir, "labels_strategy_2.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            self.assertEqual(second.classified_count, 1)

    def test_pipeline_recovers_when_state_db_is_corrupted(self):
        with managed_temp_dir("pipeline_state_corrupt") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            state_db = tmp_path / "classification_state.db"
            state_db.write_text("not a sqlite file", encoding="utf-8")

            _write_page(
                input_dir / "mechanic.json",
                {
                    "pageid": 60,
                    "title": "Mechanic C",
                    "revid": 60,
                    "categories": ["Category:Mechanic"],
                    "content": "m body",
                    "is_redirect": False,
                },
            )

            first = self._run_html_pipeline(tmp_path, input_dir, "labels_corrupt_1.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            second = self._run_html_pipeline(tmp_path, input_dir, "labels_corrupt_2.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            self.assertEqual(first.classified_count, 1)
            self.assertEqual(second.classified_count, 0)

            backups = list(tmp_path.glob("classification_state.db.corrupt.*"))
            self.assertEqual(len(backups), 1)

    def test_pipeline_fallbacks_to_stateless_when_state_init_fails(self):
        with managed_temp_dir("pipeline_state_init_fail") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            state_db = tmp_path / "classification_state.db"

            _write_page(
                input_dir / "list.json",
                {
                    "pageid": 70,
                    "title": "List P",
                    "revid": 70,
                    "categories": ["Category:Lists"],
                    "content": "list body",
                    "is_redirect": False,
                },
            )

            with patch.object(ClassificationStateStore, "create_with_recovery", side_effect=OSError("disk denied")):
                result = self._run_html_pipeline(tmp_path, input_dir, "labels_state_fail.jsonl", incremental=True, full_rebuild=False, state_db=state_db)
            self.assertEqual(result.classified_count, 1)

    def test_pipeline_missing_pageid_is_marked_invalid_and_enqueued_review(self):
        with managed_temp_dir("pipeline_missing_pageid_invalid") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            state_db = tmp_path / "classification_state.db"
            _write_page(
                input_dir / "broken.json",
                {
                    "pageid": None,
                    "title": "Broken A",
                    "revid": 1,
                    "categories": ["Category:Cat Units"],
                    "content": "cat body",
                    "is_redirect": False,
                },
            )

            result = self._run_html_pipeline(
                tmp_path,
                input_dir,
                "labels_missing_pageid.jsonl",
                incremental=True,
                full_rebuild=False,
                state_db=state_db,
            )
            self.assertEqual(result.classified_count, 1)
            self.assertEqual(result.by_entity_type["invalid"], 1)

            labels_path = tmp_path / "labels_missing_pageid.jsonl"
            review_path = tmp_path / "review_labels_missing_pageid.jsonl"
            labels = [json.loads(line) for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            reviews = [json.loads(line) for line in review_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(labels), 1)
            self.assertEqual(len(reviews), 1)
            self.assertEqual(labels[0]["entity_type"], "invalid")
            self.assertIn("missing_pageid", labels[0]["reasons"])

    def test_pipeline_missing_pageid_is_not_incrementally_skipped(self):
        with managed_temp_dir("pipeline_missing_pageid_not_skipped") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            state_db = tmp_path / "classification_state.db"
            _write_page(
                input_dir / "broken.json",
                {
                    "pageid": None,
                    "title": "Broken B",
                    "revid": 1,
                    "categories": ["Category:Enemies"],
                    "content": "enemy body",
                    "is_redirect": False,
                },
            )

            first = self._run_html_pipeline(
                tmp_path, input_dir, "labels_missing_pageid_1.jsonl", incremental=True, full_rebuild=False, state_db=state_db
            )
            second = self._run_html_pipeline(
                tmp_path, input_dir, "labels_missing_pageid_2.jsonl", incremental=True, full_rebuild=False, state_db=state_db
            )
            self.assertEqual(first.classified_count, 1)
            self.assertEqual(second.classified_count, 1)
