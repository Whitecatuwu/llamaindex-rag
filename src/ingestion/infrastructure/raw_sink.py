import asyncio
import json
from pathlib import Path
from typing import Any


class RawApiJsonlSink:
    def __init__(self, output_dir: str | Path, run_id: str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.file_path = self.output_dir / f"api_calls_{run_id}.jsonl"
        self._lock = asyncio.Lock()
        self._handle = self.file_path.open("a", encoding="utf-8")
        self._closed = False

    async def write_event(self, event: dict[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("run_id", self.run_id)
        line = json.dumps(payload, ensure_ascii=False)
        async with self._lock:
            if self._closed:
                raise RuntimeError("RawApiJsonlSink is closed.")
            self._handle.write(line)
            self._handle.write("\n")
            self._handle.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._handle.close()
