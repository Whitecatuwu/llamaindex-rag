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

CHOICE_SELECT_PROMPT = PromptTemplate(
    """
    You are an expert moderator for 'The Battle Cats' game wiki. 
Your task is to identify which of the following document excerpts are most relevant to the user's query.

Relevance Criteria for Battle Cats:
1. **Mechanics Matching**: If the query asks for "Anti-Red" or "Strong against Alien", prioritize units with those specific abilities (Massive Damage, Resistant, Freeze, etc.) against those traits.
2. **Form Specificity**: Note that units have Normal, Evolved, and True forms. A document is relevant if it matches the specific form mentioned (or the general unit if no form is specified).
3. **Stat Context**: If the user asks about "high DPS" or "tanky", prioritize documents that explicitly list stats or describe usage/strategy fitting that role.
4. **Exact Name Match**: Prioritize exact unit/enemy name matches over partial matches.

A list of documents is shown below. Each is numbered, starting at 1.

{context_str}

------------------------------------------------------------------------------------------------
Based on the criteria above, please rank the documents by relevance to the query: "{query_str}"

You must output ONLY the relevant document numbers and a relevance score (1-10), in the following format:
Doc 1: <score>
Doc 2: <score>
...

If no documents are relevant, answer with: "No relevant documents found."
"""
)
