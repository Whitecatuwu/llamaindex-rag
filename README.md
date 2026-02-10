# llamaindex-rag

## Setup

```bash
pip install -r requirements.txt
```

## Ingestion

```bash
python -m src.ingestion
```

Programmatic usage:

```python
from src.ingestion.crawl import run_crawl

summary = run_crawl(show_progress=True)
summary_no_bar = run_crawl(show_progress=False)
```

## Classification

```bash
python -m src.classification
```

Programmatic usage:

```python
from src.classification.classify import run_classify

result = run_classify(enable_classification=True, show_progress=True)
result_no_bar = run_classify(enable_classification=True, show_progress=False)
```

## Query

```bash
python -m src.app
```
