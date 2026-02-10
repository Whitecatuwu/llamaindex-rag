from __future__ import annotations
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

from src.ingestion.application.workflows.crawl_pages import CrawlPagesWorkflow, CrawlWorkflowConfig
from src.ingestion.domain.models import CrawlSummary
from src.ingestion.infrastructure.fs_sink import JsonFileSink
from src.ingestion.infrastructure.mw_client import MediaWikiClient
from src.ingestion.infrastructure.raw_sink import RawApiJsonlSink
from src.ingestion.infrastructure.registry_sqlite import SQLiteRegistryRepository


DEFAULT_BASE_URL = "https://battlecats.miraheze.org/w/api.php"
DEFAULT_DATA_DIR = Path("artifacts/raw/wiki")
DEFAULT_PAGE_DIR = DEFAULT_DATA_DIR / "page"
DEFAULT_RAW_DIR = DEFAULT_DATA_DIR / "raw"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "wiki_registry.db"


async def run_crawl_async(
    *,
    base_url: str = DEFAULT_BASE_URL,
    page_dir: str | Path = DEFAULT_PAGE_DIR,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    db_path: str | Path = DEFAULT_DB_PATH,
    workflow_config: CrawlWorkflowConfig | None = None,
    show_progress: bool = True,
) -> CrawlSummary:
    page_path = Path(page_dir)
    page_path.mkdir(parents=True, exist_ok=True)
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    db_file_path = Path(db_path)
    db_file_path.parent.mkdir(parents=True, exist_ok=True)
    run_id = _build_run_id()

    raw_sink = RawApiJsonlSink(raw_path, run_id=run_id)
    mw_client = MediaWikiClient(base_url=base_url, raw_sink=raw_sink, run_id=run_id)
    registry = SQLiteRegistryRepository(db_file_path)
    sink = JsonFileSink(page_path)
    workflow = CrawlPagesWorkflow(
        mw_client=mw_client,
        registry=registry,
        sink=sink,
        config=(
            replace(workflow_config, show_progress=show_progress)
            if workflow_config is not None
            else CrawlWorkflowConfig(show_progress=show_progress)
        ),
    )
    try:
        return await workflow.run()
    finally:
        raw_sink.close()
        registry.close()


def run_crawl(
    *,
    base_url: str = DEFAULT_BASE_URL,
    page_dir: str | Path = DEFAULT_PAGE_DIR,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    db_path: str | Path = DEFAULT_DB_PATH,
    workflow_config: CrawlWorkflowConfig | None = None,
    show_progress: bool = True,
) -> CrawlSummary:
    return asyncio.run(
        run_crawl_async(
            base_url=base_url,
            page_dir=page_dir,
            raw_dir=raw_dir,
            db_path=db_path,
            workflow_config=workflow_config,
            show_progress=show_progress,
        )
    )


async def fetch_categories_async(*, base_url: str = DEFAULT_BASE_URL) -> list[str]:
    client = MediaWikiClient(base_url=base_url)
    connector = aiohttp.TCPConnector(limit=0, limit_per_host=10, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        return await client.fetch_categories(session)


def fetch_categories(*, base_url: str = DEFAULT_BASE_URL) -> list[str]:
    return asyncio.run(fetch_categories_async(base_url=base_url))


def _build_run_id() -> str:
    return datetime.now(timezone.utc).strftime("battlecats_%Y%m%dT%H%M%S%fZ")
