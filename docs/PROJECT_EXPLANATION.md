# Project Explanation

> **Written for: anyone joining this project or curious about how it works.**
> **Tone: conversational, no jargon unexplained, every term defined on first use.**
> **Goal: by the end of this doc, you should be able to explain this pipeline to a friend over coffee.**

---

## Table of Contents

1. [What does this project do? (The Big Idea)](#1-what-does-this-project-do-the-big-idea)
2. [The Problem We Are Solving](#2-the-problem-we-are-solving)
3. [The Big Picture — 5-Step Data Pipeline](#3-the-big-picture--5-step-data-pipeline)
4. [Step 1: Scraping — Collecting Raw Data](#4-step-1-scraping--collecting-raw-data)
5. [Step 2: Freshness Gate — Cleaning the Data](#5-step-2-freshness-gate--cleaning-the-data)
6. [Step 3: LLM Extraction — Reading the Data](#6-step-3-llm-extraction--reading-the-data)
7. [Step 4: Entity Resolution — Making Sense of Names](#7-step-4-entity-resolution--making-sense-of-names)
8. [Step 5: Storage — Saving Everything](#8-step-5-storage--saving-everything)
9. [The Database — What Gets Stored](#9-the-database--what-gets-stored)
10. [The Google Sheet Output](#10-the-google-sheet-output)
11. [How to Run the Pipeline](#11-how-to-run-the-pipeline)
12. [Glossary of Terms](#12-glossary-of-terms)

---

## 1. What Does This Project Do? (The Big Idea)

Imagine you want to know **every AI startup, product, research paper, job, and news story** that exists on the internet — all in one place, all properly organized, all verified. That's exactly what this pipeline does.

You run it, and it:

```
Internet → Scrapes AI websites → Cleans & organizes data → Saves to a Google Sheet
```

The result is a spreadsheet with **7,795 rows of clean, organized AI intelligence data** across 6 tabs:
- 🏢 1,237 AI Startups
- 🛍️ 1,312 AI Products
- 📄 2,138 Research Papers
- 💼 211 AI Jobs (from the last 24 hours)
- 📰 349 AI News articles (from the last 24 hours)
- 🔗 2,548 Entity Mappings (a log of name-cleanup decisions)

---

## 2. The Problem We Are Solving

Before we explain *how* the pipeline works, let's understand *why* it exists.

### The Internet Is Messy

When you look at AI news online, you see things like:

| What the website says | What it really means |
|---|---|
| "Open AI" | The company called "OpenAI" |
| "openai.com/blog" | The source is openai.com |
| "posted 2 hours ago" | Today's date |
| "posted 3 days ago" | 3 days ago → filtered out |
| "Stanford NLP Group" | The same group as "Stanford NLP Lab" |

The raw internet is full of inconsistencies, duplicates, old data, and ambiguous names. **This pipeline cleans all of that up automatically.**

### Why Not Just Download a List?

- Lists go stale within hours
- No single list covers startups + products + papers + jobs + news simultaneously
- Most lists contain duplicates (the same startup listed under different names)
- "AI" is a moving target — you need fresh data, not old archives

This pipeline solves all four problems by running on-demand and staying fresh.

---

## 3. The Big Picture — 5-Step Data Pipeline

Think of data flowing through a factory assembly line. Each station does one specific job, then passes the result to the next station.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          THE GRAPHONE PIPELINE                              │
│                                                                             │
│  ┌──────────┐    ┌──────────────┐    ┌────────────┐    ┌────────────┐    ┌──────────┐
│  │  STEP 1  │    │   STEP 2     │    │  STEP 3    │    │  STEP 4    │    │ STEP 5   │
│  │          │    │              │    │            │    │            │    │          │
│  │ SCRAPING │ ──▶│  FRESHNESS   │ ──▶│    LLM     │ ──▶│  ENTITY    │ ──▶│  STORE   │
│  │          │    │     GATE     │    │  EXTRACTION│    │ RESOLUTION │    │          │
│  │          │    │              │    │            │    │            │    │          │
│  │  18 web  │    │ 24h filter  │    │ Gemini →   │    │ Canonical  │    │ SQLite   │
│  │  sources │    │ + Dedup      │    │ Groq →     │    │  names     │    │ + Sheets │
│  │          │    │              │    │ DeepSeek   │    │ + confidence│   │          │
│  └──────────┘    └──────────────┘    └────────────┘    └────────────┘    └──────────┘
│       │                │                   │                │                │
│       ▼                ▼                   ▼                ▼                ▼
│   Raw web          Clean,             Structured        Resolved         Final
│   pages, APIs      de-duped           JSON records      entity names     output
│   JSON/RSS/HTML    documents          (with schema)     logged           saved
└─────────────────────────────────────────────────────────────────────────────┘
```

### What each step does (one sentence each):

| Step | Name | What it does | Analogy |
|---|---|---|---|
| **1** | Scraper | Downloads raw data from 18 different websites | A librarian who visits 18 libraries and copies every AI-related book title |
| **2** | Freshness Gate | Filters out old data and removes exact duplicates | A quality control inspector who throws away outdated books and duplicate copies |
| **3** | LLM Extraction | Reads the raw data and extracts key information | A smart reader who reads each book and writes a summary: "title, author, date, topic" |
| **4** | Entity Resolution | Cleans up messy names ("Open AI" → "OpenAI") | An editor who standardizes all names so "Open AI", "openai", and "Open AI Inc." all become "OpenAI" |
| **5** | Storage | Saves everything to SQLite + exports to Google Sheets | A filing clerk who puts each summary into a cabinet AND pastes them onto a shared whiteboard |

---

## 4. Step 1: Scraping — Collecting Raw Data

### What is scraping?

**Scraping** means writing a program that visits websites automatically and pulls out data — just like a human visiting a website and copy-pasting information, but done by code at scale.

### Where does the data come from?

We scrape **18 different sources** across 5 categories:

```
Research Papers
├── arXiv API            — academic paper database (MIT license, public API)
├── PapersWithCode.co   — papers with linked GitHub code repositories
└── GitHub API           — live star counts for repos linked in papers

AI Startups
├── GitHub Topics API    — repos tagged with "artificial-intelligence", "machine-learning", etc.
├── HuggingFace Orgs API — AI organizations listed on HuggingFace
└── Seed List           — 50 known AI companies we start with

AI Products
├── Seed List            — known AI products from known companies
├── HuggingFace Models   — AI models published by organizations
└── Wikipedia            — source URLs for company information

AI Jobs (24-hour freshness)
├── Arbeitnow API        — remote tech job board
├── RemoteOK API         — remote AI jobs
├── Remotive API         — remote software jobs
└── Himalayas API         — remote engineering jobs

AI News (24-hour freshness)
├── HackerNews Algolia    — HN search API filtered to "AI"
├── TechCrunch RSS       — tech news feed
├── Dev.to API           — developer articles tagged AI
├── arXiv RSS            — new AI papers (cross-listed as news)
└── OpenAI Blog RSS      — OpenAI official blog
```

### How does the scraper work?

```
┌─────────────────────────────────────────────────────┐
│                  SCRAPING WORKFLOW                   │
│                                                      │
│  For each source (e.g. arXiv API):                  │
│                                                      │
│  1. Send a request to the website API/URL           │
│     POST /api/query?search=AI&start=0               │
│                                                      │
│  2. Receive a response                               │
│     ◄── XML/JSON/HTML response                      │
│                                                      │
│  3. Parse the response                              │
│     Extract: title, authors, URL, date               │
│                                                      │
│  4. Convert to RawDocument format                   │
│     RawDocument {                                    │
│       source: "arxiv.org",                          │
│       url: "https://arxiv.org/abs/...",            │
│       content: "...",                               │
│       content_hash: "sha256(...)"                   │
│     }                                                │
│                                                      │
│  5. Add to the pipeline queue                       │
│     ▼ goes to Step 2: Freshness Gate                │
└─────────────────────────────────────────────────────┘
```

### What is a RawDocument?

It's the **uniform format** that every scraper produces, regardless of whether the source was an API (JSON), an RSS feed (XML), or a website (HTML). All downstream steps only know about `RawDocument` — they don't care where the data came from.

```python
class RawDocument:
    source: str          # "arxiv.org" — which website it came from
    url: str             # "https://arxiv.org/abs/..." — traceable link
    fetched_at: datetime # When we downloaded it
    content: str         # The raw text/XML/JSON content
    content_hash: str    # SHA-256 hash of url+content for dedup
```

### Key scraping features

| Feature | What it does |
|---|---|
| **Async I/O (aiohttp)** | Downloads from many websites simultaneously, not one after another |
| **Rate limiting** | Waits between requests to the same website so we don't get blocked |
| **Per-domain concurrency cap** | Max 5 requests to the same website at once (prevents being IP-banned) |
| **Global concurrency cap** | Max 50 total in-flight requests at once |
| **Error handling** | If one website fails, others keep going |

---

## 5. Step 2: Freshness Gate — Cleaning the Data

### The Two Jobs of the Freshness Gate

The Freshness Gate is the quality control station. It does two things:

```
┌─────────────────────────────────────────────────────────────┐
│                 FRESHNESS GATE — TWO FILTERS                │
│                                                              │
│  FILTER 1: DEDUPLICATION                                    │
│  ────────────────────────                                    │
│  Before:  [paper1, paper2, paper1 AGAIN, paper3]            │
│  After:   [paper1,        paper2,         paper3]            │
│                                                              │
│  How: We compute SHA-256(url + content). If we've seen       │
│  this hash before, it's a duplicate → skip it.               │
│                                                              │
│  FILTER 2: DATE FILTERING (News + Jobs only)                  │
│  ────────────────────────────────────────────                  │
│  Before:  [job_today, job_yesterday, job_3days_old]          │
│  After:   [job_today, job_yesterday,      ❌ filtered]      │
│                                                              │
│  How: Parse the "date" field of each news article or job     │
│  posting. If it's older than 24 hours, throw it away.       │
│                                                              │
│  Note: Papers, Startups, Products are NOT date-filtered.     │
│  An AI paper from 2019 is still valuable.                   │
└─────────────────────────────────────────────────────────────┘
```

### Why deduplication matters

Imagine you scrape HackerNews 3 times in one pipeline run. Without dedup, the same articles would appear 3 times. The `content_hash` (SHA-256) is computed from `url + content`, so:

- Same URL, different content → **different hash → kept**
- Same URL, same content → **same hash → skipped**
- Different URL, same content → **different hash → kept** (they might be mirrors)

### Why date filtering matters for News + Jobs

The brief specifies a "24-hour freshness window" for News and Jobs. This means:

- **News**: Only articles published in the last 24 hours appear in the sheet. Yesterday's news is dropped.
- **Jobs**: Only job postings from the last 24 hours appear. Old postings are dropped.

Research papers, startups, and products are **not date-filtered** — a paper from 2019 is just as valid as one from today.

### What does "date parsing" mean in practice?

Websites don't agree on date formats. The date parser handles all of these automatically:

| Website returns | Our parser understands it as |
|---|---|
| `"2026-09-04T10:29:50Z"` | ISO-8601 — easy |
| `"Fri, 04 Sep 2026 10:29:50 GMT"` | RFC-822 — common in RSS feeds |
| `"2 hours ago"` | Relative time — parsed with `dateparser` library |
| `"September 4, 2026"` | Human-readable — parsed with `dateparser` library |
| `"Sep 04 2026"` | Ambiguous (DD/MM or MM/DD?) — context resolved |

---

## 6. Step 3: LLM Extraction — Reading the Data

### What is an LLM?

**LLM** stands for **Large Language Model**. Think of it as an extremely well-read assistant that has seen billions of webpages, books, and articles. You can ask it to read a messy webpage and extract structured information from it.

In this pipeline, we use LLMs to read the raw scraped data and extract key fields.

### Example: Before and After LLM Extraction

**Before** (what the scraper gives us — raw text):
```
"Compile by Training: Turning Natural-Language Specifications
into Local Neural Functions
Authors: Yuntian Deng, Pengyu Nie, Stuart Shieber
Published: 2026-09-03
URL: http://arxiv.org/abs/2609.04199v1
GitHub: https://github.com/... (scraped from paper page)
Stars: (not on this page)"
```

**After** (what the LLM extracts — structured JSON):
```json
{
  "title": "Compile by Training: Turning Natural-Language Specifications into Local Neural Functions",
  "authors": ["Yuntian Deng", "Pengyu Nie", "Stuart Shieber"],
  "paper_url": "http://arxiv.org/abs/2609.04199v1",
  "github_url": "https://github.com/...",
  "github_stars": 142,
  "published_date": "2026-09-03T17:59:49Z"
}
```

The LLM reads the messy text and produces clean, typed fields.

### Why we use a fallback chain (not just one LLM)

We don't rely on a single LLM provider because:

| Problem | Solution |
|---|---|
| **API limit reached** (HTTP 429) | Switch to the next provider automatically |
| **Payload too large** (HTTP 413) | Split into smaller chunks and retry |
| **Provider down** | Fallback to the next one |
| **Rate limit hit** | Wait, then retry |

```
┌──────────────────────────────────────────────────────────┐
│              LLM FALLBACK CHAIN                          │
│                                                           │
│  1. Try Gemini (Google) — gemini-2.5-flash              │
│     ├── Success?  → Use the result ✅                    │
│     └── 429 or 413? → Try Groq next                     │
│                                                           │
│  2. Try Groq — openai/gpt-oss-20b                       │
│     ├── Success?  → Use the result ✅                    │
│     └── 429 or 413? → Try DeepSeek next                 │
│                                                           │
│  3. Try DeepSeek — deepseek-chat                        │
│     ├── Success?  → Use the result ✅                   │
│     └── Still fails? → Log error, skip this record ❌   │
│                                                           │
│  Each step waits incrementally longer (retry with        │
│  backoff: 2s → 4s → 8s → 16s → 32s)                    │
└──────────────────────────────────────────────────────────┘
```

### What is "chunking"?

LLMs can only read a certain amount of text at once (called the **context window**). If a source has 1,000 pages of data, we split them into chunks of ~50 pages each, process each chunk separately, then combine the results.

```
Large dataset: [page1, page2, page3, ... page1000]
                   │
                   ▼ Split into chunks of 50
         ┌─────────┴─────────┐
         │  Chunk 1          │ Chunk 2 ... Chunk 20
         │  [p1..p50]       │ [p51..p100]
         │       ↓           │       ↓
         │  LLM extraction   │  LLM extraction
         │       ↓           │       ↓
         │  Results 1-50    │  Results 51-100
         └─────────┬─────────┘
                   │ Combine all results
                   ▼
         [Result1, Result2, Result3 ... Result1000]
```

### What does the LLM actually do for each record type?

| Record Type | What the LLM extracts |
|---|---|
| **Research Paper** | title, authors, paper_url, github_url, github_stars, published_date |
| **Startup** | entityName, employeeCount (optional) |
| **Product** | startupName, pricingModel (FREE / FREEMIUM / PAID / ENTERPRISE) |
| **Job** | company, date, is_remote, role_family |
| **News** | headline, full_text, published_date, related_entity |

### The Pydantic validation step

After the LLM returns JSON, we validate it against a **Pydantic model** (a strict type schema). If any field is missing or has the wrong type, the record is **rejected** — it never reaches the database.

This is our anti-hallucination mechanism: the LLM might occasionally produce a fake field or miss a required one. Pydantic catches that and the record is retried or skipped.

---

## 7. Step 4: Entity Resolution — Making Sense of Names

### The problem with names

The internet is full of variations of the same name:

```
"Open AI"        ← some websites write it like this
"OpenAI"         ← the official name
"open ai"        ← lowercase
"Open AI Inc."   ← with legal suffix
"openai.com"     ← URL, not the name
```

If we treat all of these as different startups, we'd have 5 entries for the same company. The Entity Resolution step fixes this.

### How does it work? (3-tier approach)

```
┌──────────────────────────────────────────────────────────────┐
│              ENTITY RESOLUTION — 3-TIER APPROACH             │
│                                                               │
│  TIER 1: EXACT MATCH                                         │
│  ─────────────────────                                        │
│  Check if the name appears in our seed list exactly.          │
│                                                               │
│  "OpenAI" in seed_list?  → "OpenAI" ✅ EXACT                 │
│                                                               │
│  TIER 2: ALIAS MATCH                                          │
│  ────────────────────                                         │
│  The seed list has "known aliases" for each entity.           │
│                                                               │
│  Seed entry for OpenAI:                                       │
│    canonical: "OpenAI"                                        │
│    aliases: ["Open AI", "open ai", "OpenAI Inc"]             │
│                                                               │
│  "Open AI" in aliases?  → "OpenAI" ✅ ALIAS                   │
│                                                               │
│  TIER 3: FUZZY MATCH                                         │
│  ────────────────────                                         │
│  If no exact or alias match, use fuzzy string matching       │
│  (Levenshtein distance). Think: "how many keystrokes         │
│  to turn one string into another?"                           │
│                                                               │
│  "Open AI Lab" vs "OpenAI"                                   │
│  Similarity score: 82% → "OpenAI" ✅ FUZZY (0.82 confidence) │
│                                                               │
│  "Elon Musk Ventures" vs "OpenAI"                            │
│  Similarity score: 28% → No match ❌ NO_MATCH (0.0 conf)     │
└──────────────────────────────────────────────────────────────┘
```

### The Entity Mapping Log

Every single name-cleanup decision is logged to the **Entity Mapping Log**. This is an audit trail that shows:

```
┌──────────────────────────────────────────────────────────────┐
│           ENTITY MAPPING LOG (audit trail)                  │
│                                                              │
│  raw_name         │ canonical_name │ method    │ confidence  │
│  ─────────────────┼────────────────┼───────────┼────────────│
│  Open AI          │ OpenAI         │ ALIAS     │ 1.00       │
│  open ai          │ OpenAI         │ ALIAS     │ 1.00       │
│  Deep Seek        │ DeepSeek       │ FUZZY     │ 0.85       │
│  Stanford NLP Lab │ Stanford NLP   │ ALIAS     │ 1.00       │
│  obra             │ obra           │ NO_MATCH  │ 0.00       │
│  brightmart       │ brightmart     │ NO_MATCH  │ 0.00       │
└──────────────────────────────────────────────────────────────┘
```

This log has **2,548 entries** — one for every time the resolver made a decision.

---

## 8. Step 5: Storage — Saving Everything

### Where does the data go?

After all the cleaning and processing, data flows into two places:

```
Processed Records
       │
       ├──▶ SQLite Database (local file: data/pipeline.db)
       │        └── All 5,247 records + 2,548 entity mappings
       │
       └──▶ Google Sheets (6 tabs)
                ├── Startups      (1,237 rows)
                ├── Products     (1,312 rows)
                ├── Research     (2,138 rows)
                ├── Jobs         (  211 rows)
                ├── News         (  349 rows)
                └── Entity Map   (2,548 rows)
```

### SQLite Database

SQLite is a simple file-based database. Think of it as an Excel spreadsheet, but you can query it with code.

The database has two main tables:

**`records` table** — stores all the structured records:
| Column | What it contains |
|---|---|
| `id` | Auto-incrementing ID |
| `record_type` | STARTUP / PRODUCT / RESEARCH_PAPER / JOB / NEWS |
| `payload_json` | The full record as a JSON string |
| `content_hash` | SHA-256 for dedup |
| `created_at` | When it was stored |

**`entity_mappings` table** — stores all name-cleanup decisions:
| Column | What it contains |
|---|---|
| `id` | Auto-incrementing ID |
| `raw_name` | The name as it appeared on the web |
| `canonical_name` | The cleaned-up standard name |
| `method` | EXACT / ALIAS / FUZZY / NO_MATCH |
| `confidence` | 0.0 to 1.0 score |
| `resolved_at` | When the decision was made |

### Google Sheets Export

The Google Sheet is the **human-readable deliverable**. The export script reads the SQLite database and writes to Google Sheets using a service account.

Each tab has:
- **Row 1: Column headers** (bold, frozen so they stay visible when scrolling)
- **Row 2+: Data rows**

Example — Research Papers tab:
| schemaVersion | recordType | source.name | source.url | collectedAt | content.title | content.authors | content.paper_url | content.github_url | content.github_stars | content.published_date |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.0 | RESEARCH_PAPER | arxiv.org | ... | 2026-09-04T... | Compile by Training... | Yuntian Deng... | http://arxiv.org/... | https://github.com/... | 142 | 2026-09-03T... |

---

## 9. The Database — What Gets Stored

### The JSON record structure (by type)

Every record in the database is stored as JSON following a strict schema. Here is what each record type looks like:

**Research Paper:**
```json
{
  "schemaVersion": "1.0",
  "recordType": "RESEARCH_PAPER",
  "source": {
    "name": "arxiv.org",
    "url": "https://arxiv.org/abs/2609.04199v1"
  },
  "collectedAt": "2026-09-04T10:26:30Z",
  "content": {
    "title": "Compile by Training: Turning Natural-Language Specifications...",
    "authors": ["Yuntian Deng", "Pengyu Nie", "Stuart Shieber"],
    "paper_url": "http://arxiv.org/abs/2609.04199v1",
    "github_url": "https://github.com/...",
    "github_stars": 142,
    "published_date": "2026-09-03T17:59:49Z"
  }
}
```

**Startup:**
```json
{
  "schemaVersion": "1.0",
  "recordType": "STARTUP",
  "source": {
    "name": "github.com",
    "url": "https://github.com/openclaw/openclaw"
  },
  "collectedAt": "2026-09-04T10:26:30Z",
  "content": {
    "entityName": "openclaw",
    "data": {
      "employeeCount": null
    }
  }
}
```

**Product:**
```json
{
  "schemaVersion": "1.0",
  "recordType": "PRODUCT",
  "source": {
    "name": "seed",
    "url": "https://en.wikipedia.org/wiki/ChatGPT"
  },
  "collectedAt": "2026-09-04T10:34:08Z",
  "content": {
    "startupName": "OpenAI",
    "pricingModel": "FREEMIUM"
  }
}
```

**Job:**
```json
{
  "schemaVersion": "1.0",
  "recordType": "JOB",
  "source": {
    "name": "arbeitnow",
    "url": "https://www.arbeitnow.com/jobs/..."
  },
  "collectedAt": "2026-09-04T10:23:00Z",
  "content": {
    "company": "vay",
    "date": "2026-09-04T08:55:13Z",
    "is_remote": false,
    "role_family": "Engineering"
  }
}
```

**News:**
```json
{
  "schemaVersion": "1.0",
  "recordType": "NEWS",
  "source": {
    "name": "hn.algolia.com",
    "url": "https://spectrum.ieee.org/..."
  },
  "collectedAt": "2026-09-04T10:10:20Z",
  "content": {
    "headline": "Fusion Dreams Drive High-Temperature Superconductor Quest",
    "full_text": "Fusion Dreams Drive...",
    "published_date": "2026-09-04T09:52:54Z",
    "related_entity": "OpenAI"
  }
}
```

### Why this JSON structure?

The `source` field is **required on every record**. This is the pipeline's anti-hallucination mechanism — every record can be traced back to a real URL. If a record looks suspicious, you can visit `source.url` and verify it yourself.

---

## 10. The Google Sheet Output

The final deliverable is a 6-tab Google Sheet. Here's what each tab contains:

```
┌─────────────────────────────────────────────────────────────────┐
│           GRAPHONE AI INTELLIGENCE PIPELINE — Google Sheet      │
│                                                                 │
│  TAB NAME            │ ROWS    │ WHAT IT CONTAINS                │
│  ────────────────────┼─────────┼───────────────────────────────  │
│  🏢 Startups         │  1,237  │ AI companies from GitHub, HF    │
│  🛍️ Products         │  1,312  │ AI products with pricing model  │
│  📄 Research Papers  │  2,138  │ AI papers from arXiv + PWC      │
│  💼 Jobs             │    211  │ AI jobs from last 24 hours      │
│  📰 News             │    349  │ AI news from last 24 hours      │
│  🔗 Entity Mapping   │  2,548  │ Name-cleanup audit log          │
│  ────────────────────┴─────────┴───────────────────────────────  │
│  TOTAL              │  7,795  │                                  │
│                                                                 │
│  Each tab has:                                                   │
│  • Row 1: Bold, frozen column headers                           │
│  • Row 2+: Data rows                                            │
│  • Schema-accurate columns (source.url is always present)       │
└─────────────────────────────────────────────────────────────────┘
```

### How to update the sheet

Run the export script anytime to refresh the data:

```bash
python scripts/export_to_sheets.py
```

This reads the SQLite database and overwrites all 6 tabs with fresh data. The service account must have **Editor** access to the sheet.

---

## 11. How to Run the Pipeline

### Quick start

```bash
# 1. Install dependencies
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env and add your keys

# 3. Run the full pipeline (all phases in order)
python -m src.pipeline.main --phase all

# 4. Export to Google Sheets
python scripts/export_to_sheets.py
```

### Run individual phases

```bash
# Phase 1: Research papers (arxiv + paperswithcode + github stars)
python -m src.pipeline.main --phase papers

# Phase 2: Startups (github topics + huggingface orgs)
python -m src.pipeline.main --phase startups

# Phase 3: Products (seed list + huggingface models)
python -m src.pipeline.main --phase products

# Phase 4: Freshness (news + jobs — 24h window)
python -m src.pipeline.main --phase freshness
```

### Run tests

```bash
python -m pytest
```

Expected output: `24 passed in ~10s`

---

## 12. Glossary of Terms

| Term | Plain English Definition |
|---|---|
| **API** | Application Programming Interface — a way for programs to talk to each other. Like a waiter taking your order and bringing food from the kitchen. |
| **Async / Asyncio** | Doing multiple things at once without waiting for each to finish. Like sending 10 emails at the same time instead of one after another. |
| **Chunking** | Splitting a large piece of data into smaller pieces so an LLM can process it. Like cutting a long book into chapters. |
| **Context Window** | The maximum amount of text an LLM can read at once. Like the size of a single page of a book. |
| **Deduplication** | Removing duplicate entries. Like removing repeated songs from a playlist. |
| **Entity Resolution** | Figuring out that "Open AI", "OpenAI", and "openai.com" all refer to the same company. |
| **Fuzzy Matching** | Finding similar strings even when they're spelled slightly differently. Like a spell-checker suggesting corrections. |
| **Freshness Gate** | A filter that only allows data newer than a certain age (24 hours) to pass through. Like a bouncer at a club checking IDs. |
| **gspread** | A Python library that lets us write data to Google Sheets programmatically. |
| **HTTP 429** | "Too Many Requests" — the website told us to slow down. |
| **HTTP 413** | "Payload Too Large" — we sent more data than the API can handle. |
| **LLM** | Large Language Model — an AI trained on billions of text examples. Can read and summarize text, extract information, and answer questions. |
| **Payload** | The actual data being sent in an HTTP request or response. |
| **Pydantic** | A Python library for defining and validating data schemas. Like a type-checker for JSON data. |
| **Rate Limiting** | A rule that says "you can only make X requests per second to this website." Prevents getting blocked or banned. |
| **RSS / Atom** | A standardized format for sharing news/article feeds. Like a newsletter subscription. |
| **RawDocument** | The standard format every scraper outputs, containing source, URL, content, and hash. |
| **Schema** | A blueprint that defines what fields a record must have and what types they should be. |
| **Schema Validation** | Checking that data matches its schema. Invalid data gets rejected. |
| **Scraping** | Automatically extracting data from websites. Like a robot reading webpages. |
| **SHA-256** | A "fingerprint" for data — a unique string of characters computed from any input. Same input always produces the same fingerprint. Used for deduplication. |
| **SQLite** | A simple file-based database. Stores data in a single `.db` file. No server needed. |
| **Service Account** | A robot Google account used for programmatic access to Google services (Sheets, Drive). |
| **Token** | A secret key that authenticates API requests. Like a password for programs. |

---

*Document version: 1.0 — 2026-09-04*
*Part of the GraphOne AI Intelligence Pipeline*
