from __future__ import annotations
import asyncio
from pathlib import Path

import aiohttp

from src.ingestion.application.workflows.crawl_pages import CrawlPagesWorkflow, CrawlWorkflowConfig
from src.ingestion.domain.models import CrawlSummary
from src.ingestion.infrastructure.fs_sink import JsonFileSink
from src.ingestion.infrastructure.mw_client import MediaWikiClient
from src.ingestion.infrastructure.registry_sqlite import SQLiteRegistryRepository


DEFAULT_BASE_URL = "https://battlecats.miraheze.org/w/api.php"
DEFAULT_DATA_DIR = Path("artifacts/raw/wiki")
DEFAULT_HTML_DIR = DEFAULT_DATA_DIR / "pages"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "wiki_registry.db"


async def run_crawl_async(
    *,
    base_url: str = DEFAULT_BASE_URL,
    html_dir: str | Path = DEFAULT_HTML_DIR,
    db_path: str | Path = DEFAULT_DB_PATH,
    workflow_config: CrawlWorkflowConfig | None = None,
) -> CrawlSummary:
    html_path = Path(html_dir)
    html_path.mkdir(parents=True, exist_ok=True)
    db_file_path = Path(db_path)
    db_file_path.parent.mkdir(parents=True, exist_ok=True)

    mw_client = MediaWikiClient(base_url=base_url)
    registry = SQLiteRegistryRepository(db_file_path)
    sink = JsonFileSink(html_path)
    workflow = CrawlPagesWorkflow(
        mw_client=mw_client,
        registry=registry,
        sink=sink,
        config=workflow_config,
    )
    try:
        return await workflow.run()
    finally:
        registry.close()


def run_crawl(
    *,
    base_url: str = DEFAULT_BASE_URL,
    html_dir: str | Path = DEFAULT_HTML_DIR,
    db_path: str | Path = DEFAULT_DB_PATH,
    workflow_config: CrawlWorkflowConfig | None = None,
) -> CrawlSummary:
    return asyncio.run(
        run_crawl_async(
            base_url=base_url,
            html_dir=html_dir,
            db_path=db_path,
            workflow_config=workflow_config,
        )
    )


async def fetch_categories_async(*, base_url: str = DEFAULT_BASE_URL) -> list[str]:
    client = MediaWikiClient(base_url=base_url)
    connector = aiohttp.TCPConnector(limit=0, limit_per_host=10, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        return await client.fetch_categories(session)


def fetch_categories(*, base_url: str = DEFAULT_BASE_URL) -> list[str]:
    return asyncio.run(fetch_categories_async(base_url=base_url))