"""SQLite-backed storage (source of truth to develop against before wiring
Google Sheets). Also provides SQLDedupStore, the production-shaped
implementation of the DedupStore protocol from freshness/dedup_tracker.py —
this is what makes "never process the same item twice" durable across restarts
(and, with DATABASE_URL pointed at Postgres, across distributed crawler nodes).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from ..config import settings

Base = declarative_base()


class RecordRow(Base):
    __tablename__ = "records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_type = Column(String, index=True, nullable=False)
    source_url = Column(String, index=True, nullable=False)
    payload_json = Column(Text, nullable=False)  # full validated record, as JSON
    collected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class EntityMappingRow(Base):
    __tablename__ = "entity_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_name = Column(String, nullable=False)
    canonical_name = Column(String, nullable=False, index=True)
    method = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    resolved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SeenHashRow(Base):
    __tablename__ = "seen_hashes"

    content_hash = Column(String, primary_key=True)
    first_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


_engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=_engine, future=True)


def init_db() -> None:
    Base.metadata.create_all(_engine)


class SQLDedupStore:
    """Sync SQLAlchemy calls wrapped for the async DedupStore protocol via a
    thread — fine at this pipeline's scale; swap for an async driver
    (e.g. `databases` + asyncpg) if you move to Postgres at high concurrency.
    """

    async def has_seen(self, key: str) -> bool:
        import asyncio

        return await asyncio.to_thread(self._has_seen_sync, key)

    async def mark_seen(self, key: str) -> None:
        import asyncio

        await asyncio.to_thread(self._mark_seen_sync, key)

    @staticmethod
    def _has_seen_sync(key: str) -> bool:
        with SessionLocal() as session:
            return session.get(SeenHashRow, key) is not None

    @staticmethod
    def _mark_seen_sync(key: str) -> None:
        with SessionLocal() as session:
            if session.get(SeenHashRow, key) is None:
                session.add(SeenHashRow(content_hash=key))
                session.commit()
