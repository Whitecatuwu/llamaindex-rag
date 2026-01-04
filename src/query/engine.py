from llama_index.core import StorageContext, load_index_from_storage
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.postprocessor import LLMRerank

import src.config.settings
from src.config.prompts import QA_PROMPT, CHOICE_SELECT_PROMPT


def build_query_engine():
    storage = StorageContext.from_defaults(persist_dir="indexes/vector_store")
    index = load_index_from_storage(storage)

    synthesizer = get_response_synthesizer(
        response_mode="compact",
        text_qa_template=QA_PROMPT,
    )

    retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=10,
    )

    reranker = LLMRerank(
        # choice_select_prompt=CHOICE_SELECT_PROMPT,
        choice_batch_size=5,  # Rank 5 documents at a time (to fit context window)
        top_n=3,
    )

    return RetrieverQueryEngine(
        retriever=retriever,
        response_synthesizer=synthesizer,
        node_postprocessors=[reranker],
    )
