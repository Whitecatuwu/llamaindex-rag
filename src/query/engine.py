from llama_index.core import StorageContext, load_index_from_storage
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.core.retrievers import VectorIndexRetriever

import src.config.settings
from src.config.prompts import QA_PROMPT


def build_query_engine():
    storage = StorageContext.from_defaults(persist_dir="indexes/vector_store")
    index = load_index_from_storage(storage)

    synthesizer = get_response_synthesizer(
        response_mode="compact",
        text_qa_template=QA_PROMPT,
    )

    retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=5,
    )

    return RetrieverQueryEngine(
        retriever=retriever,
        response_synthesizer=synthesizer,
    )
