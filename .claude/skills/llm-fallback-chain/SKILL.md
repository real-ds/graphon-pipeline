---
name: llm-fallback-chain
description: Use when implementing or modifying src/llm/orchestrator.py, chunking.py, or providers.py — anything handling multi-provider LLM extraction, 429 rate limits, or 413 payload errors.
---

# Multi-Tier LLM Fallback Chain

## Goal
Turn raw HTML/text into schema-valid JSON using an ordered chain of LLM providers,
never failing a document just because one provider is down or rate-limited.

## Chain design
- Order providers cheapest/fastest → most reliable-but-slower:
  `Gemini Flash → Groq (Llama 3) → DeepSeek`. Each provider is a class implementing
  the same `LLMProvider.extract(prompt, schema) -> dict` interface so swapping order
  or adding a provider is a one-line config change, not a rewrite.
- On any exception, classify it: `RateLimitError` (429), `PayloadTooLargeError` (413),
  `ProviderError` (5xx/timeout), `ValidationError` (response didn't match schema).
  Route each differently (see below) instead of a blanket "try next provider."

## 429 handling (rate limits)
- Exponential backoff with full jitter: `sleep = random(0, min(cap, base * 2**attempt))`.
- Retry the SAME provider up to N times before falling through to the next provider —
  falling through immediately on a transient 429 wastes your best/cheapest provider's
  capacity for no reason.
- Track a per-provider token bucket locally so you throttle before the provider does.

## 413 handling (payload too large / context overflow)
- Never truncate blindly at a character count. Chunk semantically:
  1. Strip boilerplate (nav, footer, ads) before counting tokens.
  2. If still over budget, prioritize: title/headline > byline/date > first N
     paragraphs > rest. For research papers, abstract > body.
  3. Re-estimate tokens after each cut; only send what fits with margin for the
     completion + schema instructions.
- Log the original vs. truncated size so you can tell during grading/debugging
  whether truncation is losing the fields you need.

## Validation loop
- Always validate the provider's JSON output against the target Pydantic schema
  before accepting it. A schema-invalid response is NOT a successful extraction —
  route it through the fallback chain too, don't silently store partial garbage.
- Cap total attempts across the whole chain (e.g. 3 providers × 2 retries = 6 max)
  and mark the document `extraction_failed` rather than looping forever.

## What "done" looks like
- A single `orchestrator.extract(raw_document, target_schema)` call that internally
  handles provider order, backoff, chunking, and validation, returning either a
  valid schema instance or a typed failure you can log and skip.
