# Evaluation Checklist (self-check before submitting)

Weighted against the brief's own criteria — check each honestly.

## LLM Orchestration — 25%
- [ ] Fallback chain (Gemini → Groq → DeepSeek) actually falls through on
      real provider failures, not just in a mocked test.
- [ ] 429s trigger backoff + same-provider retry before falling through.
- [ ] 413s trigger chunking/truncation, not a bare failure.
- [ ] Schema-invalid LLM output is treated as a failure and retried on the
      next provider — not silently stored.

## Data Quality — 25%
- [ ] Every stored record has a real, working `source.url`.
- [ ] No LLM-invented values where source content didn't actually contain them
      (nulls are fine; guesses are not).
- [ ] Relative dates ("2 hours ago") normalize correctly relative to fetch time.
- [ ] News/Jobs are hard-filtered to the 24h window before storage.
- [ ] GitHub star counts are live-fetched, not hardcoded/estimated.

## Scale Thinking — 20%
- [ ] Source lists, concurrency limits, and provider chain are config/env-driven.
- [ ] Architecture doc explains the queue-based path from current scale to 500k+.
- [ ] Per-domain concurrency limiting prevents one source from starving others.

## Engineering Rigor — 20%
- [ ] Fully async (aiohttp/Playwright), no blocking sync calls in the hot path.
- [ ] Structured logging throughout — no bare `print`.
- [ ] Re-running any phase twice doesn't create duplicate records.
- [ ] Core logic (schemas, entity resolution, date parsing, chunking) has tests.

## Entity Resolution — 10%
- [ ] Seed list has ~50 real, verified canonical entities.
- [ ] "OpenAI" / "OpenAI, Inc." / "Open AI" style variants correctly collapse.
- [ ] Every resolution decision (not just merges) is logged to the Entity
      Mapping Log, including NO_MATCH cases.
- [ ] Fuzzy-match auto-merge threshold is conservative enough to avoid
      false-positive merges (precision over recall).

## Hard disqualifier check
- [ ] Zero hallucinated records — every field traces back to something actually
      present in the fetched source content.
