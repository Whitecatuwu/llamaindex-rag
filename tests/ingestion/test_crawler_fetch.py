import importlib
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class FakeResponse:
    def __init__(self, status=200, json_data=None, text_data="", headers=None):
        self.status = status
        self._json_data = json_data
        self._text_data = text_data
        self.headers = headers or {}
        self.request_info = SimpleNamespace(real_url="http://test.invalid")
        self.history = ()

    async def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data

    async def text(self):
        return self._text_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, *args, **kwargs):
        if not self._responses:
            raise AssertionError("No more fake responses configured")
        self.calls += 1
        return self._responses.pop(0)


_crawler_module = None


def get_crawler_module():
    global _crawler_module
    if _crawler_module is None:
        with patch("loguru.logger.add", return_value=None):
            _crawler_module = importlib.import_module("src.ingestion.crawler")
        from loguru import logger as loguru_logger

        loguru_logger.disable("src.ingestion.crawler")
    return _crawler_module


def make_crawler():
    crawler_module = get_crawler_module()
    with patch("src.ingestion.crawler.sqlite3.connect") as connect_mock:
        conn = sqlite3.connect(":memory:")
        connect_mock.return_value = conn
        return crawler_module.WikiCrawler()


class FetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_success_returns_data_and_http_meta(self):
        crawler = make_crawler()
        session = FakeSession(
            [
                FakeResponse(
                    status=200,
                    json_data={"ok": True},
                    headers={"ETag": "etag", "Last-Modified": "lm"},
                )
            ]
        )

        result = await crawler._fetch(session, params={"action": "query"})
        self.assertIsNotNone(result)
        data, http_meta = result
        self.assertEqual(data, {"ok": True})
        self.assertEqual(http_meta["status"], 200)
        self.assertEqual(http_meta["etag"], "etag")
        self.assertEqual(http_meta["last_modified"], "lm")

    async def test_fetch_retries_on_500_then_success(self):
        crawler = make_crawler()
        session = FakeSession(
            [
                FakeResponse(status=500),
                FakeResponse(status=200, json_data={"ok": True}),
            ]
        )

        with patch("src.ingestion.crawler.asyncio.sleep", new=AsyncMock()):
            result = await crawler._fetch(session, params={"action": "query"}, retries=2)

        self.assertIsNotNone(result)
        self.assertEqual(session.calls, 2)

    async def test_fetch_non_200_returns_none(self):
        crawler = make_crawler()
        session = FakeSession([FakeResponse(status=404, text_data="not found")])

        result = await crawler._fetch(session, params={"action": "query"})
        self.assertIsNone(result)

    async def test_fetch_page_data_includes_http_meta(self):
        crawler = make_crawler()
        data = {
            "query": {
                "pages": [
                    {
                        "pageid": 123,
                        "title": "Test Page",
                        "revisions": [
                            {
                                "revid": 456,
                                "timestamp": "2020-01-01T00:00:00Z",
                                "slots": {"main": {"content": "abc"}},
                            }
                        ],
                    }
                ]
            }
        }
        session = FakeSession(
            [
                FakeResponse(
                    status=200,
                    json_data=data,
                    headers={"ETag": "etag", "Last-Modified": "lm"},
                )
            ]
        )

        result = await crawler.fetch_page_data(session, "Test Page")
        self.assertIsNotNone(result)
        self.assertIn("http", result)
        self.assertEqual(result["http"]["status"], 200)
        self.assertEqual(result["http"]["etag"], "etag")
        self.assertEqual(result["http"]["last_modified"], "lm")
