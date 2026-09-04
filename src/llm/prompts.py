"""Prompt templates for structured extraction. Kept separate from orchestrator.py
so prompt iteration doesn't touch control-flow code.
"""

EXTRACTION_SYSTEM_PREAMBLE = """You are a precise data-extraction engine. You will be
given raw web content and a JSON schema. Extract ONLY information that is explicitly
present in the content. If a field is not present or you are not confident, output
null for that field — never guess or invent values. Output ONLY valid JSON matching
the schema, with no markdown fences and no commentary."""


def build_extraction_prompt(*, schema_json: str, content: str) -> str:
    return (
        f"{EXTRACTION_SYSTEM_PREAMBLE}\n\n"
        f"JSON schema:\n{schema_json}\n\n"
        f"Content:\n{content}\n\n"
        f"JSON output:"
    )
