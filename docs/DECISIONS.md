# Key Implementation Decisions

## 2026-09-04: Initial Implementation

### LLM Provider Model Names
- **Gemini**: `gemini-1.5-flash` (scaffold) → `gemini-2.5-flash` (live verified)
- **Groq**: `llama3-70b-8192` (scaffold, decommissioned) → `openai/gpt-oss-20b` (live verified)
- **DeepSeek**: `deepseek-chat` (working, but requires credits on provided key)

### Source Selection
Confirmed via live HTTP inspection:
- ✅ **News (Tier A reliable)**: HackerNews Algolia, TechCrunch RSS, arXiv RSS, OpenAI Blog RSS, Dev.to
- ⚠️ **News (blocked)**: VentureBeat (Vercel 429), TheVerge (no /rss path), AINews (HTML scraping only)
- ✅ **Jobs (Tier A reliable)**: Arbeitnow API, RemoteOK API, Remotive API, Himalayas API
- ⚠️ **Jobs (blocked)**: YC (Cloudflare), BuiltIn (rate-limited)
- ✅ **Research Papers (Tier A)**: arxiv.org Atom API, paperswithcode.co (HTTP 200, .com redirects)
- ✅ **Startups/Products**: GitHub topic search (15 AI topics), HuggingFace orgs/models, seed list

### Pipeline Order
Papers → Startups → Products → Freshness (News+Jobs). This order matches AGENT.md priority
because the LLM-based startup/product entity resolution benefits from already-loaded seed data.

### 24h Freshness Gate
Implemented as a hard filter at ingestion time (before `save_record`). Stale records are
NEVER stored. Verified: re-running the freshness phase produces 0 duplicate records.

### Entity Resolution
50-entity seed list in `data/seed/canonical_entities.json`. Each `known_alias` is captured
as a separate raw startup (showing resolution working). Every raw→canonical decision is
logged to `EntityMapping` table. Currently 2548+ mappings across 3 phases.

### News LLM Extraction
**Disabled by default** to avoid 300+ API calls per run. Set `USE_LLM_FOR_NEWS=1` to enable.
News records store parsed metadata directly (headline, full_text, date) — this is sufficient
for the 6-tab Google Sheet requirement.

### Windows Compatibility
On Windows, `aiohttp` with the Proactor event loop can hit `WinError 121` (semaphore timeout)
on long-running connections. Fixes applied:
- Increased arxiv request timeout to 120s
- Added per-connector connection limits
- Catch `asyncio.TimeoutError` in arxiv scraper

### What I'd Add Given More Time
1. **GitHub code-search for arxiv papers**: Backfill GitHub URLs/stars for arxiv records
   (~20% currently have them) via direct GitHub API queries on arxiv abstract pages.
2. **Real PWC run**: The PWC scraper is production-ready but not in the final pipeline
   (arxiv alone provided 1000 papers). Re-enable by removing the `if saved < target_count` guard.
3. **Google Sheets export**: Code is complete. Needs GCP project + service account setup
   (out of band per the plan).
4. **News LLM extraction**: Wire `LLMOrchestrator.extract` into the news loop with
   a smaller subset (e.g. only the top 50 most-recent items).
5. **Concurrent PWC page fetching**: Already implemented in the scraper but not
   invoked in the final pipeline.
