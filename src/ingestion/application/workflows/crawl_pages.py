import asyncio
from dataclasses import dataclass

import aiohttp
from loguru import logger

from src.ingestion.domain.models import CrawlSummary, PageRef
from src.ingestion.infrastructure.fs_sink import JsonFileSink
from src.ingestion.infrastructure.mw_client import MediaWikiClient
from src.ingestion.infrastructure.registry_sqlite import SQLiteRegistryRepository


@dataclass(frozen=True)
class CrawlWorkflowConfig:
    semaphore_limit: int = 5
    chunk_size: int = 50
    polite_sleep_seconds: float = 1.0
    connector_limit: int = 0
    connector_limit_per_host: int = 10
    connector_ttl_dns_cache: int = 300


class CrawlPagesWorkflow:
    def __init__(
        self,
        mw_client: MediaWikiClient,
        registry: SQLiteRegistryRepository,
        sink: JsonFileSink,
        config: CrawlWorkflowConfig | None = None,
    ) -> None:
        self.mw_client = mw_client
        self.registry = registry
        self.sink = sink
        self.config = config or CrawlWorkflowConfig()
        self._semaphore = asyncio.Semaphore(self.config.semaphore_limit)

    async def run(self) -> CrawlSummary:
        connector = aiohttp.TCPConnector(
            limit=self.config.connector_limit,
            limit_per_host=self.config.connector_limit_per_host,
            ttl_dns_cache=self.config.connector_ttl_dns_cache,
        )
        async with aiohttp.ClientSession(connector=connector) as session:
            remote_pages = await self.mw_client.fetch_all_pages_metadata(session)
            local_pages = self.registry.get_local_state()

            refs = [
                PageRef(pageid=pageid, remote_revid=remote_revid)
                for pageid, remote_revid in remote_pages.items()
                if local_pages.get(pageid) is None or remote_revid > local_pages[pageid]
            ]
            if not refs:
                logger.info("All pages are up to date.")
                return CrawlSummary(
                    discovered_total=len(remote_pages),
                    queued_total=0,
                    processed_total=0,
                    failed_total=0,
                    skipped_total=len(remote_pages),
                )

            logger.info("Starting download for {} pages...", len(refs))
            processed_total = 0
            failed_total = 0

            for i in range(0, len(refs), self.config.chunk_size):
                chunk = refs[i : i + self.config.chunk_size]
                results = await asyncio.gather(
                    *(self._process_page(session, ref) for ref in chunk),
                    return_exceptions=False,
                )
                processed_total += sum(1 for ok in results if ok)
                failed_total += sum(1 for ok in results if not ok)
                logger.info("Processing chunk {}/{}...", i, len(refs))
                await asyncio.sleep(self.config.polite_sleep_seconds)

            return CrawlSummary(
                discovered_total=len(remote_pages),
                queued_total=len(refs),
                processed_total=processed_total,
                failed_total=failed_total,
                skipped_total=len(remote_pages) - len(refs),
            )

    async def _process_page(self, session: aiohttp.ClientSession, ref: PageRef) -> bool:
        async with self._semaphore:
            page_doc = await self.mw_client.fetch_page_doc(session, ref.pageid)
            if page_doc is None:
                return False

            file_path = self.sink.write_page_doc(page_doc)
            self.registry.upsert_page(page_doc, file_path, ref.remote_revid)
            logger.info("Saved JSON: {}", page_doc.title)
            return True
