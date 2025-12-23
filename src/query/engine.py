from llama_index.core import StorageContext, load_index_from_storage
from llama_index.core.query_engine import RetrieverQueryEngine

from retrieval.retriever import build_retriever
from query.synthesizer import build_synthesizer
import config.settings


def build_query_engine():
    storage = StorageContext.from_defaults(persist_dir="indexes/vector_store")
    index = load_index_from_storage(storage)

    synthesizer = build_synthesizer()

    retriever = build_retriever(index)

    return RetrieverQueryEngine(
        retriever=retriever,
        response_synthesizer=synthesizer,
    )
