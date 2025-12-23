from llama_index.core.retrievers import VectorIndexRetriever


def build_retriever(index, top_k: int = 4):
    return VectorIndexRetriever(
        index=index,
        similarity_top_k=top_k,
    )
