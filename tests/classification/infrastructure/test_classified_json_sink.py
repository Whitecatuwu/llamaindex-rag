import json
import unittest
from unittest.mock import patch

from src.classification.application.contracts import ClassificationLabelRecord
from src.classification.infrastructure.sinks.classified_json_sink import ClassifiedJsonSink
from tests.utils.tempdir import managed_temp_dir


class ClassifiedJsonSinkTests(unittest.TestCase):
    def test_write_label_outputs_classified_copy_with_subtypes(self):
        with managed_temp_dir("classified_sink") as tmp_path:
            source_path = tmp_path / "Asuka Cat (Rare Cat).json"
            source_payload = {"pageid": 123, "title": "Asuka Cat"}
            source_path.write_text(json.dumps(source_payload, ensure_ascii=False), encoding="utf-8")

            sink = ClassifiedJsonSink(classified_root=str(tmp_path / "classified"))
            sink.write_label(
                ClassificationLabelRecord(
                    doc_id="123",
                    pageid=123,
                    title="Asuka Cat",
                    revision_id=None,
                    canonical_url=None,
                    entity_type="cat",
                    source_path=str(source_path),
                    subtypes=("rarity:rare", "source:event_capsule"),
                    confidence=1.0,
                    reasons=(),
                    matched_rules=(),
                    strategy_version="1.0.0",
                    is_redirect=False,
                    parse_warning=None,
                )
            )
            sink.close()

            target_path = tmp_path / "classified" / "cat" / "Asuka Cat (Rare Cat).json"
            self.assertTrue(target_path.exists())
            self.assertIn("\n", target_path.read_text(encoding="utf-8"))

            copied_payload = json.loads(target_path.read_text(encoding="utf-8"))
            self.assertEqual(copied_payload["subtypes"], ["rarity:rare", "source:event_capsule"])
            self.assertFalse(copied_payload["is_ambiguous"])

            original_payload = json.loads(source_path.read_text(encoding="utf-8"))
            self.assertNotIn("subtypes", original_payload)
            self.assertNotIn("is_ambiguous", original_payload)

    def test_write_label_renames_on_name_collision(self):
        with managed_temp_dir("classified_collision") as tmp_path:
            source_a = tmp_path / "same.json"
            source_a.write_text(json.dumps({"title": "A"}, ensure_ascii=False), encoding="utf-8")

            source_b_dir = tmp_path / "nested"
            source_b_dir.mkdir(parents=True, exist_ok=True)
            source_b = source_b_dir / "same.json"
            source_b.write_text(json.dumps({"title": "B"}, ensure_ascii=False), encoding="utf-8")

            sink = ClassifiedJsonSink(classified_root=str(tmp_path / "classified"))
            sink.write_label(
                ClassificationLabelRecord(
                    doc_id="1",
                    pageid=1,
                    title="A",
                    revision_id=None,
                    canonical_url=None,
                    entity_type="cat",
                    source_path=str(source_a),
                    subtypes=("rarity:normal",),
                    confidence=1.0,
                    reasons=(),
                    matched_rules=(),
                    strategy_version="1.0.0",
                    is_redirect=False,
                    parse_warning=None,
                )
            )
            sink.write_label(
                ClassificationLabelRecord(
                    doc_id="2",
                    pageid=2,
                    title="B",
                    revision_id=None,
                    canonical_url=None,
                    entity_type="cat",
                    source_path=str(source_b),
                    subtypes=("rarity:rare",),
                    confidence=1.0,
                    reasons=(),
                    matched_rules=(),
                    strategy_version="1.0.0",
                    is_redirect=False,
                    parse_warning=None,
                )
            )
            sink.close()

            normal_path = tmp_path / "classified" / "cat" / "same.json"
            renamed_path = tmp_path / "classified" / "cat" / "same_2.json"
            self.assertTrue(normal_path.exists())
            self.assertTrue(renamed_path.exists())

    def test_write_label_overwrites_same_document_without_suffix(self):
        with managed_temp_dir("classified_same_doc") as tmp_path:
            source_path = tmp_path / "same.json"
            source_path.write_text(json.dumps({"pageid": 9, "title": "Same"}, ensure_ascii=False), encoding="utf-8")

            sink = ClassifiedJsonSink(classified_root=str(tmp_path / "classified"))
            row = ClassificationLabelRecord(
                doc_id="9",
                pageid=9,
                title="Same",
                revision_id=None,
                canonical_url=None,
                entity_type="cat",
                source_path=str(source_path),
                subtypes=("rarity:normal",),
                confidence=1.0,
                reasons=(),
                matched_rules=(),
                strategy_version="1.0.0",
                is_redirect=False,
                parse_warning=None,
            )
            sink.write_label(row)
            sink.write_label(row)
            sink.close()

            normal_path = tmp_path / "classified" / "cat" / "same.json"
            renamed_path = tmp_path / "classified" / "cat" / "same_9.json"
            self.assertTrue(normal_path.exists())
            self.assertFalse(renamed_path.exists())

    def test_warns_when_legacy_double_underscore_filename_exists(self):
        with managed_temp_dir("classified_legacy_warn") as tmp_path:
            source_path = tmp_path / "stage_1.json"
            source_path.write_text(json.dumps({"pageid": 1, "title": "Stage A"}, ensure_ascii=False), encoding="utf-8")

            classified_dir = tmp_path / "classified" / "stage"
            classified_dir.mkdir(parents=True, exist_ok=True)
            legacy_path = classified_dir / "stage_1__999.json"
            legacy_path.write_text(json.dumps({"pageid": 999, "title": "Legacy"}, ensure_ascii=False), encoding="utf-8")

            sink = ClassifiedJsonSink(classified_root=str(tmp_path / "classified"))
            with patch("src.classification.infrastructure.sinks.classified_json_sink.logger.warning") as warning_mock:
                sink.write_label(
                    ClassificationLabelRecord(
                        doc_id="1",
                        pageid=1,
                        title="Stage A",
                        revision_id=None,
                        canonical_url=None,
                        entity_type="stage",
                        source_path=str(source_path),
                        subtypes=("stage_family:event",),
                        confidence=1.0,
                        reasons=(),
                        matched_rules=(),
                        strategy_version="1.0.0",
                        is_redirect=False,
                        parse_warning=None,
                    )
                )
            sink.close()

            self.assertTrue((classified_dir / "stage_1.json").exists())
            warning_mock.assert_called()
