# Classification DDD Pipeline Plan

## Summary
本文件將 Battle Cats Wiki 頁面分類流程定義為 DDD 的分段 Application Use Case：`ClassifyWikiPagesUseCase`，以 `discover -> load -> classify -> persist -> report` 的 workflow 執行。支援 `html` 與 `registry.db` 兩種來源，並由 ingestion adapter 觸發。

## Architecture
- Bounded Context: `src/classification/`
- Domain layer: entity/type/rules/classifier
- Application layer: use case + workflow + ports
- Infrastructure layer: sources + sinks
- Interfaces layer: ingestion adapter

## UseCase Contract
### Command
- `source_mode`: `html|db`
- `low_confidence_threshold`: float
- `include_redirects`: bool

### Result
- `total_pages`
- `classified_count`
- `misc_count`
- `low_conf_count`
- `conflict_count`
- `parse_warning_count`
- `by_entity_type`

## Pipeline Steps
1. `discover`: 根據 `source_mode` 蒐集 `PageRef`
2. `load`: 載入頁面，若 JSON 損毀使用 fallback extractor，並標記 `parse_warning`
3. `classify`: 規則打分決定主類；低信心或衝突降級為 `misc + reason`
4. `persist`: 輸出 labels 與 review queue
5. `report`: 輸出統計報告

## Rule Strategy
- 主類優先序: `update > cat/enemy/stage > list > mechanic > misc`
- 主訊號: categories
- 輔助訊號: title/content patterns
- 子類採多標籤映射
  - `cat`: rarity/role/attack/target_trait/ability/source
  - `enemy`: trait/ability/campaign_scope
  - `stage`: family/progression/modifier/event_window
  - `update|mechanic|list`: 專屬 subtype map

## Determinism
- 固定 `classification_strategy_version`
- 同輸入 + 同版本 => 同輸出
- 規則異動需 bump 版本並更新測試/驗證資料

## Logging
建議穩定欄位：
- `source_mode`
- `total_discovered`
- `loaded_ok`
- `parse_warning_count`
- `by_entity_type`
- `low_conf_count`
- `conflict_count`
- `duration_ms`

## Test Plan
- Domain rules tests
- Subtype mapping tests
- Pipeline use case tests
- Fault-tolerance loader tests
- Ingestion adapter tests

## Acceptance Criteria
1. 可由 `html` 與 `db` 兩來源完成分類流程。
2. 產生三種輸出：
   - `page_labels_*.jsonl`
   - `review_queue_*.jsonl`
   - `classification_report_*.json`
3. 無法判定或衝突頁面須落 `misc + reason`。
4. 同輸入重跑輸出一致。
5. Ingestion adapter 能觸發同一 Use Case。

## Assumptions
- 文檔語言以中文為主，術語保留英文。
- 僅輸出文檔與 BDD 規格，不新增 BDD 執行依賴。
- `.feature` 先做規格化描述，後續再決定 `behave` 或 `pytest-bdd`。
