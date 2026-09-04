"""Semantic-priority truncation so payloads never trigger 413s while keeping the
fields most likely to matter for extraction. See .claude/skills/llm-fallback-chain
for the design rationale.

Uses a cheap whitespace-token estimate (~4 chars/token) rather than a real
tokenizer to keep this dependency-free; swap in `tiktoken` if you need exactness
for a specific provider.
"""
from __future__ import annotations

import re

_BOILERPLATE_PATTERNS = [
    re.compile(r"<script.*?</script>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<style.*?</style>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<nav.*?</nav>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<footer.*?</footer>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<!--.*?-->", re.DOTALL),
]


def strip_boilerplate(html_or_text: str) -> str:
    text = html_or_text
    for pattern in _BOILERPLATE_PATTERNS:
        text = pattern.sub("", text)
    return text


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def truncate_to_budget(
    text: str,
    *,
    title: str = "",
    max_tokens: int,
    reserve_for_instructions: int = 300,
) -> str:
    """Priority order: title > first N paragraphs > rest. Truncates at a paragraph
    boundary where possible so we don't cut mid-sentence and confuse the LLM.
    """
    budget = max(200, max_tokens - reserve_for_instructions)
    cleaned = strip_boilerplate(text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]

    kept: list[str] = [title] if title else []
    used = estimate_tokens(title)
    for para in paragraphs:
        para_tokens = estimate_tokens(para)
        if used + para_tokens > budget:
            break
        kept.append(para)
        used += para_tokens

    if len(kept) <= (1 if title else 0):
        # Nothing fit at paragraph granularity (e.g. one giant paragraph) — hard
        # character-slice as a last resort, still leaving headroom.
        char_budget = budget * 4
        kept = [title, cleaned[:char_budget]] if title else [cleaned[:char_budget]]

    return "\n\n".join(kept)
