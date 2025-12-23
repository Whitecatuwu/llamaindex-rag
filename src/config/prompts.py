from llama_index.core.prompts import PromptTemplate

QA_PROMPT = PromptTemplate(
    """請僅根據下列證據回答問題，不得使用任何外部或背景知識。

證據：
{context_str}

問題：
{query_str}

回答規則：
- 條列回答
- 每點需能對應到證據
"""
)
