# GraphOne AI Intelligence Pipeline

> **A fault-tolerant, async, schema-first data pipeline that scrapes the open web
> for AI startups, products, research papers, jobs, and news — extracts
> structured records via a multi-tier LLM fallback chain, deduplicates and
> canonicalizes entities, and exports everything to a 6-tab Google Sheet.**
>
> **Built for the GraphOne AI Engineer Take-Home Assessment — 2026-09-04**

[![Tests](https://img.shields.io/badge/tests-24%2F24%20passing-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#license)
[![Sheet](https://img.shields.io/badge/live%20sheet-7%2C795%20records-4285F4)](https://docs.google.com/spreadsheets/d/1Cq2i_jZRCwHjJ6ooTukAgt0ydOqoa7DWi1c_Su_5ViY/edit?usp=sharing)

---

## 📊 Live Deliverable

**[Open the live Google Sheet →](https://docs.google.com/spreadsheets/d/1Cq2i_jZRCwHjJ6ooTukAgt0ydOqoa7DWi1c_Su_5ViY/edit?usp=sharing)**

| Tab | Records | Source(s) |
|---|--:|---|
| **Startups** | 1,237 | GitHub topics (15 AI categories) · HuggingFace orgs · paper-derived |
| **Products** | 1,312 | Seed list (49 companies) · HuggingFace models · 4 pricing tiers |
| **Research Papers** | 2,138 | arXiv API (`cs.AI`, `cs.LG`, `cs.CL`, `cs.CV`) · PapersWithCode · GitHub stars |
| **Jobs** | 211 | Arbeitnow · RemoteOK · Remotive · Himalayas (all 24h fresh) |
| **News** | 349 | HackerNews Algolia · TechCrunch RSS · arXiv RSS · OpenAI Blog · Dev.to (24h fresh) |
| **Entity Mapping Log** | 2,548 | Audit trail of every raw→canonical entity decision |
| **TOTAL** | **7,795** | — |

> **All tabs include schema-aligned column headers (row 1) with bold/freeze formatting.**

---

## 🎯 Why This Project Matters

The AI landscape moves hourly. By the time an analyst reads a "Top 100 AI Startups" list, half of those startups have pivoted, raised, or shut down. This pipeline automates the **discovery → structuring → dedup → canonicalization** loop that every serious AI intelligence team needs but few build right.

### What makes this implementation production-grade (not a toy scraper)

| Anti-Pattern | How This Pipeline Avoids It |
|---|---|
| **Hallucinated data** | Every record requires `source.url` — nothing enters storage without a traceable origin. |
| **Duplicate noise** | SHA-256 dedup on `url + content` is enforced at the freshness gate, before any LLM spend. |
| **Vendor lock-in** | 3-tier LLM fallback (Gemini Flash → Groq OSS → DeepSeek) with retry/backoff on 429/413. |
| **Schema drift** | Pydantic models are the *source of truth* — invalid records fail loudly, never reach the sheet. |
| **24h staleness** | Hard filter at ingestion: only records newer than 24h enter News/Jobs tabs. |
| **Entity fragmentation** | "Open AI" / "OpenAI" / "open ai" all resolve to one canonical name with method + confidence logged. |
| **One-shot scrapers** | Idempotent by construction — re-running any phase is safe and produces zero duplicates. |

### The "500k records" question

The architecture is queue-driven (`asyncio.Queue` per stage), with per-domain semaphores and global concurrency limits. Going from 7,795 → 500,000 records is an **infrastructure change** (swap in-process queue for Kafka/SQS, swap SQLite for Postgres), **not a code change**. See [`docs/architecture.md`](docs/architecture.md) §1 for the full scale analysis.

---

## 🧰 Tech Stack

### Core
| Layer | Library | Why |
|---|---|---|
| **Async I/O** | `aiohttp` 3.9+ | Native asyncio HTTP client, no thread-pool overhead |
| **JS rendering** | `playwright` 1.44+ | Only when anti-bot / JS-only sites are unavoidable |
| **HTML parsing** | `selectolax` 0.3+ | 5–10× faster than BeautifulSoup; C-extension under the hood |
| **Schema validation** | `pydantic` 2.7+ | Strict typing, HttpUrl/HttpUrl coercion, field validators |
| **ORM** | `SQLAlchemy` 2.0+ | Async + sync sessions, type-safe queries |
| **Date parsing** | `dateparser` 1.2+ | Handles "2 hours ago", ISO-8601, RFC-822, custom formats |
| **Fuzzy matching** | `rapidfuzz` 3.9+ | C++ Levenshtein/WRatio — 10× faster than fuzzywuzzy |

### LLM Providers (3-tier fallback chain)
| Priority | Provider | Model | Use Case |
|---|---|---|---|
| 1 (default) | **Google Gemini** | `gemini-2.5-flash` | Fast, cheap, large context |
| 2 (fallback on 429) | **Groq** | `openai/gpt-oss-20b` | Open-source, fast inference |
| 3 (fallback on 429/413) | **DeepSeek** | `deepseek-chat` | Reasoning model, deepest context |

### Storage & Export
| Component | Purpose |
|---|---|
| **SQLite** (`data/pipeline.db`) | Local persistence + dedup store |
| **Google Sheets API** (`gspread` + service account) | 6-tab output deliverable |
| **CSV** (`data/exports/*.csv`) | Portable backup, manual upload fallback |

### Tooling
- **Python 3.10+** (3.11 recommended for `asyncio` performance)
- **`pytest` + `pytest-asyncio`** — 24 unit tests covering freshness, dedup, entity resolution
- **`.env` + `python-dotenv`** — typed config via Pydantic Settings

---

## 🚀 Quickstart

### Prerequisites
- Python 3.10 or newer
- (Optional) Chromium for Playwright: `playwright install chromium`

### 1. Clone & install
```bash
git clone https://github.com/real-ds/graphon-pipeline.git
cd graphon-pipeline
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and fill in:
#   GEMINI_API_KEY=...         # required for LLM extraction
#   GROQ_API_KEY=...           # optional fallback
#   DEEPSEEK_API_KEY=...       # optional fallback
#   GITHUB_TOKEN=...           # for GitHub stars enrichment
#   GOOGLE_SERVICE_ACCOUNT_JSON=./credentials/oauth_client.json
#   GOOGLE_SHEETS_ID=...       # see "Google Sheets setup" below
```

### 3. Run the full pipeline
```bash
python -m src.pipeline.main --phase all
```

This runs in order:
1. **Papers** (arxiv + paperswithcode + GitHub stars)
2. **Startups** (GitHub topics + HF orgs)
3. **Products** (seed list + HF models)
4. **Freshness** (News 24h + Jobs 24h)

### 4. Run a single phase
```bash
python -m src.pipeline.main --phase papers
python -m src.pipeline.main --phase startups
python -m src.pipeline.main --phase products
python -m src.pipeline.main --phase freshness
```

### 5. Export to Google Sheets
```bash
python scripts/export_to_sheets.py
```
This reads the SQLite DB and writes all 6 tabs to the configured Google Sheet,
with schema-aligned column headers in row 1 (bold, frozen).

---

## 📁 Google Sheets Setup (one-time)

The pipeline ships with a service account JSON at `credentials/oauth_client.json`.
A Google Sheet must be created and shared with that account.

**1. Create the sheet**
- Go to [sheets.google.com](https://sheets.google.com) → click **"Blank"**
- Name it `GRAPHONE-PIPELINE`
- Copy the **Sheet ID** from the URL (the long string between `/d/` and `/edit`)

**2. Share with the service account**
- In the sheet, click **Share**
- Add this email (Editor access):
  ```
  graphone-sheets@my-projects-auth-504106.iam.gserviceaccount.com
  ```
- Click **Share** → **"Anyone with the link"** → **"Viewer"**

**3. Configure `.env`**
```bash
GOOGLE_SHEETS_ID=your_sheet_id_here
```

**4. Run the export**
```bash
python scripts/export_to_sheets.py
```

> 📝 **Fallback**: If you can't set up GCP, use the CSV export instead:
> `python scripts/export_to_csv.py` produces 6 CSVs in `data/exports/`
> that can be manually uploaded as 6 tabs.

---

## 🏗️ Architecture

```
┌─────────────┐   ┌──────────────┐   ┌────────────┐   ┌────────────┐   ┌──────────┐
│  SCRAPE     │──▶│ FRESHNESS    │──▶│  EXTRACT   │──▶│  RESOLVE   │──▶│  STORE   │
│ (async I/O) │   │ GATE (24h)   │   │  (LLM)     │   │  (entity)  │   │ (SQLite) │
└─────────────┘   └──────────────┘   └────────────┘   └────────────┘   └──────────┘
   aiohttp          dedup store        Gemini→Groq       seed list +      Pydantic
   Playwright       (sha256)           →DeepSeek         fuzzy match      validation
```

### 5 stages
1. **Acquisition** (`src/scrapers/`) — async collectors (aiohttp + Playwright) emit a common `RawDocument { source, url, fetched_at, content_hash }` shape.
2. **Freshness gate** (`src/freshness/`) — date-normalizes each document and filters by 24h window for News/Jobs. Dedup store (sha256 of url+content) prevents reprocessing.
3. **Extraction** (`src/llm/`) — chunks RawDocuments for context windows, runs them through a 3-tier LLM fallback chain with retry/backoff on 429/413.
4. **Resolution** (`src/entity_resolution/`) — canonicalizes startup/product names against a 50-entity seed list + fuzzy matching, logging every decision.
5. **Storage** (`src/storage/`) — validates against Pydantic schemas, writes to SQLite, exports to the 6-tab Google Sheet.

See [`docs/architecture.md`](docs/architecture.md) for the production-scale writeup.

---

## 📂 Project Structure

```
graphone-pipeline/
├── AGENT.md                     # AI agent instructions (Claude Code etc.)
├── README.md                    # ← you are here
├── requirements.txt
├── .env.example
│
├── docs/                        # all submission + design docs
│   ├── architecture.md          # production-scale design writeup
│   ├── DECISIONS.md             # why each library / model was chosen
│   ├── SCHEMA.md                # human-readable schema mirror
│   ├── GOOGLE_SHEETS_OPTIONS.md # CSV-upload / OAuth2 / service-account paths
│   └── README.md                # docs index
│
├── src/                         # all source code
│   ├── schemas/                 # Pydantic models = source of truth
│   │   ├── base.py              # BaseRecord (schemaVersion, source, collectedAt)
│   │   ├── startup.py
│   │   ├── product.py
│   │   ├── research_paper.py
│   │   ├── job.py
│   │   ├── news.py
│   │   └── entity_mapping.py
│   ├── scrapers/                # Phase I & II
│   ├── llm/                     # Phase III: orchestrator, chunking, providers
│   ├── entity_resolution/       # Phase IV: canonicalization engine
│   ├── freshness/               # date parsing + dedup store
│   ├── storage/                 # db, models, sheets export
│   ├── pipeline/                # orchestration entrypoints
│   ├── config.py                # Pydantic Settings
│   └── logger.py
│
├── tests/                       # 24 unit tests
├── data/
│   ├── seed/                    # 50-entity canonical list
│   ├── exports/                 # CSV backups of all 6 tabs
│   └── pipeline.db              # SQLite (git-ignored)
├── credentials/
│   └── oauth_client.json        # service account (git-ignored)
└── scripts/
    ├── export_to_sheets.py      # Google Sheets export
    └── export_to_csv.py         # CSV export fallback
```

---

## 🧪 Tests

```bash
python -m pytest
```
```
24 passed in ~10s
```

Coverage:
- Schema validation (all 6 record types)
- 24h freshness gate behavior
- Dedup store idempotency
- Entity resolver (EXACT / ALIAS / FUZZY / NO_MATCH paths)
- LLM chunker boundary handling
- Date parser normalization

---

## 📤 Deliverables Summary

| Deliverable | Status | Location |
|---|:---:|---|
| GitHub repo (pushed) | ✅ | https://github.com/real-ds/graphon-pipeline |
| Google Sheet (live, public) | ✅ | [Link](https://docs.google.com/spreadsheets/d/1Cq2i_jZRCwHjJ6ooTukAgt0ydOqoa7DWi1c_Su_5ViY/edit?usp=sharing) |
| CSV exports (6 files) | ✅ | `data/exports/*.csv` |
| Architecture writeup | ✅ | [`docs/architecture.md`](docs/architecture.md) |
| Decisions log | ✅ | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| Schema reference | ✅ | [`docs/SCHEMA.md`](docs/SCHEMA.md) |
| Unit tests | ✅ 24/24 | `tests/` |
| Service account JSON | ✅ | `credentials/oauth_client.json` (git-ignored) |

---

## ⚠️ Known Limitations (documented in DECISIONS.md)

- **arXiv categories** are limited to `cs.AI`, `cs.LG`, `cs.CL`, `cs.CV` (per the brief's AI focus)
- **Y Combinator jobs** are blocked by Cloudflare (not in this run)
- **DeepSeek** requires credits on the provided key (Gemini + Groq are sufficient)
- **VentureBeat news** returns HTTP 429 (skipped)
- **Service account** has the org policy `iam.disableServiceAccountCreation` enabled, so the included JSON must be reused; new service accounts cannot be created in this GCP project

---

## 📄 License

MIT — see `LICENSE` for details.

## 🙏 Acknowledgments

- arXiv for open paper metadata
- GitHub Topics API for AI startup discovery
- HuggingFace for org/model listings
- HackerNews Algolia for clean HN search API
- PapersWithCode for paper↔code linking
