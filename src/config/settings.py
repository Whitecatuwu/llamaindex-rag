# 嵌入模型和LLM的配置文件

from llama_index.llms.openrouter import OpenRouter
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.huggingface import HuggingFaceLLM

from dotenv import load_dotenv
import os

load_dotenv()

os.environ["OPENROUTER_API_KEY"] = os.getenv("OPENROUTER_API_KEY")

# 嵌入模型
Settings.embed_model = HuggingFaceEmbedding(
    model_name="Qwen/Qwen3-Embedding-0.6B", device="cuda"
)

# LLM模型
"""Settings.llm = HuggingFaceLLM(
    model_name="Qwen/Qwen3-1.7B",
    tokenizer_name="Qwen/Qwen3-1.7B",
    context_window=4096,
)"""

Settings.llm = OpenRouter(
    model="xiaomi/mimo-v2-flash:free",
    temperature=0.2,
    max_tokens=2048,
)
