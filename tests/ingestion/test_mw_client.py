import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.ingestion.infrastructure.mw_client import MediaWikiClient


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


class FakeRawSink:
    def __init__(self):
        self.events = []

    async def write_event(self, event):
        self.events.append(event)


class MediaWikiClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_success_returns_data_and_http_meta(self):
        client = MediaWikiClient(base_url="http://unit.invalid")
        session = FakeSession(
            [
                FakeResponse(
                    status=200,
                    json_data={"ok": True},
                    headers={"ETag": "etag", "Last-Modified": "lm"},
                )
            ]
        )

        result = await client._fetch(
            session,
            params={"action": "query"},
            operation="fetch_categories",
        )
        self.assertIsNotNone(result)
        data, http_meta = result
        self.assertEqual(data, {"ok": True})
        self.assertEqual(http_meta["status"], 200)
        self.assertEqual(http_meta["etag"], "etag")
        self.assertEqual(http_meta["last_modified"], "lm")

    async def test_fetch_retries_on_500_then_success(self):
        client = MediaWikiClient(base_url="http://unit.invalid")
        session = FakeSession(
            [
                FakeResponse(status=500),
                FakeResponse(status=200, json_data={"ok": True}),
            ]
        )

        with patch("src.ingestion.infrastructure.mw_client.asyncio.sleep", new=AsyncMock()):
            result = await client._fetch(
                session,
                params={"action": "query"},
                retries=2,
                operation="fetch_categories",
            )

        self.assertIsNotNone(result)
        self.assertEqual(session.calls, 2)

    async def test_fetch_non_200_returns_none(self):
        client = MediaWikiClient(base_url="http://unit.invalid")
        session = FakeSession([FakeResponse(status=404, text_data="not found")])
        result = await client._fetch(
            session,
            params={"action": "query"},
            operation="fetch_categories",
        )
        self.assertIsNone(result)

    async def test_fetch_page_doc_includes_http_meta_and_prefers_revision_content(self):
        client = MediaWikiClient(base_url="http://unit.invalid")
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
                                "slots": {"main": {"content": "wikitext-content"}},
                            }
                        ],
                        "extract": "plain-text-extract",
                        "categories": [{"title": "Category:A"}],
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

        result = await client.fetch_page_doc(session, 123, redirects_from=("Alias B", "Alias A"))
        self.assertIsNotNone(result)
        self.assertEqual(result.pageid, 123)
        self.assertEqual(result.revid, 456)
        self.assertEqual(result.content, "plain-text-extract")
        self.assertEqual(result.redirects_from, ("Alias A", "Alias B"))
        self.assertEqual(result.http["status"], 200)
        self.assertEqual(result.http["etag"], "etag")
        self.assertEqual(result.http["last_modified"], "lm")

    async def test_fetch_all_pages_metadata_returns_canonical_pages_and_redirect_map(self):
        client = MediaWikiClient(base_url="http://unit.invalid")
        progress_events: list[tuple[str, int]] = []
        session = FakeSession(
            [
                FakeResponse(
                    status=200,
                    json_data={
                        "query": {
                            "pages": [
                                {"pageid": 1, "title": "Target Page", "revisions": [{"revid": 10}]},
                                {"pageid": 2, "title": "No Redirect", "lastrevid": 20},
                            ]
                        }
                    },
                ),
                FakeResponse(
                    status=200,
                    json_data={
                        "query": {
                            "allredirects": [
                                {"from": "Alias B", "to": "Target Page"},
                                {"from": "Alias A", "to": "Target Page"},
                                {"from": "Unknown Alias", "to": "Missing Canonical"},
                            ]
                        }
                    },
                ),
            ]
        )
        result = await client.fetch_all_pages_metadata(
            session,
            progress_callback=lambda phase, increment: progress_events.append((phase, increment)),
        )
        self.assertEqual(result.canonical_pages, {1: 10, 2: 20})
        self.assertEqual(result.redirects_from, {1: ("Alias A", "Alias B")})
        self.assertEqual(progress_events, [("discovery_pages", 2), ("discovery_redirects", 3)])

    async def test_fetch_all_pages_metadata_emits_progress_on_continuation(self):
        client = MediaWikiClient(base_url="http://unit.invalid")
        progress_events: list[tuple[str, int]] = []
        session = FakeSession(
            [
                FakeResponse(
                    status=200,
                    json_data={
                        "query": {
                            "pages": [
                                {"pageid": 1, "title": "Target A", "revisions": [{"revid": 10}]},
                                {"pageid": 2, "title": "Target B", "revisions": [{"revid": 20}]},
                            ]
                        },
                        "continue": {"gapcontinue": "Target B"},
                    },
                ),
                FakeResponse(
                    status=200,
                    json_data={
                        "query": {
                            "pages": [
                                {"pageid": 3, "title": "Target C", "revisions": [{"revid": 30}]},
                            ]
                        }
                    },
                ),
                FakeResponse(
                    status=200,
                    json_data={
                        "query": {
                            "allredirects": [
                                {"from": "Alias A1", "to": "Target A"},
                                {"from": "Alias B1", "to": "Target B"},
                            ]
                        },
                        "continue": {"arcontinue": "Alias B1"},
                    },
                ),
                FakeResponse(
                    status=200,
                    json_data={
                        "query": {
                            "allredirects": [
                                {"from": "Alias C1", "to": "Target C"},
                            ]
                        }
                    },
                ),
            ]
        )

        result = await client.fetch_all_pages_metadata(
            session,
            progress_callback=lambda phase, increment: progress_events.append((phase, increment)),
        )

        self.assertEqual(result.canonical_pages, {1: 10, 2: 20, 3: 30})
        self.assertEqual(result.redirects_from, {1: ("Alias A1",), 2: ("Alias B1",), 3: ("Alias C1",)})
        self.assertEqual(
            progress_events,
            [
                ("discovery_pages", 2),
                ("discovery_pages", 1),
                ("discovery_redirects", 2),
                ("discovery_redirects", 1),
            ],
        )

    async def test_fetch_categories_handles_continuation_and_dedup(self):
        client = MediaWikiClient(base_url="http://unit.invalid")
        session = FakeSession(
            [
                FakeResponse(
                    status=200,
                    json_data={
                        "query": {"allcategories": [{"category": "A"}, {"category": "B"}]},
                        "continue": {"accontinue": "B|..."},
                    },
                ),
                FakeResponse(
                    status=200,
                    json_data={
                        "query": {
                            "allcategories": [{"category": "B"}, {"category": "C"}]
                        }
                    },
                ),
            ]
        )
        result = await client.fetch_categories(session)
        self.assertEqual(result, ["A", "B", "C"])

    async def test_fetch_logs_raw_event_with_warnings_and_continue(self):
        sink = FakeRawSink()
        client = MediaWikiClient(base_url="http://unit.invalid", raw_sink=sink, run_id="run_1")
        session = FakeSession(
            [
                FakeResponse(
                    status=200,
                    json_data={
                        "query": {"pages": []},
                        "warnings": {"query": {"*": "warn"}},
                        "continue": {"rvcontinue": "123|0"},
                    },
                    headers={"ETag": "etag", "Last-Modified": "lm"},
                )
            ]
        )

        result = await client._fetch(
            session,
            params={"action": "query"},
            operation="fetch_page_doc",
            pageid=1,
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(sink.events), 1)
        event = sink.events[0]
        self.assertEqual(event["run_id"], "run_1")
        self.assertEqual(event["operation"], "fetch_page_doc")
        self.assertEqual(event["pageid"], 1)
        self.assertEqual(event["outcome"], "success")
        self.assertEqual(event["warnings"], {"query": {"*": "warn"}})
        self.assertEqual(event["continue_token"], {"rvcontinue": "123|0"})
        self.assertEqual(event["request"]["params"]["action"], "query")
        self.assertEqual(event["http"]["status"], 200)
        self.assertEqual(event["http"]["etag"], "etag")

    async def test_fetch_logs_raw_retry_events(self):
        sink = FakeRawSink()
        client = MediaWikiClient(base_url="http://unit.invalid", raw_sink=sink, run_id="run_2")
        session = FakeSession([FakeResponse(status=500), FakeResponse(status=500)])

        with patch("src.ingestion.infrastructure.mw_client.asyncio.sleep", new=AsyncMock()):
            result = await client._fetch(
                session,
                params={"action": "query"},
                retries=2,
                operation="fetch_all_pages_metadata",
            )

        self.assertIsNone(result)
        self.assertEqual(len(sink.events), 2)
        self.assertEqual(sink.events[0]["outcome"], "retryable_error")
        self.assertEqual(sink.events[1]["outcome"], "retryable_error")
        self.assertEqual(sink.events[0]["attempt"], 1)
        self.assertEqual(sink.events[1]["attempt"], 2)
