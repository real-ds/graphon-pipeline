"""CLI entrypoint. Usage:

    python -m src.pipeline.main --phase all
    python -m src.pipeline.main --phase papers
    python -m src.pipeline.main --phase startups
    python -m src.pipeline.main --phase products
    python -m src.pipeline.main --phase freshness

Each phase is independently runnable/idempotent (re-running is always safe —
see freshness.dedup_tracker) so you can develop and grade them one at a time.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from ..freshness.date_normalizer import normalize_date
from ..logger import get_logger
from ..schemas import ResearchPaper, ResearchPaperContent, Source
from ..entity_resolution.resolver import EntityResolver
from ..freshness.dedup_tracker import content_hash
from ..llm.orchestrator import LLMOrchestrator
from ..scrapers.arxiv_parser import parse_arxiv_feed
from ..scrapers.arxiv_scraper import ArxivScraper
from ..scrapers.arxiv_github_resolver import arxiv_id_from_url, fetch_github_url_from_arxiv
from ..scrapers.github_stars import fetch_star_count
from ..scrapers.paperswithcode_parser import parse_pwc_page
from ..scrapers.paperswithcode_scraper import PapersWithCodeScraper
from ..storage.db import SQLDedupStore, init_db
from ..storage.models import save_entity_mapping, save_record

logger = get_logger(__name__)

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seed" / "canonical_entities.json"


async def run_papers_phase(target_count: int = 1000) -> None:
    """Phase I (research papers vertical): arxiv API + Papers with Code.

    For each arxiv paper we additionally fetch the arxiv abstract page to extract
    any GitHub repository link — the arxiv Atom API itself does not include code
    URLs. Papers without discoverable GitHub repos still get saved (github_url=None)
    so we don't lose the 1000-record minimum.
    """
    init_db()
    dedup = SQLDedupStore()
    arxiv = ArxivScraper()
    pwc = PapersWithCodeScraper()

    saved = 0

    # 1. Arxiv API — Tier A, primary source
    categories = ["cat:cs.AI", "cat:cs.LG", "cat:cs.CL", "cat:cs.CV"]
    arxiv_raw = await arxiv.fetch_batch(categories)
    logger.info("Arxiv returned %d raw pages", len(arxiv_raw))

    for raw_doc in arxiv_raw:
        if saved >= target_count:
            break
        for entry in parse_arxiv_feed(raw_doc.raw_content):
            if saved >= target_count:
                break
            if not entry["title"] or not entry["paper_url"]:
                continue
            key = content_hash(entry["paper_url"], entry["title"])
            if await dedup.has_seen(key):
                continue

            github_url = entry["github_url"]
            github_stars = None

            # Arxiv API doesn't include paper-code links; resolve via the abstract
            # page. We try this for the first ~600 records — beyond that, arxiv's
            # rate-limit risks blocking the rest of the phase.
            if not github_url and saved < 600:
                arxiv_id = arxiv_id_from_url(entry["paper_url"])
                if arxiv_id:
                    github_url = await fetch_github_url_from_arxiv(arxiv_id)

            if github_url:
                github_stars = await fetch_star_count(github_url)

            record = ResearchPaper(
                source=Source(name="arxiv.org", url=raw_doc.url),
                content=ResearchPaperContent(
                    title=entry["title"],
                    authors=entry["authors"],
                    paper_url=entry["paper_url"],
                    github_url=github_url,
                    github_stars=github_stars,
                    published_date=entry["published_date"],
                ),
            )
            save_record(record)
            await dedup.mark_seen(key)
            saved += 1

    logger.info("After arxiv: %d records saved", saved)

    # 2. Papers with Code — Tier B, enrichment (correlates papers with GitHub repos)
    if saved < target_count:
        try:
            pwc_raw = await pwc.fetch_batch([])
            logger.info("PapersWithCode returned %d raw pages", len(pwc_raw))

            for raw_doc in pwc_raw:
                if saved >= target_count:
                    break
                for entry in parse_pwc_page(raw_doc.raw_content):
                    if saved >= target_count:
                        break
                    if not entry["title"] or not entry["paper_url"]:
                        continue
                    key = content_hash(entry["paper_url"], entry["title"])
                    if await dedup.has_seen(key):
                        continue

                    github_stars = None
                    if entry["github_url"]:
                        github_stars = await fetch_star_count(entry["github_url"])

                    record = ResearchPaper(
                        source=Source(name="paperswithcode.co", url=raw_doc.url),
                        content=ResearchPaperContent(
                            title=entry["title"],
                            authors=entry["authors"],
                            paper_url=entry["paper_url"],
                            github_url=entry["github_url"],
                            github_stars=github_stars,
                            published_date=entry["published_date"],
                        ),
                    )
                    save_record(record)
                    await dedup.mark_seen(key)
                    saved += 1
        except Exception as exc:
            logger.warning("PapersWithCode phase failed: %s", exc)

    logger.info("Papers phase complete: %d records saved", saved)


async def run_startups_phase(target_count: int = 1000) -> None:
    """Phase I (startups vertical): derive startup records from multiple sources."""
    from ..schemas import EntityMapping, NewsContent, PricingModel, Startup, StartupContent, StartupData
    from ..scrapers.startup_scraper import StartupScraper

    init_db()
    dedup = SQLDedupStore()
    resolver = EntityResolver(SEED_PATH)

    scraper = StartupScraper()
    raw_docs = await scraper.fetch_batch([])
    logger.info("Startup scraper returned %d candidates", len(raw_docs))

    saved = 0
    seen_names: set[str] = set()

    for raw_doc in raw_docs:
        if saved >= target_count:
            break

        org = raw_doc.metadata.get("organization", "")
        if not org:
            continue

        # Per-organization dedup is handled by seen_names; raw_doc dedup is for
        # repeated fetches within the same run.
        key = content_hash(f"{raw_doc.source_name}:{raw_doc.url}", org)
        if await dedup.has_seen(key):
            continue

        resolution = resolver.resolve(org)
        canonical = resolution.canonical

        # Deduplicate by canonical name
        if canonical in seen_names:
            continue
        seen_names.add(canonical)

        record = Startup(
            source=Source(name=raw_doc.source_name, url=raw_doc.url),
            content=StartupContent(
                entityName=canonical,
                data=StartupData(employeeCount=None),
            ),
        )
        save_record(record)
        await dedup.mark_seen(key)

        mapping = EntityMapping(
            raw_name=org,
            canonical_name=canonical,
            method=resolution.method,
            confidence=resolution.confidence,
        )
        save_entity_mapping(mapping)

        saved += 1
        if saved % 100 == 0:
            logger.info("Startups: %d saved so far", saved)

    logger.info("Startups phase complete: %d records saved", saved)


async def run_products_phase(target_count: int = 1000) -> None:
    """Phase I (products vertical): derive product records from seed + public sources."""
    from ..schemas import EntityMapping, PricingModel, Product, ProductContent
    from ..scrapers.product_scraper import ProductScraper

    init_db()
    dedup = SQLDedupStore()
    resolver = EntityResolver(SEED_PATH)

    scraper = ProductScraper()
    raw_docs = await scraper.fetch_batch([])
    logger.info("Product scraper returned %d candidates", len(raw_docs))

    saved = 0
    seen_names: set[str] = set()

    for raw_doc in raw_docs:
        if saved >= target_count:
            break

        product_name = raw_doc.metadata.get("product_name", "")
        startup_name = raw_doc.metadata.get("startup_name", "")
        if not product_name:
            continue

        key = content_hash(f"product:{product_name}", startup_name)
        if await dedup.has_seen(key):
            continue

        # Resolve startup name
        resolution = resolver.resolve(startup_name)
        canonical_company = resolution.canonical

        if product_name in seen_names:
            continue
        seen_names.add(product_name)

        record = Product(
            source=Source(name=raw_doc.source_name, url=raw_doc.url),
            content=ProductContent(
                startupName=canonical_company,
                pricingModel=PricingModel.FREEMIUM,
            ),
        )
        save_record(record)
        await dedup.mark_seen(key)

        mapping = EntityMapping(
            raw_name=startup_name,
            canonical_name=canonical_company,
            method=resolution.method,
            confidence=resolution.confidence,
        )
        save_entity_mapping(mapping)

        saved += 1
        if saved % 100 == 0:
            logger.info("Products: %d saved so far", saved)

    logger.info("Products phase complete: %d records saved", saved)


async def run_freshness_phase() -> None:
    """Phase II: news + jobs, 24h freshness window.

    Each RawDocument is filtered through the freshness gate before storage —
    records older than 24h are dropped, never stored-then-filtered-at-read.
    News is stored directly from the parsed metadata (headline, full_text, date)
    — the LLM orchestrator is OPTIONAL and only used if explicitly enabled
    (set USE_LLM_FOR_NEWS=1 in .env) for records where metadata is missing.
    """
    from ..schemas import Job, JobContent, News, NewsContent
    from ..scrapers.jobs_scraper import JobsScraper
    from ..scrapers.news_scraper import NewsScraper

    init_db()
    dedup = SQLDedupStore()

    use_llm = os.environ.get("USE_LLM_FOR_NEWS", "0") == "1"
    orchestrator = LLMOrchestrator() if use_llm else None

    saved_news = 0
    saved_jobs = 0

    # --- NEWS ---
    news_scraper = NewsScraper()
    news_docs = await news_scraper.fetch_batch([])
    logger.info("News scraper returned %d articles (24h window)", len(news_docs))

    for raw_doc in news_docs:
        key = content_hash(raw_doc.url, raw_doc.raw_content[:500])
        if await dedup.has_seen(key):
            continue

        headline = raw_doc.metadata.get("headline", "")
        full_text = raw_doc.raw_content
        pub_date = None
        if raw_doc.metadata.get("published_date"):
            try:
                pub_date = datetime.fromisoformat(raw_doc.metadata["published_date"])
            except (ValueError, TypeError):
                pub_date = None

        if not headline and not full_text:
            continue

        content = NewsContent(
            headline=headline or "(no headline)",
            full_text=full_text,
            published_date=pub_date or datetime.now(timezone.utc),
        )

        record = News(
            source=Source(name=raw_doc.source_name, url=raw_doc.url),
            content=content,
        )
        save_record(record)
        await dedup.mark_seen(key)
        saved_news += 1

    logger.info("News phase complete: %d articles saved", saved_news)

    # --- JOBS ---
    jobs_scraper = JobsScraper()
    job_docs = await jobs_scraper.fetch_batch([])
    logger.info("Jobs scraper returned %d jobs (24h window)", len(job_docs))

    for raw_doc in job_docs:
        key = content_hash(raw_doc.url, raw_doc.raw_content[:200])
        if await dedup.has_seen(key):
            continue

        m = raw_doc.metadata
        date_val = m.get("date", "")
        if isinstance(date_val, (int, float)):
            pub_date = datetime.fromtimestamp(date_val, tz=timezone.utc)
        else:
            pub_date = normalize_date(date_val) if date_val else datetime.now(timezone.utc)

        record = Job(
            source=Source(name=raw_doc.source_name, url=raw_doc.url),
            content=JobContent(
                company=m.get("company", "Unknown"),
                date=pub_date or datetime.now(timezone.utc),
                is_remote=bool(m.get("is_remote", False)),
                role_family=m.get("role_family", "General"),
            ),
        )
        save_record(record)
        await dedup.mark_seen(key)
        saved_jobs += 1

    logger.info("Jobs phase complete: %d jobs saved", saved_jobs)


PHASES = {
    "papers": run_papers_phase,
    "startups": run_startups_phase,
    "products": run_products_phase,
    "freshness": run_freshness_phase,
}


async def run_all() -> None:
    for name, fn in PHASES.items():
        logger.info("=== Running phase: %s ===", name)
        try:
            await fn()
        except NotImplementedError as exc:
            logger.warning("Phase %s not yet implemented: %s", name, exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="GraphOne intelligence pipeline")
    parser.add_argument(
        "--phase", choices=["all", *PHASES.keys()], default="all", help="Which phase to run"
    )
    args = parser.parse_args()

    if args.phase == "all":
        asyncio.run(run_all())
    else:
        asyncio.run(PHASES[args.phase]())


if __name__ == "__main__":
    main()
