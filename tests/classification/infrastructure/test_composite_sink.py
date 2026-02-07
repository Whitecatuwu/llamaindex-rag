import json
import unittest

from src.classification.infrastructure.sinks.classified_json_sink import ClassifiedJsonSink
from src.classification.infrastructure.sinks.composite_sink import CompositeClassificationSink
from src.classification.infrastructure.sinks.jsonl_sink import JsonlClassificationSink
from tests.utils.tempdir import managed_temp_dir


class CompositeSinkTests(unittest.TestCase):
    def test_composite_sink_writes_jsonl_and_classified_outputs(self):
        with managed_temp_dir("composite_sink") as tmp_path:
            source_path = tmp_path / "Enemy A.json"
            source_path.write_text(json.dumps({"title": "Enemy A"}, ensure_ascii=False), encoding="utf-8")

            labels_path = tmp_path / "labels.jsonl"
            review_path = tmp_path / "review.jsonl"
            classified_root = tmp_path / "classified"

            composite = CompositeClassificationSink(
                primary=JsonlClassificationSink(labels_path=str(labels_path), review_path=str(review_path)),
                secondary=ClassifiedJsonSink(classified_root=str(classified_root)),
            )
            row = {
                "doc_id": "2",
                "pageid": 2,
                "title": "Enemy A",
                "entity_type": "enemy",
                "source_path": str(source_path),
                "subtypes": ["trait:red"],
                "confidence": 1.0,
                "reasons": [],
                "matched_rules": [],
                "strategy_version": "1.0.0",
                "is_redirect": False,
                "parse_warning": None,
            }
            composite.write_label(row)
            composite.write_review(row)
            composite.close()

            self.assertTrue(labels_path.exists())
            self.assertTrue(review_path.exists())
            self.assertTrue((classified_root / "enemy" / "Enemy A.json").exists())

