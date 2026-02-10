import unittest
from pathlib import Path

from src.ingestion.application.workflows.crawl_pages import CrawlPagesWorkflow, CrawlWorkflowConfig
from src.ingestion.domain.models import PageDiscoveryResult, WikiPageDoc
from tests.utils.tempdir import managed_temp_dir


def make_doc(pageid: int, revid: int) -> WikiPageDoc:
    return WikiPageDoc(
        source="battlecats.miraheze.org",
        pageid=pageid,
        title=f"Page {pageid}",
        canonical_url=f"https://battlecats.miraheze.org/wiki/Page_{pageid}",
        revid=revid,
        timestamp="2020-01-01T00:00:00Z",
        content_model="wikitext",
        categories=(),
        content=f"content-{pageid}",
        is_redirect=False,
        redirect_target=None,
        fetched_at="2020-01-01T00:00:01Z",
        http={"status": 200, "etag": "", "last_modified": ""},
    )


class FakeMwClient:
    def __init__(
        self,
        remote_pages: dict[int, int],
        docs: dict[int, WikiPageDoc | None],
        redirects_from: dict[int, tuple[str, ...]] | None = None,
    ) -> None:
        self.remote_pages = remote_pages
        self.docs = docs
        self.redirects_from = redirects_from or {}
        self.fetch_page_calls: list[int] = []
        self.fetch_page_redirects: dict[int, tuple[str, ...]] = {}

    async def fetch_all_pages_metadata(self, _session):
        return PageDiscoveryResult(
            canonical_pages=self.remote_pages,
            redirects_from=self.redirects_from,
        )

    async def fetch_page_doc(self, _session, pageid: int, retries: int = 3, redirects_from: tuple[str, ...] = ()):
        self.fetch_page_calls.append(pageid)
        self.fetch_page_redirects[pageid] = redirects_from
        return self.docs.get(pageid)


class FakeRegistry:
    def __init__(self, local_state: dict[int, int], should_fail: bool = False) -> None:
        self.local_state = local_state
        self.upserts: list[tuple[int, int, str]] = []
        self.should_fail = should_fail

    def get_local_state(self):
        return self.local_state

    def upsert_page(self, page_doc: WikiPageDoc, file_path: Path):
        if self.should_fail:
            raise RuntimeError("db write failed")
        self.upserts.append((page_doc.pageid, page_doc.revid, str(file_path)))


class FakeSink:
    def __init__(self, base_dir: Path, should_fail: bool = False) -> None:
        self.base_dir = base_dir
        self.written: list[int] = []
        self.should_fail = should_fail

    def write_page_doc(self, page_doc: WikiPageDoc) -> Path:
        if self.should_fail:
            raise RuntimeError("disk write failed")
        self.written.append(page_doc.pageid)
        return self.base_dir / f"{page_doc.pageid}.json"


class CrawlWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_diff_processes_only_new_or_updated_pages(self):
        with managed_temp_dir("crawl_workflow_diff") as tmp:
            mw = FakeMwClient(
                remote_pages={1: 10, 2: 20, 3: 30},
                docs={2: make_doc(2, 20), 3: make_doc(3, 30)},
            )
            registry = FakeRegistry(local_state={1: 10, 2: 19})
            sink = FakeSink(tmp)
            workflow = CrawlPagesWorkflow(
                mw_client=mw,
                registry=registry,
                sink=sink,
                config=CrawlWorkflowConfig(chunk_size=2, polite_sleep_seconds=0),
            )

            summary = await workflow.run()
            self.assertEqual(summary.discovered_total, 3)
            self.assertEqual(summary.queued_total, 2)
            self.assertEqual(summary.processed_total, 2)
            self.assertEqual(summary.failed_total, 0)
            self.assertEqual(sorted(mw.fetch_page_calls), [2, 3])
            self.assertEqual(len(registry.upserts), 2)

    async def test_no_updates_returns_early(self):
        with managed_temp_dir("crawl_workflow_no_updates") as tmp:
            mw = FakeMwClient(remote_pages={1: 10}, docs={1: make_doc(1, 10)})
            registry = FakeRegistry(local_state={1: 10})
            sink = FakeSink(tmp)
            workflow = CrawlPagesWorkflow(
                mw_client=mw,
                registry=registry,
                sink=sink,
                config=CrawlWorkflowConfig(chunk_size=1, polite_sleep_seconds=0),
            )

            summary = await workflow.run()
            self.assertEqual(summary.queued_total, 0)
            self.assertEqual(summary.processed_total, 0)
            self.assertEqual(summary.skipped_total, 1)
            self.assertEqual(mw.fetch_page_calls, [])

    async def test_failed_page_fetch_counts_as_failed(self):
        with managed_temp_dir("crawl_workflow_failed_fetch") as tmp:
            mw = FakeMwClient(remote_pages={9: 9}, docs={9: None})
            registry = FakeRegistry(local_state={})
            sink = FakeSink(tmp)
            workflow = CrawlPagesWorkflow(
                mw_client=mw,
                registry=registry,
                sink=sink,
                config=CrawlWorkflowConfig(chunk_size=1, polite_sleep_seconds=0),
            )

            summary = await workflow.run()
            self.assertEqual(summary.queued_total, 1)
            self.assertEqual(summary.processed_total, 0)
            self.assertEqual(summary.failed_total, 1)

    async def test_sink_failure_counts_failed_and_continues(self):
        with managed_temp_dir("crawl_workflow_sink_failure") as tmp:
            mw = FakeMwClient(remote_pages={2: 20, 3: 30}, docs={2: make_doc(2, 20), 3: make_doc(3, 30)})
            registry = FakeRegistry(local_state={})
            sink = FakeSink(tmp, should_fail=True)
            workflow = CrawlPagesWorkflow(
                mw_client=mw,
                registry=registry,
                sink=sink,
                config=CrawlWorkflowConfig(chunk_size=2, polite_sleep_seconds=0),
            )

            summary = await workflow.run()
            self.assertEqual(summary.queued_total, 2)
            self.assertEqual(summary.processed_total, 0)
            self.assertEqual(summary.failed_total, 2)

    async def test_registry_failure_counts_failed_and_continues(self):
        with managed_temp_dir("crawl_workflow_registry_failure") as tmp:
            mw = FakeMwClient(remote_pages={2: 20, 3: 30}, docs={2: make_doc(2, 20), 3: make_doc(3, 30)})
            registry = FakeRegistry(local_state={}, should_fail=True)
            sink = FakeSink(tmp)
            workflow = CrawlPagesWorkflow(
                mw_client=mw,
                registry=registry,
                sink=sink,
                config=CrawlWorkflowConfig(chunk_size=2, polite_sleep_seconds=0),
            )

            summary = await workflow.run()
            self.assertEqual(summary.queued_total, 2)
            self.assertEqual(summary.processed_total, 0)
            self.assertEqual(summary.failed_total, 2)

    async def test_registry_uses_fetched_page_revid_when_remote_has_newer_value(self):
        with managed_temp_dir("crawl_workflow_revid_race") as tmp:
            mw = FakeMwClient(remote_pages={2: 99}, docs={2: make_doc(2, 20)})
            registry = FakeRegistry(local_state={})
            sink = FakeSink(tmp)
            workflow = CrawlPagesWorkflow(
                mw_client=mw,
                registry=registry,
                sink=sink,
                config=CrawlWorkflowConfig(chunk_size=1, polite_sleep_seconds=0),
            )

            summary = await workflow.run()
            self.assertEqual(summary.processed_total, 1)
            self.assertEqual(registry.upserts, [(2, 20, str(tmp / "2.json"))])

    async def test_redirect_aliases_are_passed_to_page_doc_builder(self):
        with managed_temp_dir("crawl_workflow_redirect_aliases") as tmp:
            mw = FakeMwClient(
                remote_pages={2: 20},
                docs={2: make_doc(2, 20)},
                redirects_from={2: ("Alias B", "Alias A")},
            )
            registry = FakeRegistry(local_state={})
            sink = FakeSink(tmp)
            workflow = CrawlPagesWorkflow(
                mw_client=mw,
                registry=registry,
                sink=sink,
                config=CrawlWorkflowConfig(chunk_size=1, polite_sleep_seconds=0),
            )

            summary = await workflow.run()
            self.assertEqual(summary.processed_total, 1)
            self.assertEqual(mw.fetch_page_redirects[2], ("Alias B", "Alias A"))
