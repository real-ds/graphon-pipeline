"""Persistent dedup store: the mechanism that guarantees the pipeline never
processes the same article/job twice, even across distributed crawler nodes
(Phase VI, question 3).

For the take-home this is a SQLite table (see src/storage/db.py for the engine);
in production this becomes a shared Redis SET or Postgres table so multiple
crawler processes/nodes share one dedup state instead of each having its own.
The interface below is deliberately storage-agnostic so that swap is a backend
change, not a call-site change.
"""
from __future__ import annotations

import hashlib
from typing import Protocol


def content_hash(url: str, content: str) -> str:
    """Stable identity for a piece of content: same URL + same content -> same hash.
    If a page's content changes (edited article), the hash changes too, so an
    edited-and-republished item is correctly treated as "new" content to re-check.
    """
    h = hashlib.sha256()
    h.update(url.strip().lower().encode("utf-8"))
    h.update(b"|")
    h.update(content.strip().encode("utf-8"))
    return h.hexdigest()


class DedupStore(Protocol):
    async def has_seen(self, key: str) -> bool: ...
    async def mark_seen(self, key: str) -> None: ...


class InMemoryDedupStore:
    """Dev/test double. NOT safe across distributed nodes or process restarts —
    use SQLDedupStore (src/storage/db.py) for anything that needs to persist.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    async def has_seen(self, key: str) -> bool:
        return key in self._seen

    async def mark_seen(self, key: str) -> None:
        self._seen.add(key)
