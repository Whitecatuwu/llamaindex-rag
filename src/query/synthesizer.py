from llama_index.core.response_synthesizers import get_response_synthesizer
from config.prompts import QA_PROMPT


def build_synthesizer():
    return get_response_synthesizer(
        response_mode="compact",
        text_qa_template=QA_PROMPT,
    )
