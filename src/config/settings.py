from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.huggingface import HuggingFaceLLM

Settings.embed_model = HuggingFaceEmbedding(model_name="Qwen/Qwen3-Embedding-0.6B")

Settings.llm = HuggingFaceLLM(
    model_name="Qwen/Qwen3-1.7B",
    tokenizer_name="Qwen/Qwen3-1.7B",
    context_window=4096,
)
