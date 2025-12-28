from llama_index.core import VectorStoreIndex
from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import JSONNodeParser

import src.config.settings  # noqa: F401


def main():
    docs = SimpleDirectoryReader("data/raw/wiki/cats").load_data()

    parser = JSONNodeParser()
    nodes = parser.get_nodes_from_documents(docs)

    index = VectorStoreIndex(nodes)
    index.storage_context.persist(persist_dir="indexes/vector_store")

    print("✅ Index built and saved.")


if __name__ == "__main__":
    main()
