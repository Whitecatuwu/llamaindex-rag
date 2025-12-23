from llama_index.core import VectorStoreIndex
from llama_index.core import StorageContext
from ingestion.loader import load_documents
from ingestion.splitter import build_nodes
import config.settings  # noqa: F401


def main():
    docs = load_documents()
    nodes = build_nodes(docs)

    index = VectorStoreIndex(nodes)
    index.storage_context.persist(persist_dir="indexes/vector_store")

    print("✅ Index built and saved.")


if __name__ == "__main__":
    main()
