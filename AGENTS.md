
# AGENTS.md — Battle Cats Wiki RAG Agent Contract (Revised)

This document defines the operational contract for AI agents working in this repository.
Agents **MUST** follow these rules exactly.

---

## 0) Domain Context (Battle Cats Wiki)

Target source: **Battle Cats Wiki on Miraheze (MediaWiki)**. The corpus is **semi-structured**:

* Pages contain **wikitext**, templates (infobox/navbox), tables, lists, headings, redirects, categories.
* Content types vary heavily (entity pages vs large list pages vs mechanics docs).
* Many pages share repeated boilerplate (navigation templates) → MUST be removed and/or deduplicated.
* The system MUST produce **stable citations** that map to a specific **page revision + chunk**.

Primary ingestion approach SHOULD prefer MediaWiki APIs / exports over raw HTML scraping to preserve structure and reduce noise.

---

## 1) Scope (What you MAY do)

You MAY:

* Implement or modify the **Battle Cats RAG pipeline** within these boundaries:

  * ingestion: fetch / parse / clean / normalize / dedup
  * structuring: page typing, infobox extraction, table row materialization
  * chunking: heading-aware, field-aware, row-aware chunking
  * embeddings: batching, caching, normalization
  * indexing: vector + metadata (and optional BM25/hybrid)
  * retrieval: query rewrite, hybrid retrieval, filters, rerank
  * generation: prompt templates, citations, answer rendering
  * evaluation: golden set, offline eval scripts, metrics, regressions

* Fix bugs, add tests, improve observability (logging/metrics), and refactor **without changing external behavior** unless explicitly requested.

* Update documentation (`README.md`, `/docs`, `/spec`) when behavior or interfaces change.

* Add **small** dependencies only if necessary and compliant with §11.

---

## 2) Non-goals / Prohibitions (What you MUST NOT do)

You MUST NOT:

* Change production credentials, secrets, tokens, or add any secret to code, artifacts, or logs.
* Perform network calls during tests unless explicitly mocked/recorded with fixtures.
* Rebuild or mutate a **persistent index** unless explicitly requested AND gated flags are enabled (§10).
* Change the public API/CLI contract (flags, output schema) without updating docs AND tests.
* Add unspecified “helpful” behavior (e.g., guessing missing inputs, fuzzy-matching IDs).
* Remove citations or weaken citation guarantees (§8).
* Silently change chunking/retrieval parameters that shift quality without documenting and adding eval evidence (§13).
* Violate source site rules (robots, rate limiting, polite crawling). Ingestion MUST implement throttling and caching.
* Store or emit user PII in logs, artifacts, or prompts (unless explicitly required by a test fixture).

---

## 3) Definitions (Key Terms)

* **Corpus**: raw Battle Cats Wiki content (pages, revisions, metadata) before processing.
* **Page**: a MediaWiki page identified by `{pageid, title}` (may redirect).
* **Revision**: a specific version of page content `{revision_id, revision_ts}`.
* **Entity Type**: page classification: `cat | enemy | stage | update | mechanic | list | misc`.
* **Document (Doc)**: structured representation produced from a page revision.
* **Chunk**: unit used for embedding/indexing, derived from a Doc section/field/row.
* **Index**: vector store + metadata store (+ optional BM25).
* **Retrieval**: selecting candidate chunks for answering.
* **Rerank**: reordering candidates using a reranker model.
* **Answer**: final response grounded in retrieved chunks.
* **Citation**: stable reference to retrieved chunk(s) used in the answer.
* **Strategy Version**: semantic version string that identifies parsing/chunking logic affecting IDs (see §5.3, §9).

---

## 4) Repo Map (Where things live)

> Update paths to match this repository.

* `src/ingest/` — fetchers (MediaWiki API), crawlers, rate limit, caching
* `src/parse/` — wikitext parsing, template handling, table/list extraction
* `src/normalize/` — cleaning, boilerplate removal, canonicalization, dedup
* `src/typing/` — page type classifier (rules + category/template heuristics)
* `src/chunking/` — chunkers: section/field/row strategies, overlap logic, chunk router
* `src/embeddings/` — embedding adapters, batching, caching
* `src/index/` — vector store adapter, upsert, metadata schema
* `src/retrieval/` — query pipeline, hybrid retrieval, filters
* `src/rerank/` — reranker adapters, scoring, top-k logic
* `src/generation/` — prompt templates, answer assembly, citations
* `src/api/` or `src/cli/` — external interface (HTTP/CLI)
* `tests/` — unit/integration tests (network MUST be mocked)
* `docs/` — user docs
* `spec/` — product specs, acceptance criteria, eval protocol
* `eval/` — evaluation datasets, scripts, reports
* `artifacts/` — generated immutable pipeline outputs (see §5)

---

## 5) Data Contract (Ingestion → Doc → Chunk)

### 5.1 Ingestion input/output

**Input**

* Source: Battle Cats Wiki (MediaWiki)
* Config: page filters, namespaces, category filters, throttle, cache dir
* Mode (gated):

  * `dry-run` (DEFAULT, read-only)
  * `write-artifacts` (opt-in)
  * `write-index` (opt-in; see §10)

**Page discovery**

Ingestion SHOULD support at least one of:

* category-based discovery (categorymembers)
* namespace-based discovery (ns filters)
* explicit allowlist/seed list

Redirects MUST be resolved to canonical pages (§10.3).

**Output artifacts (immutable)**

Artifacts MUST be content-addressable and reproducible given the same config + revisions (within deterministic boundaries, §9).

* `artifacts/pages/` raw fetch logs + revision pointers + discovery manifests
* `artifacts/docs/` structured docs (jsonl/parquet)
* `artifacts/chunks/` chunk manifests (jsonl)
* `artifacts/embeddings/` embedding cache (optional)

**Recommended artifact naming**

* `artifacts/pages/discovery_{run_id}.json`
* `artifacts/pages/fetch_{run_id}.jsonl`
* `artifacts/docs/docs_{run_id}.jsonl`
* `artifacts/chunks/chunks_{run_id}.jsonl`
* `artifacts/embeddings/emb_{run_id}.parquet` (or per-model cache dir)

`run_id` MUST include: `{source}_{date}_{config_hash}`.

---

### 5.2 Document schema (minimum)

Each Doc MUST include:

* `doc_id` (stable): choose **one** strategy and keep consistent:

  * `pageid` (preferred) OR
  * canonical `title`
* `title`, `canonical_url`
* `revision_id`, `revision_ts`
* `entity_type`
* `sections[]`:
  `{ heading_path: string[], text: string, lists?: any, tables?: any }`
* `infobox?`: `{[key: string]: string}` (if present)
* `categories[]`
* `redirects_from[]` (RECOMMENDED)

**Doc stability expectations**

For the same `{doc_id, revision_id}` and same parser version, doc output MUST be deterministic.

---

### 5.3 Chunk schema (minimum)

Each Chunk MUST include:

* `chunk_id` (stable for same revision + strategy)
* `doc_id`, `title`, `canonical_url`
* `revision_id`
* `strategy_version` (REQUIRED): version string for chunking logic that affects `chunk_id`
* one of:

  * `heading_path` (for narrative/sections)
  * `field_path` (for infobox/stat bundles)
  * `table_path` (for table rows)
* `chunk_type`: `section | field | table_row`
* `text`
* `span?`: `{ start_char: number, end_char: number }` (within `text`)
* `hash` (for dedup)

**Chunk ID stability requirement**

`chunk_id` MUST be deterministic and stable under:

* same `doc_id`
* same `revision_id`
* same `chunk_type`
* same path (`heading_path` / `field_path` / `table_path`)
* same ordinal routing
* same `strategy_version`

Recommended format:

* `chunk_id = hash(doc_id + revision_id + chunk_type + path + ordinal + strategy_version)`

---

## 6) Chunking Strategy Requirements (Battle Cats specific)

Chunking MUST be **type-aware** and route by `entity_type`.

### 6.0 Chunk Router (mandatory)

Chunking MUST have an explicit router:

* Input: `Doc`
* Output: chunk strategy selection (`section`, `field`, `table_row`) with parameters
* Routing rules MUST be deterministic and test-covered.

---

### 6.1 Heading-aware chunking (default for narrative)

* Split by wiki headings into `heading_path`.
* Maintain semantic cohesion; target size MUST be configurable by tokens/characters.
* Overlap MAY be used but MUST be:

  * documented
  * measurable
  * deterministic

---

### 6.2 Field-aware chunking (Cat/Enemy/Stage)

For `cat | enemy | stage`:

* Extract infobox/stats into structured fields.
* Emit `field` chunks grouped into stable bundles, e.g.:

  * `Core Stats`
  * `Abilities / Traits`
  * `Acquisition / Unlock`
  * `Forms / Evolutions` (if applicable)
* Avoid mixing numeric/stat chunks with unrelated narrative paragraphs.

**Bundle membership MUST be stable** for the same parser output.

---

### 6.3 Table-row chunking (List/Update/Drop tables)

For `list | update` and any page with large tables:

* Large tables MUST be materialized row-by-row.
* Each row chunk MUST carry:

  * table name + heading context (`table_path`)
  * row key(s) (e.g., stage name, enemy name, drop item)
* MUST NOT embed full multi-page tables as a single chunk.

---

### 6.4 Boilerplate removal (mandatory)

* Remove or downweight repeated navboxes/footers/templates shared across pages.
* If removal affects accuracy, preserve it as **metadata**, not as chunk text.
* Boilerplate removal MUST be deterministic and logged (counts + rules applied).

**Boilerplate rules**

Boilerplate removal logic MUST be centralized (single module or config file), and changes MUST trigger §13 (quality evidence).

---

## 7) Retrieval Contract (Battle Cats RAG)

### 7.1 Hybrid retrieval expectation

Battle Cats queries often include:

* proper nouns (unit/enemy/stage names)
* numeric stats (DPS/range/cost)
* version/update identifiers

Therefore retrieval SHOULD support **hybrid** modes (BM25 + vector) when configured.

---

### 7.2 Filters

Retrieval MUST accept optional filters:

* `entity_type` (`cat|enemy|stage|update|mechanic|list|misc`)
* `revision_ts` or `revision_id` constraints (if supported)
* tags/categories (optional)

Filters MUST only reduce candidate space; MUST NOT introduce unseen sources.

---

### 7.3 Rerank

If reranking is enabled:

* reranker MUST only reorder retrieved candidates (no unseen sources)
* reranker inputs and top-k MUST be logged in debug mode
* reranker MUST be deterministic for the same inputs in eval mode (§9)

---

## 8) Generation & Citation Guarantees (Hard Requirements)

### 8.1 Grounding

* Every non-trivial factual claim MUST be supported by ≥1 retrieved chunk.
* No chunk → no claim.
* If evidence is insufficient, the Answer MUST say so.

---

### 8.2 Citation format MUST be stable

Each citation MUST include at least:

* `doc_id`
* `chunk_id`
* `canonical_url`
* `revision_id`

Optionally:

* `heading_path` / `field_path` / `table_path`
* `span` inside the chunk

**Recommended serialized format (example)**

```json
{
  "doc_id": "12345",
  "chunk_id": "c_9f2a...",
  "canonical_url": "https://battlecats.miraheze.org/wiki/Some_Page",
  "revision_id": "987654321",
  "path": {"heading_path": ["Stats", "Abilities"]},
  "span": {"start_char": 120, "end_char": 245}
}
```

---

### 8.3 Only cite what you retrieved

Citations MUST refer to chunks actually retrieved for that request.

---

### 8.4 Answer behavior on low/conflicting evidence

If top-k evidence is insufficient or conflicting:

* explicitly state the limitation
* propose a safe fallback (ask for version context, exact unit name, etc.)
* never hallucinate “exact” stats

---

## 9) Determinism & Test Rules

### 9.1 Determinism boundary

For unit tests and eval:

* seed randomness
* mock LLM calls (or record/replay)
* mock network calls (MediaWiki API) with fixtures
* chunk IDs MUST remain stable for unchanged inputs and `strategy_version`

**Strategy versioning rule**

Any change affecting parsing/chunking outputs MUST bump:

* parser version (if applicable) and/or
* `strategy_version` (required in chunks)

---

### 9.2 No network in tests (default)

Tests MUST NOT call external URLs unless explicitly marked and fully mocked/recorded.

---

## 10) Index Safety & Incremental Updates (Battle Cats specific)

### 10.1 Default is read-only

All index mutations MUST be behind explicit flags:

* `--write-index`, `--upsert`, `--rebuild`

Default behavior MUST be **read-only**.

---

### 10.2 Incremental updates are preferred

* Use `revision_id`/`revision_ts` to detect changes.
* Only reprocess changed pages and affected chunks.
* Avoid full re-embedding unless explicitly requested.

---

### 10.3 Redirect handling

* Canonicalize redirects to a single `doc_id`.
* Maintain `redirects_from` for recall/aliasing, but avoid duplicate indexing.
* Retrieval MAY use `redirects_from` as aliases, but indexing MUST be canonical-only.

---

## 11) Dependency Policy

* Prefer standard library and existing dependencies.
* If adding a dependency, you MUST:

  * explain why (what limitation it solves)
  * keep it minimal
  * add tests covering the new code path
  * avoid heavy parsing stacks if a smaller lib is sufficient

---

## 12) Logging & Observability

Do not log secrets or raw user PII.

### 12.1 Ingestion logs (stable fields)

* pages discovered, pages fetched, revisions processed
* throttle/caching stats (cache hit rate)
* docs count, chunks count
* boilerplate removed count, dedup stats
* per-entity-type counts (docs/chunks) RECOMMENDED

---

### 12.2 Query logs (stable fields)

* retrieval mode (vector/BM25/hybrid)
* top-k sizes, latency breakdown
* rerank enabled? model name? reranked top-k
* cache hit?

---

### 12.3 Debug mode

* Off by default
* When enabled, MAY include top-k chunk ids + scores (no secrets)

---

## 13) No Silent Quality Regressions

If you change any of:

* chunking rules (size/overlap/heuristics/type routing)
* boilerplate removal logic
* embedding model or normalization
* retrieval strategy (hybrid params / BM25 settings / vector params)
* reranker model or top-k

You MUST:

* update relevant spec in `spec/` (acceptance + rationale)
* add/adjust eval cases in `eval/`
* provide before/after evidence:

  * metrics (preferred) OR
  * qualitative diff on a small golden set (minimum)

**Minimum eval requirement**

A “small golden set” MUST include:

* ≥ 5 entity queries (cat/enemy/stage)
* ≥ 3 table/list queries (drop tables, release orders, etc.)
* ≥ 2 mechanic queries
* ≥ 1 update/version query

---

## 14) Execution Playbook (How to run)

> Replace commands with your actual tooling.

### 14.1 Setup

* Install: `make setup` / `poetry install` / `pip install -r requirements.txt`
* Env: `.env.example` documents required vars
* never commit `.env`

### 14.2 Tests (MUST pass)

* `make test` 或 `python -m unittest discover`
* lint/format: `make lint`, `make format`

### 14.3 Local run

* Ingest (dry-run preferred):

  * `make ingest DRY_RUN=1 SOURCE=battlecats_wiki`
* Query:

  * `make query Q="..."`

### 14.4 Index safety switches

* Index mutation MUST require explicit opt-in flags.
* Default MUST be read-only.

---

## 15) When uncertain

If requirements are ambiguous:

* do not guess
* implement the smallest safe change
* add a TODO with:

  * the concrete question
  * the exact file/line where it matters

End of contract.