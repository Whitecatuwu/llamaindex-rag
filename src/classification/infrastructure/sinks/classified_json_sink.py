import json
import re
from pathlib import Path

from src.classification.application.contracts import ClassificationLabelRecord
from src.classification.application.ports import ClassificationSinkPort
from src.config.logger_config import logger


class ClassifiedJsonSink(ClassificationSinkPort):
    # Classification output always reuses source filename as the primary naming rule.
    # We do not recalculate filenames from title/doc fields in this layer.
    def __init__(self, classified_root: str) -> None:
        self.classified_root = Path(classified_root)
        self.classified_root.mkdir(parents=True, exist_ok=True)
        self.copied_count = 0
        self.skipped_invalid_source_count = 0
        self.collision_renamed_count = 0
        self.by_entity_type: dict[str, int] = {}
        logger.info("Classified JSON sink initialized: classified_root={}", str(self.classified_root))

    def write_label(self, row: ClassificationLabelRecord) -> None:
        source_path = Path(row.source_path)
        if not source_path.exists() or source_path.suffix.lower() != ".json":
            self.skipped_invalid_source_count += 1
            logger.warning(
                "Skip classified copy due to invalid source path: doc_id={}, source_path={}",
                row.doc_id,
                row.source_path,
            )
            return

        with source_path.open("r", encoding="utf-8", errors="replace") as fp:
            payload = json.load(fp)
        payload["subtypes"] = list(row.subtypes)
        payload["is_ambiguous"] = row.is_ambiguous

        entity_type = str(row.entity_type or "misc")
        entity_dir = self.classified_root / entity_type
        entity_dir.mkdir(parents=True, exist_ok=True)
        self._warn_legacy_double_underscore_names(entity_dir=entity_dir, source_name=source_path.name, entity_type=entity_type)

        target_path = self._resolve_output_path(
            entity_dir=entity_dir,
            source_name=source_path.name,
            pageid=row.pageid,
            doc_id=row.doc_id,
        )
        if target_path.name != source_path.name:
            self.collision_renamed_count += 1

        with target_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
            fp.write("\n")

        self.copied_count += 1
        self.by_entity_type[entity_type] = self.by_entity_type.get(entity_type, 0) + 1

    def write_review(self, row: ClassificationLabelRecord) -> None:
        logger.debug("Classified JSON sink received review row (no-op): doc_id={}", row.doc_id)

    def close(self) -> None:
        logger.info(
            "Classified JSON sink closed: classified_root={}, copied_count={}, skipped_invalid_source_count={}, collision_renamed_count={}, by_entity_type={}",
            str(self.classified_root),
            self.copied_count,
            self.skipped_invalid_source_count,
            self.collision_renamed_count,
            self.by_entity_type,
        )

    @staticmethod
    def _resolve_output_path(
        entity_dir: Path,
        source_name: str,
        pageid: object,
        doc_id: object,
    ) -> Path:
        candidate = entity_dir / source_name
        if not candidate.exists():
            return candidate
        if ClassifiedJsonSink._is_same_document(candidate, pageid=pageid, doc_id=doc_id):
            return candidate

        # "_<id>" is collision fallback only. It is not the primary naming strategy.
        source_stem = Path(source_name).stem
        source_suffix = Path(source_name).suffix or ".json"
        unique = str(pageid) if pageid is not None else str(doc_id)
        return entity_dir / f"{source_stem}_{unique}{source_suffix}"

    @staticmethod
    def _is_same_document(path: Path, pageid: object, doc_id: object) -> bool:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fp:
                existing = json.load(fp)
        except Exception:
            return False

        existing_pageid = existing.get("pageid")
        if pageid is not None and existing_pageid is not None and str(existing_pageid) == str(pageid):
            return True
        if doc_id is not None and str(existing.get("doc_id", "")) == str(doc_id):
            return True
        return False

    @staticmethod
    def _warn_legacy_double_underscore_names(entity_dir: Path, source_name: str, entity_type: str) -> None:
        source_stem = Path(source_name).stem
        pattern = re.compile(rf"^{re.escape(source_stem)}__\d+\.json$")
        for existing in entity_dir.glob("*.json"):
            if not pattern.match(existing.name):
                continue
            recommended_pattern = f"{source_stem}_<id>.json"
            logger.warning(
                "Detected legacy classified filename pattern: entity_type={}, legacy_filename={}, recommended_pattern={}",
                entity_type,
                existing.name,
                recommended_pattern,
            )
