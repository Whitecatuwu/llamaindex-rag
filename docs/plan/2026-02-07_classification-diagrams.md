# Classification Pipeline Diagrams

## Workflow Diagram
此圖描述分類 Use Case 從入口到報告輸出的完整流程，對應 `discover -> load -> classify -> persist -> report`。

```mermaid
flowchart TD
    A[入口] --> B{觸發方式}
    B -->|Classification Entrypoint| D[src/classification/classify.py (run_classify)]

    D --> E

    E --> F[ClassifyWikiPagesUseCase.execute]
    F --> G[ClassificationPipeline.run]

    G --> H[1. discover]
    H --> I{source_mode}
    I -->|html| J[HtmlPageSource.discover]
    I -->|db| K[RegistryPageSource.discover]

    G --> L[2. load]
    L --> M[HtmlPageSource.load / RegistryPageSource.load]
    M --> N{JSON 可解析?}
    N -->|是| O[建立 WikiPage]
    N -->|否| P[Fallback extractor + parse_warning]
    P --> O

    G --> Q0[3. should_classify]
    Q0 --> S0{full_rebuild or incremental off?}
    S0 -->|是| Q
    S0 -->|否| S1[讀取 classification_state.db]
    S1 --> S2{revid 可用?}
    S2 -->|是| S3[比對 last_revid]
    S2 -->|否| S4[計算 content_hash 比對]
    S3 -->|未變更| SKIP[skip unchanged]
    S4 -->|未變更| SKIP
    S3 -->|已變更| Q
    S4 -->|已變更| Q

    G --> Q[4. classify]
    Q --> R[RuleBasedClassifier.classify]
    R --> S[主類規則打分 update>cat/enemy/stage>list>mechanic>misc]
    S --> T{低信心/衝突?}
    T -->|是| U[entity_type=misc + reason]
    T -->|否| V[輸出主類 + 多值子類]

    G --> W[5. persist]
    W --> X[JsonlClassificationSink.write_label]
    W --> Y{misc or low_conf or conflict}
    Y -->|是| Z[write_review]
    W --> X2[ClassifiedJsonSink.write_label]
    X2 --> SU[6. state upsert]

    G --> AA[7. report]
    AA --> AB[JsonReportSink.write_report]

    AB --> AC[ClassifyWikiPagesResult 回傳]
```

## Data Object Flow Diagram
此圖描述資料物件在 pipeline 內的流向與最終產物。

```mermaid
flowchart LR
    A[PageRef\nsource_id, location, metadata] --> B[WikiPage\npageid, title, revid, categories, content,\nis_redirect, source_path, parse_warning]
    B --> BS[Incremental Gate\nrevid/hash + strategy_version]
    BS -->|unchanged| SK[skip]
    BS -->|changed| C
    B --> C[Classification\nentity_type, subtypes[], confidence,\nreasons[], matched_rules[], strategy_version]
    B --> D[label row]
    C --> D
    D --> E[page_labels_*.jsonl]
    D --> E2[classified/<entity_type>/*.json (+subtypes)]

    D --> F{needs_review?}
    F -->|misc / low_conf / conflict| G[review row]
    G --> H[review_queue_*.jsonl]

    B --> I[Pipeline counters\nparse_warning_count, discovered]
    C --> J[Pipeline counters\nby_entity_type, misc_count,\nlow_conf_count, conflict_count,\nskipped_unchanged_count]
    I --> K[report object]
    J --> K
    K --> L[classification_report_*.json]
    C --> ST[classification_state.db\nlast_revid/content_hash/strategy_version]
```
