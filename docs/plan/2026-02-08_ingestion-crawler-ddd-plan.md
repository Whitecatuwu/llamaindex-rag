# Ingestion Crawler DDD Plan

## Summary
本文件描述 Battle Cats Wiki crawler 從單一 `WikiCrawler` 類別拆分為 `domain / application / infrastructure` 的方案，並保留既有資料契約（page JSON 欄位與 SQLite `pages` schema）與 `fetch_categories` 能力。

## Architecture
- Bounded Context: `src/ingestion/`
- Domain layer: deterministic data contract 與命名規則
- Application layer: crawl workflow orchestration
- Infrastructure layer: MediaWiki API, SQLite registry, JSON file sink
- Interface layer: 函數型 API (`run_crawl`, `fetch_categories`)

## Public API
- `run_crawl(...) -> CrawlSummary`
- `run_crawl_async(...) -> CrawlSummary`
- `fetch_categories(...) -> list[str]`
- `fetch_categories_async(...) -> list[str]`

## Data Contract
- `WikiPageDoc` 輸出欄位維持：
  - `source`, `pageid`, `title`, `canonical_url`, `revid`, `timestamp`
  - `content_model`, `categories`, `content`, `is_redirect`, `redirect_target`
  - `fetched_at`, `http`
- SQLite `pages` schema 維持：
  - `page_id`, `title`, `last_revid`, `last_updated`, `file_path`, `categories`

## Workflow Steps
1. `discover_remote`: `fetch_all_pages_metadata`
2. `load_local`: `get_local_state`
3. `diff`: new page 或 remote `revid` 較新才排入處理
4. `process_page`: fetch page -> write JSON -> upsert registry
5. `batching`: chunk + semaphore + polite sleep
6. `summary`: discovered/queued/processed/failed/skipped 計數回傳

## Fetch Categories Contract
- 使用 MediaWiki `list=allcategories` + continuation
- 回傳 `list[str]`
- 跨頁合併後去重，保留 first-seen 順序
- 失敗時回傳空列表並記錄 log

## Determinism
- `sanitize_filename`, `build_canonical_url`, `make_filename` 為純函數
- 同 title/pageid 輸入應產生穩定檔名與 URL

## Test Plan
- `tests/ingestion/test_mw_client.py`
- `tests/ingestion/test_registry_sqlite.py`
- `tests/ingestion/test_fs_sink.py`
- `tests/ingestion/test_crawl_workflow.py`
- `tests/ingestion/test_crawl_api.py`

## BDD Spec
- `spec/feature/ingestion_crawler_ddd_acceptance.feature`
- 覆蓋分層結構、`fetch_categories` continuation、diff 行為、JSON 契約、retry 行為、無更新早退。

## 2026-02-09 Artifact layout update
- Ingestion output is split into two tracks:
  - `artifacts/raw/wiki/page`: structured `WikiPageDoc` JSON files for downstream pipeline.
  - `artifacts/raw/wiki/raw`: append-only API raw logs for replay/debug.
- Raw log file format:
  - `api_calls_{run_id}.jsonl` (one file per crawl run).
  - Each event includes `run_id`, `operation`, `pageid`, `attempt`, request params, HTTP meta, full `response_json`, optional `response_text`, `warnings`, `continue_token`, error payload, timing, and `outcome`.
- `run_crawl/run_crawl_async` API changes:
  - New arguments: `page_dir`, `raw_dir`.
  - `page_dir` is the single page artifact selector.
