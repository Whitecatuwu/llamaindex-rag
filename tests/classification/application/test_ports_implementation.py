import shutil
import unittest
import uuid
from pathlib import Path

from src.classification.application.ports import (
    ClassificationSinkPort,
    PageSourcePort,
    ReportSinkPort,
)
from src.classification.infrastructure.sinks.jsonl_sink import JsonlClassificationSink
from src.classification.infrastructure.sinks.report_sink import JsonReportSink
from src.classification.infrastructure.sources.HtmlPageSource import HtmlPageSource
from src.classification.infrastructure.sources.RegistryPageSource import RegistryPageSource


class PortsImplementationTests(unittest.TestCase):
    def test_sources_implement_page_source_port(self):
        html_source = HtmlPageSource(input_dir="data/raw/wiki/html")
        registry_source = RegistryPageSource(db_path="data/raw/wiki/wiki_registry.db")

        self.assertIsInstance(html_source, PageSourcePort)
        self.assertIsInstance(registry_source, PageSourcePort)

    def test_sinks_implement_sink_ports(self):
        base_tmp = Path("data/tmp-tests")
        base_tmp.mkdir(parents=True, exist_ok=True)
        tmp_path = base_tmp / f"ports_{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            labels_path = tmp_path / "labels.jsonl"
            review_path = tmp_path / "review.jsonl"
            report_path = tmp_path / "report.json"

            classification_sink = JsonlClassificationSink(
                labels_path=str(labels_path),
                review_path=str(review_path),
            )
            report_sink = JsonReportSink(report_path=str(report_path))
            try:
                self.assertIsInstance(classification_sink, ClassificationSinkPort)
                self.assertIsInstance(report_sink, ReportSinkPort)
            finally:
                classification_sink.close()
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)
