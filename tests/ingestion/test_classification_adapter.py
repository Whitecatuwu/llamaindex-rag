import json
import unittest

from src.ingestion.classification_adapter import run
from tests.utils.tempdir import managed_temp_dir


class ClassificationAdapterTests(unittest.TestCase):
    def test_adapter_runs_when_enabled(self):
        with managed_temp_dir("adapter") as tmp_path:
            input_dir = tmp_path / "html"
            input_dir.mkdir()
            (input_dir / "stage.json").write_text(
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

            result = run(
                enable_classification=True,
                source_mode="html",
                input_dir=str(input_dir),
                output_labels_path=str(tmp_path / "labels.jsonl"),
                output_report_path=str(tmp_path / "report.json"),
                output_review_path=str(tmp_path / "review.jsonl"),
            )

            self.assertIsNotNone(result)
            self.assertEqual(result.classified_count, 1)
