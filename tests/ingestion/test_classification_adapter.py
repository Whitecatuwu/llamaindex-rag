import json
import shutil
import unittest
import uuid
from pathlib import Path

from src.ingestion.classification_adapter import run


class ClassificationAdapterTests(unittest.TestCase):
    def test_adapter_runs_when_enabled(self):
        base_tmp = Path("data/tmp-tests")
        base_tmp.mkdir(parents=True, exist_ok=True)
        tmp_path = base_tmp / f"adapter_{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
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
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)
