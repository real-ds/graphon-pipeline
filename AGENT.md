# AGENT.md — Instructions for AI Coding Agents

You are acting as a senior backend/data engineer completing the GraphOne AI Engineer
take-home assessment (see `docs/ASSESSMENT_BRIEF.md` for the verbatim brief). This
file tells you how to work in this repo: priorities, constraints, and guardrails.

## Non-negotiable constraints (read this first)

1. **Never fabricate data.** Every `Startup`, `Product`, `ResearchPaper`, `Job`, or
   `News` record MUST carry a real `source.url` that was actually fetched. If an LLM
   extraction can't confidently fill a field, leave it `null` — do not guess. The
   brief states hallucinated data is grounds for disqualification; treat that as a
   hard test-suite-level rule, not a style preference.
2. **Freshness is a hard filter, not a display flag.** News/jobs older than 24 hours
   must be dropped before storage, not stored-then-filtered-at-read-time.
3. **Schema is the contract.** Don't add ad-hoc fields to a record without updating
   the corresponding Pydantic model in `src/schemas/` first. Downstream (Sheets
   export, entity resolution) trusts the schema.
4. **Idempotency.** Every scraper must go through `freshness.dedup_tracker` before a
   record is written. Re-running any pipeline phase twice must never double-count.
5. **Scale by config, not by rewrite.** Concurrency limits, worker counts, and source
   lists belong in `src/config.py` / `.env`, not hardcoded inside scraper logic.

## Priority order (do these in sequence)

The assessment weights evaluation as: LLM Orchestration 25%, Data Quality 25%, Scale
Thinking 20%, Engineering Rigor 20%, Entity Resolution 10%. Build in this order:

1. `src/schemas/*` — lock the schemas first (already scaffolded — extend, don't
   restructure, unless you find a real gap).
2. `src/llm/orchestrator.py` + `src/llm/chunking.py` — the fallback chain and 413/429
   handling is the single highest-weighted item. Get this rock-solid before wiring
   more scrapers to it.
3. `src/freshness/date_normalizer.py` + `dedup_tracker.py` — required correctness
   before Phase II can claim "24h fresh."
4. `src/scrapers/arxiv_scraper.py` and `paperswithcode_scraper.py` — arxiv has a
   free, no-auth API (`http://export.arxiv.org/api/query`); use it instead of
   scraping HTML wherever possible. This is your fastest path to 1,000 real
   research-paper records with zero anti-bot risk.
5. `src/entity_resolution/resolver.py` — extend `data/seed/canonical_entities.json`
   to 50 real AI startups before relying on it.
6. `src/scrapers/news_scraper.py`, `jobs_scraper.py`, `antibot.py` — these need
   per-target inspection; pick 5 news sources and 5 job boards that don't need heavy
   JS rendering first, then spend remaining anti-bot effort on 1–2 high-value
   JS-heavy targets to demonstrate the technique (per Phase V, this can be
   *documented* rather than fully implemented for every source).
7. `src/storage/sheets_exporter.py` — wire real Google Sheets API credentials last;
   until then, `src/storage/db.py` (SQLite) is the source of truth you develop against.

## Working conventions

- Python 3.11+, fully async (`asyncio` + `aiohttp`; `playwright.async_api` for
  JS-rendered/anti-bot targets). Do not introduce sync `requests` calls into the hot
  path — it will bottleneck the concurrency story that Phase I/V is scored on.
- All logging via `src/logger.py` (structlog-style, JSON-capable) — no bare `print`.
- All outbound HTTP calls go through `src/scrapers/rate_limiter.py` and
  `src/utils/retry.py` — don't hand-roll retry loops per scraper.
- Every new module gets a matching test in `tests/` for its pure-logic parts
  (schema validation, entity resolution, date parsing, chunking math). You don't need
  to test live network calls — mock them.
- Keep `docs/architecture.md` in sync with reality; it's a graded deliverable
  (Phase VI, max 3 pages) — don't let it drift into aspirational fiction.

## When you hit ambiguity

The brief explicitly rewards "figure it out, decide, document the decision" over
"wait for clarification." Default behavior:

- Ambiguous schema field → make the smallest reasonable choice, note it in
  `docs/DECISIONS.md`, move on.
- A target site is fully Cloudflare/Datadome-blocked and not worth the time → document
  the attempted approach and why you deprioritized it in `docs/architecture.md` §2,
  and spend the time on a source that's actually reachable. Partial-but-honest beats
  stalled-and-silent.
- Rate limit or quota exhausted on one LLM provider mid-run → fall through the chain
  automatically (that's the point of `orchestrator.py`); don't stop the pipeline.

## Skills available to you

See `.claude/skills/` for domain playbooks on: multi-tier LLM fallback design,
anti-bot scraping strategy, and entity resolution/deduplication. Read the relevant
one before implementing that phase.
