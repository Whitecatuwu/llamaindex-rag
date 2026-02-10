import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.ingestion.crawl import (
    fetch_categories,
    fetch_categories_async,
    run_crawl,
    run_crawl_async,
)
from src.ingestion.domain.models import CrawlSummary


class CrawlApiTests(unittest.TestCase):
    def test_run_crawl_sync_wrapper(self):
        expected = CrawlSummary(
            discovered_total=10,
            queued_total=5,
            processed_total=5,
            failed_total=0,
            skipped_total=5,
        )
        with patch("src.ingestion.crawl.run_crawl_async", new=AsyncMock(return_value=expected)):
            result = run_crawl()
        self.assertEqual(result, expected)

    def test_fetch_categories_sync_wrapper(self):
        with patch(
            "src.ingestion.crawl.fetch_categories_async",
            new=AsyncMock(return_value=["CatA", "CatB"]),
        ):
            result = fetch_categories()
        self.assertEqual(result, ["CatA", "CatB"])


class CrawlApiAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_crawl_async_wiring_and_close(self):
        expected = CrawlSummary(
            discovered_total=3,
            queued_total=2,
            processed_total=2,
            failed_total=0,
            skipped_total=1,
        )
        registry = MagicMock()
        raw_sink = MagicMock()
        workflow = MagicMock()
        workflow.run = AsyncMock(return_value=expected)

        with (
            patch("src.ingestion.crawl.MediaWikiClient", return_value=MagicMock()),
            patch("src.ingestion.crawl.SQLiteRegistryRepository", return_value=registry),
            patch("src.ingestion.crawl.JsonFileSink", return_value=MagicMock()),
            patch("src.ingestion.crawl.RawApiJsonlSink", return_value=raw_sink),
            patch("src.ingestion.crawl.CrawlPagesWorkflow", return_value=workflow),
        ):
            result = await run_crawl_async()

        self.assertEqual(result, expected)
        raw_sink.close.assert_called_once()
        registry.close.assert_called_once()

    async def test_fetch_categories_async_calls_client(self):
        client = MagicMock()
        client.fetch_categories = AsyncMock(return_value=["A", "B"])
        with patch("src.ingestion.crawl.MediaWikiClient", return_value=client):
            result = await fetch_categories_async(base_url="http://unit.invalid")

        self.assertEqual(result, ["A", "B"])
        client.fetch_categories.assert_awaited()

    async def test_run_crawl_async_accepts_page_dir(self):
        expected = CrawlSummary(
            discovered_total=0,
            queued_total=0,
            processed_total=0,
            failed_total=0,
            skipped_total=0,
        )
        with (
            patch("src.ingestion.crawl.MediaWikiClient", return_value=MagicMock()),
            patch("src.ingestion.crawl.SQLiteRegistryRepository", return_value=MagicMock()),
            patch("src.ingestion.crawl.JsonFileSink", return_value=MagicMock()),
            patch("src.ingestion.crawl.RawApiJsonlSink", return_value=MagicMock()),
            patch("src.ingestion.crawl.CrawlPagesWorkflow", return_value=MagicMock(run=AsyncMock(return_value=expected))),
        ):
            result = await run_crawl_async(page_dir="tests/tmp/same/path")

        self.assertEqual(result, expected)
