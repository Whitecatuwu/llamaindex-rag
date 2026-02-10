import asyncio
from contextlib import ExitStack
from dataclasses import dataclass

import aiohttp
from tqdm import tqdm
from src.config.logger_config import logger

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
    show_progress: bool = True


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
            with ExitStack() as discovery_progress_stack:
                discovery_pages_progress = None
                discovery_redirects_progress = None
                if self.config.show_progress:
                    discovery_pages_progress = discovery_progress_stack.enter_context(
                        tqdm(
                            total=None,
                            desc="Discovery pages",
                            unit=" page",
                            leave=True,
                        )
                    )
                    discovery_redirects_progress = discovery_progress_stack.enter_context(
                        tqdm(
                            total=None,
                            desc="Discovery redirects",
                            unit=" redirect",
                            leave=True,
                        )
                    )

                def _on_discovery_progress(phase: str, increment: int) -> None:
                    if increment <= 0:
                        return
                    if phase == "discovery_pages" and discovery_pages_progress is not None:
                        discovery_pages_progress.update(increment)
                    elif phase == "discovery_redirects" and discovery_redirects_progress is not None:
                        discovery_redirects_progress.update(increment)

                discovery = await self.mw_client.fetch_all_pages_metadata(
                    session,
                    progress_callback=_on_discovery_progress if self.config.show_progress else None,
                )
            remote_pages = discovery.canonical_pages
            local_pages = self.registry.get_local_state()

            refs = [
                PageRef(
                    pageid=pageid,
                    remote_revid=remote_revid,
                    redirects_from=discovery.redirects_from.get(pageid, ()),
                )
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
            total_chunks = (len(refs) + self.config.chunk_size - 1) // self.config.chunk_size

            with tqdm(
                total=len(refs),
                desc="Ingestion pages",
                unit="page",
                leave=True,
                disable=not self.config.show_progress,
            ) as progress:
                for chunk_index, i in enumerate(range(0, len(refs), self.config.chunk_size), start=1):
                    chunk = refs[i : i + self.config.chunk_size]
                    results = await asyncio.gather(
                        *(self._process_page(session, ref) for ref in chunk),
                        return_exceptions=False,
                    )
                    processed_total += sum(1 for ok in results if ok)
                    failed_total += sum(1 for ok in results if not ok)
                    progress.update(len(chunk))
                    logger.info("Processing chunk {}/{}...", chunk_index, total_chunks)
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
            try:
                page_doc = await self.mw_client.fetch_page_doc(
                    session,
                    ref.pageid,
                    redirects_from=ref.redirects_from,
                )
                if page_doc is None:
                    return False

                file_path = self.sink.write_page_doc(page_doc)
                self.registry.upsert_page(page_doc, file_path)
                logger.info("Saved JSON: {}", page_doc.title)
                return True
            except Exception as exc:
                logger.exception(
                    "Failed processing pageid {} with error type {}: {}",
                    ref.pageid,
                    type(exc).__name__,
                    exc,
                )
                return False
