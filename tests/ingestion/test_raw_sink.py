import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from src.ingestion.infrastructure.raw_sink import RawApiJsonlSink


class RawApiJsonlSinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_write_event_appends_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = RawApiJsonlSink(Path(tmp), run_id="run_1")
            try:
                await sink.write_event({"operation": "fetch_page_doc", "attempt": 1})
            finally:
                sink.close()

            file_path = Path(tmp) / "api_calls_run_1.jsonl"
            self.assertTrue(file_path.exists())
            lines = file_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["run_id"], "run_1")
            self.assertEqual(payload["operation"], "fetch_page_doc")
            self.assertEqual(payload["attempt"], 1)

    async def test_write_event_is_concurrency_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = RawApiJsonlSink(Path(tmp), run_id="run_2")
            try:
                await asyncio.gather(
                    *(sink.write_event({"operation": "fetch_categories", "attempt": i}) for i in range(20))
                )
            finally:
                sink.close()

            file_path = Path(tmp) / "api_calls_run_2.jsonl"
            payloads = [json.loads(line) for line in file_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(payloads), 20)
            self.assertEqual({int(p["attempt"]) for p in payloads}, set(range(20)))
