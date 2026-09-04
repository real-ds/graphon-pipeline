"""Backfill GitHub URLs for arxiv-sourced ResearchPaper records that don't have one.

For each arxiv record in the DB, fetches the arxiv abstract page and extracts
the first github.com link found. Then queries the GitHub API for current stars.
This runs AFTER the papers phase to enrich the records.
"""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from ..config import settings
from ..logger import get_logger
from ..scrapers.arxiv_github_resolver import (
    arxiv_id_from_url,
    fetch_github_url_from_arxiv,
)
from ..scrapers.github_stars import fetch_star_count
from ..schemas import ResearchPaper, ResearchPaperContent, Source
from ..storage.db import RecordRow, SessionLocal

logger = get_logger(__name__)


async def backfill_github_urls(max_records: int = 200) -> int:
    """Enrich arxiv records with GitHub URLs (and star counts).

    Returns the number of records updated.
    """
    updated = 0

    with SessionLocal() as session:
        papers = session.scalars(
            select(RecordRow).where(RecordRow.record_type == "RESEARCH_PAPER")
        ).all()

    to_enrich: list[tuple[RecordRow, str]] = []
    for r in papers:
        if updated >= max_records:
            break
        try:
            payload = json.loads(r.payload_json)
        except (json.JSONDecodeError, TypeError):
            continue

        if payload.get("content", {}).get("github_url"):
            continue
        if "arxiv.org" not in r.source_url:
            continue

        arxiv_id = arxiv_id_from_url(payload.get("content", {}).get("paper_url", ""))
        if not arxiv_id:
            continue

        to_enrich.append((r, arxiv_id))

    logger.info("Backfilling %d arxiv records with GitHub URLs", len(to_enrich))

    sem = asyncio.Semaphore(3)
    counter = [0]

    async def enrich_one(item: tuple[RecordRow, str]) -> None:
        record_row, arxiv_id = item
        async with sem:
            gh = await fetch_github_url_from_arxiv(arxiv_id)
            stars = None
            if gh:
                stars = await fetch_star_count(gh)
            if gh:
                try:
                    payload = json.loads(record_row.payload_json)
                    payload["content"]["github_url"] = gh
                    if stars is not None:
                        payload["content"]["github_stars"] = stars
                    record_row.payload_json = json.dumps(payload)
                    with SessionLocal() as s:
                        s.add(record_row)
                        s.commit()
                    counter[0] += 1
                    if counter[0] % 10 == 0:
                        logger.info("Backfilled %d records so far", counter[0])
                except Exception as exc:
                    logger.warning("Failed to update record %s: %s", arxiv_id, exc)

    tasks = [enrich_one(item) for item in to_enrich]
    await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("Backfill complete: %d records enriched with GitHub URLs", counter[0])
    return counter[0]


if __name__ == "__main__":
    asyncio.run(backfill_github_urls())
