"""Thin repository functions: validated Pydantic record -> DB row.
Kept separate from db.py (schema) so the write path is easy to unit-test with a
mocked session.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..schemas import EntityMapping
from .db import EntityMappingRow, RecordRow, SessionLocal


def save_record(record: BaseModel) -> None:
    with SessionLocal() as session:
        session.add(
            RecordRow(
                record_type=getattr(record, "recordType"),
                source_url=str(record.source.url),  # type: ignore[attr-defined]
                payload_json=record.model_dump_json(),
            )
        )
        session.commit()


def save_entity_mapping(mapping: EntityMapping) -> None:
    with SessionLocal() as session:
        session.add(
            EntityMappingRow(
                raw_name=mapping.raw_name,
                canonical_name=mapping.canonical_name,
                method=mapping.method.value,
                confidence=mapping.confidence,
            )
        )
        session.commit()
