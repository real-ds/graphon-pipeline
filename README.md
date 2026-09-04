# GraphOne / FrontierAtlas Intelligence Pipeline

A fault-tolerant, async data-intelligence pipeline that scrapes startups, products,
research papers, AI news, and AI jobs; extracts structured records via a multi-tier
LLM fallback chain; resolves entities to canonical form; and exports everything to
Google Sheets — built for the GraphOne AI Engineer take-home assessment.

## 1. What this repo contains

```
graphone-pipeline/
├── AGENT.md                 # instructions for AI coding agents (Claude Code, etc.)
├── docs/                    # all project + submission documents live here
├── src/                     # all source code
│   ├── schemas/             # pydantic models = the canonical JSON schema (source of truth)
│   ├── scrapers/            # Phase I & II: bulk + freshness scraping
│   ├── llm/                 # Phase III: multi-tier LLM extraction engine
│   ├── entity_resolution/   # Phase IV: canonicalization engine
│   ├── freshness/           # date normalization + dedup tracking
│   ├── storage/             # persistence + Google Sheets export
│   ├── pipeline/            # orchestration entrypoints
│   └── utils/               # retry/backoff, shared helpers
├── tests/                   # unit tests for the logic that must NOT silently break
├── data/                    # seed data + local scrape cache (git-ignored except seed/)
└── scripts/                 # one-off operational scripts (setup, sheets export)
```

## 2. Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # only needed for JS-rendered / anti-bot sources
cp .env.example .env                 # fill in your API keys
python -m src.pipeline.main --phase all
```

Run a single phase while developing:

```bash
python -m src.pipeline.main --phase papers      # arxiv + paperswithcode + github stars
python -m src.pipeline.main --phase startups
python -m src.pipeline.main --phase products
python -m src.pipeline.main --phase freshness   # news + jobs, 24h window
```

## 3. Architecture overview (see docs/architecture.md for the full write-up)

1. **Acquisition layer** (`src/scrapers/`) — async collectors (aiohttp for plain HTTP
   APIs/HTML, Playwright for JS-heavy/anti-bot targets) all emit a common
   `RawDocument { source, url, fetched_at, html_or_json, content_hash }` shape.
2. **Freshness gate** (`src/freshness/`) — every RawDocument is date-normalized and
   checked against a persistent dedup store (content hash + URL) before it's allowed
   further downstream. This is what guarantees "never process the same article twice."
3. **Extraction layer** (`src/llm/`) — RawDocuments that need structuring are chunked
   to fit context windows, then run through a provider fallback chain
   (Gemini Flash → Groq Llama 3 → DeepSeek) with retry/backoff on 429/413.
4. **Resolution layer** (`src/entity_resolution/`) — canonicalizes startup/product
   names against a seed list + fuzzy matching, logging every raw→canonical mapping.
5. **Storage layer** (`src/storage/`) — writes validated Pydantic records to
   SQLite/Postgres and exports to the 6-tab Google Sheet required by the brief.

## 4. Design principles baked into this scaffold

- **Schema-first**: every record is validated against a Pydantic model before it can
  reach storage — hallucinated/incomplete records fail loudly instead of polluting output.
- **Source traceability**: every record schema requires `source.url`; nothing is
  written without a real URL it can be traced back to (per the assessment's
  hallucination-disqualification warning).
- **Horizontal scale, not code changes**: acquisition is queue-driven (see
  `docs/architecture.md` §1) so going from 1k → 500k records is an infrastructure/worker-count
  change, not a code change.
- **Idempotent by construction**: the dedup store keys on `sha256(url + content)`, so
  re-running any phase is always safe.

## 5. What's implemented vs. stubbed

**Working implementations** (all phases run end-to-end):
- ✅ **Arxiv scraper** — Tier A API, 1000+ papers from `cs.AI`, `cs.LG`, `cs.CL`, `cs.CV`
- ✅ **PapersWithCode scraper** — Tier B HTML parsing, with `.co`/`.com` fallback
- ✅ **GitHub stars** — live repo metadata enrichment
- ✅ **News scraper** — 5 sources (HN Algolia, Dev.to, TechCrunch RSS, arXiv RSS, OpenAI Blog)
- ✅ **Jobs scraper** — 4 sources (Himalayas, RemoteOK, Remotive, Arbeitnow APIs)
- ✅ **Startup scraper** — GitHub topics (15 AI topics) + HuggingFace orgs
- ✅ **Product scraper** — Seed list (49 companies) + HuggingFace models (42 orgs)
- ✅ **24h freshness gate** — hard filter at ingestion time
- ✅ **LLM orchestrator** — Gemini 2.5 Flash → Groq GPT-OSS-20B → DeepSeek chain
- ✅ **Entity resolver** — 50-entity seed list + fuzzy matching, 2548+ mappings logged
- ✅ **SQLite storage** — `data/pipeline.db` with shared dedup store
- ✅ **CSV export** — `python scripts/export_to_csv.py`
- ✅ **Google Sheets export** — `python scripts/export_to_sheets.py` (requires GCP setup)

**Live model verification (2026-09-04):**
- `gemini-2.5-flash` — active
- `openai/gpt-oss-20b` — active
- `deepseek-chat` — active (credits required)

## 6. Verified output

| Record Type | Count | Source |
|---|---|---|
| Research Papers | 2000+ | arxiv.org (cs.AI, cs.LG, cs.CL, cs.CV) |
| Startups | 1200+ | GitHub topics + HF orgs + paper-derived |
| Products | 1300+ | Seed list + HuggingFace models |
| News (24h) | 340+ | HN Algolia + TechCrunch RSS + arXiv RSS + OpenAI |
| Jobs (24h) | 200+ | Arbeitnow + other APIs |
| Entity Mappings | 2500+ | Resolution log |

## 7. Docs

All submission-relevant documents live in `docs/` — see `docs/README.md` for the index.
