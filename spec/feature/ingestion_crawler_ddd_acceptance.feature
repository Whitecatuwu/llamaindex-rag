Feature: Ingestion crawler DDD refactor acceptance
  As a team maintaining Battle Cats Wiki ingestion
  I want crawler behavior preserved after DDD refactor
  So that architecture is cleaner without changing external contracts

  Scenario: A1 DDD layering and entrypoints exist
    Given the repository root path
    When I check ingestion structure
    Then "src/ingestion/domain" should exist
    And "src/ingestion/application/workflows" should exist
    And "src/ingestion/infrastructure" should exist
    And "src/ingestion/crawl.py" should expose "run_crawl"
    And "src/ingestion/crawl.py" should expose "fetch_categories"

  Scenario: A2 fetch_categories supports continuation pages
    Given MediaWiki allcategories API returns multiple continued pages
    When fetch_categories_async is executed
    Then it should merge category names from all pages
    And it should keep first-seen order
    And it should remove duplicate category names

  Scenario: A3 crawler only processes diff pages
    Given remote metadata and local registry state
    When crawl workflow runs
    Then only pages that are new or have newer remote revision should be processed
    And unchanged pages should not trigger fetch, save, or upsert

  Scenario: A4 page JSON output contract remains stable
    Given one page is fetched successfully
    When it is written by ingestion sink
    Then output JSON should include keys "source", "pageid", "title", "canonical_url", "revid", "timestamp"
    And output JSON should include keys "categories", "content", "is_redirect", "redirect_target", "fetched_at", "http"

  Scenario: A5 _fetch retry and failure behavior
    Given first HTTP response is 500 or 429 and later response is 200
    When MediaWiki client _fetch executes with retries
    Then it should retry and eventually return data with http metadata
    And non-200 non-retryable responses should return no data

  Scenario: A6 workflow exits early when no updates are needed
    Given remote pages and local registry are fully aligned
    When crawl workflow runs
    Then processed_total should be 0
    And no page fetch should be executed
