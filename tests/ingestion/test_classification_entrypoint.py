import json
import unittest

from src.classification.classify import run_classify
from tests.utils.tempdir import managed_temp_dir


class ClassificationAdapterTests(unittest.TestCase):
    def test_adapter_runs_when_enabled(self):
        with managed_temp_dir("adapter") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            source_path = input_dir / "stage.json"
            source_path.write_text(
                json.dumps(
                    {
                        "pageid": 1,
                        "title": "Stage A",
                        "revid": 1,
                        "categories": ["Category:Event Stages"],
                        "content": "stage content",
                        "is_redirect": False,
                    }
                ),
                encoding="utf-8",
            )

            result = run_classify(
                enable_classification=True,
                source_mode="html",
                input_dir=str(input_dir),
                output_labels_path=str(tmp_path / "labels.jsonl"),
                output_report_path=str(tmp_path / "report.json"),
                output_review_path=str(tmp_path / "review.jsonl"),
                classified_output_root=str(tmp_path / "classified"),
                incremental=False,
                show_progress=False,
            )

            self.assertIsNotNone(result)
            self.assertEqual(result.classified_count, 1)
            self.assertTrue((tmp_path / "labels.jsonl").exists())
            self.assertTrue((tmp_path / "review.jsonl").exists())
            self.assertTrue((tmp_path / "report.json").exists())
            classified_path = tmp_path / "classified" / "stage" / "stage.json"
            self.assertTrue(classified_path.exists())
            copied_payload = json.loads(classified_path.read_text(encoding="utf-8"))
            self.assertIn("subtypes", copied_payload)
            self.assertIn("is_ambiguous", copied_payload)
            original_payload = json.loads(source_path.read_text(encoding="utf-8"))
            self.assertNotIn("subtypes", original_payload)

    def test_adapter_incremental_skips_unchanged(self):
        with managed_temp_dir("adapter_incremental") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            source_path = input_dir / "stage_1.json"
            source_path.write_text(
                json.dumps(
                    {
                        "pageid": 1,
                        "title": "Stage A",
                        "revid": 1,
                        "categories": ["Category:Event Stages"],
                        "content": "stage content",
                        "is_redirect": False,
                    }
                ),
                encoding="utf-8",
            )

            first = run_classify(
                enable_classification=True,
                source_mode="html",
                input_dir=str(input_dir),
                output_labels_path=str(tmp_path / "labels_1.jsonl"),
                output_report_path=str(tmp_path / "report_1.json"),
                output_review_path=str(tmp_path / "review_1.jsonl"),
                classified_output_root=str(tmp_path / "classified"),
                state_db_path=str(tmp_path / "classification_state.db"),
                incremental=True,
                full_rebuild=False,
                show_progress=False,
            )
            second = run_classify(
                enable_classification=True,
                source_mode="html",
                input_dir=str(input_dir),
                output_labels_path=str(tmp_path / "labels_2.jsonl"),
                output_report_path=str(tmp_path / "report_2.json"),
                output_review_path=str(tmp_path / "review_2.jsonl"),
                classified_output_root=str(tmp_path / "classified"),
                state_db_path=str(tmp_path / "classification_state.db"),
                incremental=True,
                full_rebuild=False,
                show_progress=False,
            )

            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            self.assertEqual(first.classified_count, 1)
            self.assertEqual(second.classified_count, 0)

    def test_adapter_missing_pageid_is_invalid_and_in_review(self):
        with managed_temp_dir("adapter_missing_pageid") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            source_path = input_dir / "broken.json"
            source_path.write_text(
                json.dumps(
                    {
                        "title": "Broken Page",
                        "revid": 1,
                        "categories": ["Category:Mechanic"],
                        "content": "mechanic content",
                        "is_redirect": False,
                    }
                ),
                encoding="utf-8",
            )

            result = run_classify(
                enable_classification=True,
                source_mode="html",
                input_dir=str(input_dir),
                output_labels_path=str(tmp_path / "labels_invalid.jsonl"),
                output_report_path=str(tmp_path / "report_invalid.json"),
                output_review_path=str(tmp_path / "review_invalid.jsonl"),
                classified_output_root=str(tmp_path / "classified"),
                incremental=True,
                full_rebuild=False,
                state_db_path=str(tmp_path / "classification_state.db"),
                show_progress=False,
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.classified_count, 1)
            self.assertEqual(result.by_entity_type["invalid"], 1)

            labels = (tmp_path / "labels_invalid.jsonl").read_text(encoding="utf-8").strip().splitlines()
            reviews = (tmp_path / "review_invalid.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(labels), 1)
            self.assertEqual(len(reviews), 1)

            label_row = json.loads(labels[0])
            review_row = json.loads(reviews[0])
            self.assertEqual(label_row["entity_type"], "invalid")
            self.assertEqual(review_row["entity_type"], "invalid")
