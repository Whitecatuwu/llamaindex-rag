import json
from pathlib import Path

from src.classification.application.contracts import ClassificationReportRecord
from src.classification.application.ports import ReportSinkPort
from src.config.logger_config import logger


class JsonReportSink(ReportSinkPort):
    def __init__(self, report_path: str) -> None:
        self.report_path = Path(report_path)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)

    def write_report(self, report: ClassificationReportRecord) -> None:
        self.report_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Classification report written: report_path={}", str(self.report_path))
