import json
from pathlib import Path

from src.classification.application.ports import ClassificationSinkPort


class JsonlClassificationSink(ClassificationSinkPort):
    def __init__(self, labels_path: str, review_path: str) -> None:
        labels_file = Path(labels_path)
        review_file = Path(review_path)
        labels_file.parent.mkdir(parents=True, exist_ok=True)
        review_file.parent.mkdir(parents=True, exist_ok=True)
        self._labels_fp = labels_file.open("w", encoding="utf-8")
        self._review_fp = review_file.open("w", encoding="utf-8")

    def write_label(self, row: dict) -> None:
        self._labels_fp.write(json.dumps(row, ensure_ascii=False) + "\n")

    def write_review(self, row: dict) -> None:
        self._review_fp.write(json.dumps(row, ensure_ascii=False) + "\n")

    def close(self) -> None:
        self._labels_fp.close()
        self._review_fp.close()
