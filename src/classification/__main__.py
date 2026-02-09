from src.classification.classify import run_classify

# python -m src.classification
if __name__ == "__main__":
    result = run_classify(
        enable_classification=True,
        source_mode="html",
        input_dir="artifacts/raw/wiki/page",
        db_path="artifacts/raw/wiki/wiki_registry.db",
        output_labels_path="artifacts/classified/page_labels_ingestion.jsonl",
        output_report_path="artifacts/classified/classification_report_ingestion.json",
        output_review_path="artifacts/classified/review_queue_ingestion.jsonl",
        classified_output_root="artifacts/classified/wiki",
        incremental=True,
        full_rebuild=False,
        state_db_path="artifacts/classified/classification_state.db",
        low_confidence_threshold=0.5,
        include_redirects=True,
    )
    print(result)
