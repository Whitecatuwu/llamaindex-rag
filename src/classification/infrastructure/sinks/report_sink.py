import json
from pathlib import Path

from src.classification.application.ports import ReportSinkPort


class JsonReportSink(ReportSinkPort):
    def __init__(self, report_path: str) -> None:
        self.report_path = Path(report_path)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)

    def write_report(self, report: dict) -> None:
        self.report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
