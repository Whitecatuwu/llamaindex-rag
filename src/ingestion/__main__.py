from src.ingestion.crawl import run_crawl

# python -m src.ingestion
if __name__ == "__main__":
    summary = run_crawl()
    print(summary)
