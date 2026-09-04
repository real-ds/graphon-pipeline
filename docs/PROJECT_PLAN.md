# Project Plan — 3-Day Trial

Scoring weights to optimize against: **LLM Orchestration 25% · Data Quality 25% ·
Scale Thinking 20% · Engineering Rigor 20% · Entity Resolution 10%**. Build in the
order below — it front-loads the highest-weighted, highest-risk items.

## Day 1 — Foundation + highest-risk pieces first

- [ ] Confirm schemas (`src/schemas/`) match the brief exactly; extend if you find
      a real gap (don't restructure without reason).
- [ ] Build and unit-test the LLM orchestrator fallback chain
      (`src/llm/orchestrator.py`) against a mock provider first — prove the
      429/413 handling logic works before spending real API quota on it.
- [ ] Build and unit-test `freshness/date_normalizer.py` against a table of real
      example date strings pulled from your actual target sites (relative dates,
      missing dates, various formats).
- [ ] Get the arxiv research-papers phase running end-to-end
      (`python -m src.pipeline.main --phase papers`) — this is your fastest,
      lowest-risk path to a real 1,000-record output.
- [ ] Extend `data/seed/canonical_entities.json` to the full ~50 entries with
      real, verified AI startups (the scaffold ships ~50 already — review and
      adjust based on what you actually encounter while scraping).

## Day 2 — Breadth: startups, products, news, jobs

- [ ] Pick 2–3 startup/product directory sources reachable without heavy
      anti-bot work; implement scrapers for them (Tier A/B first).
- [ ] Wire scraped raw content through the LLM orchestrator to produce
      Startup/Product records; run every extracted name through
      `EntityResolver` before storage.
- [ ] Implement the 5 news sources and 5 job boards
      (`news_scraper.py` / `jobs_scraper.py`) — prefer RSS/JSON feeds over HTML
      parsing where available (check each board/source for one first).
- [ ] Apply the 24-hour freshness gate before storage, not after — verify with
      a manual spot-check that nothing older than 24h landed in the DB.
- [ ] Attempt 1–2 Cloudflare/Datadome-protected high-value sources with
      `AntiBotScraper` to demonstrate the technique (Phase V). If a target is
      genuinely uncrackable in the time budget, document the attempt and
      reasoning in `architecture.md` §2 instead of stalling on it.

## Day 3 — Scale story, polish, submission

- [ ] Write `architecture.md` (max 3 pages) answering the 4 required questions —
      do this from what you actually built, not aspirationally.
- [ ] Run the full pipeline once clean (`--phase all`) and check row counts
      against the minimums (1,000 startups / products / papers; all fresh
      jobs+news found).
- [ ] Export to Google Sheets (`scripts/export_to_sheets.py`) and verify all 6
      tabs render correctly and are publicly viewable.
- [ ] Fill in `docs/DECISIONS.md` with the judgment calls you made under
      ambiguity — this is explicitly rewarded per the brief's tone.
- [ ] Run through `docs/EVALUATION_CHECKLIST.md` and `docs/SUBMISSION_CHECKLIST.md`
      before submitting both links.
