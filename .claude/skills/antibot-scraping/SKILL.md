---
name: antibot-scraping
description: Use when implementing or modifying src/scrapers/*.py, particularly antibot.py — anything touching Cloudflare/Datadome-protected or heavily JS-rendered targets, or when deciding how to scale concurrency safely.
---

# Anti-Bot & Scale Scraping Strategy

## Tiering targets first (don't treat every source the same)
1. **Tier A — official API exists** (arxiv, many job boards via public/undocumented
   JSON endpoints): use it. Zero anti-bot risk, fastest to build, most reliable.
   Always check for this before writing an HTML scraper.
2. **Tier B — plain server-rendered HTML, no bot protection**: `aiohttp` + a real
   parser (`selectolax` or `bs4`). Cheapest to run at scale.
3. **Tier C — JS-rendered but not actively bot-blocking**: Playwright, but only
   render what you need (block images/fonts/analytics requests to cut load time).
4. **Tier D — Cloudflare/Datadome-protected**: highest cost, lowest reliability.
   Don't build your whole pipeline's throughput around these — isolate them behind
   the same `Scraper` interface so a slow/flaky Tier D source can't block Tier A/B/C
   throughput (separate worker pool / concurrency limit).

## Tier D technique notes (document what you tried, even if partial)
- Playwright with `playwright-stealth` patches, a real (not headless-default) user
  agent, and realistic viewport/timezone/locale reduces fingerprint-based blocks.
- Respect and rotate sane request pacing — bursts are what trips rate-based bot
  detection, not raw volume.
- Residential/rotating proxies are the standard production answer for IP-based
  blocking; for a take-home, it's fine to document this as the scale-time solution
  rather than fully implement paid proxy infra — say so explicitly in
  `docs/architecture.md` rather than silently skipping it.
- If a target actively serves a CAPTCHA challenge page, don't try to solve it
  programmatically for this assessment — log it as `blocked`, document the
  approach you'd take in production, and move budget to a reachable source. Time
  spent on a genuinely uncrackable Tier D target is time not spent hitting the
  1,000-record minimums, which are graded.

## Scaling concurrency safely
- Concurrency limit per *domain*, not just globally (`asyncio.Semaphore` keyed by
  host) — otherwise one slow source starves the others' fair share of workers.
- Backpressure: bound your queue size; a producer that outpaces the LLM extraction
  stage should block/slow down, not pile unbounded raw HTML in memory.
- The "500k without code changes" requirement means: source list, concurrency caps,
  and worker count must be config/env-driven, and the queue between
  scrape → extract → store stages must be a real queue (in-memory `asyncio.Queue`
  for the take-home; note in docs that this becomes Redis/SQS/Kafka at production
  scale) so stages scale independently.

## What "done" looks like
- Every scraper implements one `Scraper.fetch_batch(sources) -> list[RawDocument]`
  interface so Tier A–D sources are interchangeable to the pipeline orchestrator.
- `docs/architecture.md` names, for each of the 5 news sources and 5 job boards,
  which tier it falls in and why.
