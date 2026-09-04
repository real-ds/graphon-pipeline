"""Export all DB records to CSV files (no Google Sheets required).

Usage:
    python scripts/export_to_csv.py

Outputs:
    data/exports/startups.csv
    data/exports/products.csv
    data/exports/research_papers.csv
    data/exports/jobs.csv
    data/exports/news.csv
    data/exports/entity_mapping.csv
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from src.storage.db import EntityMappingRow, RecordRow, SessionLocal


def _flatten(d: dict, prefix: str = "") -> dict:
    flat = {}
    for key, value in d.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, full_key))
        else:
            flat[full_key] = value
    return flat


def export_csv(output_dir: Path = Path("data/exports")) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    rows_by_type: dict[str, list[dict]] = {}

    with SessionLocal() as session:
        for row in session.scalars(select(RecordRow)):
            rt = row.record_type
            rows_by_type.setdefault(rt, [])
            try:
                rows_by_type[rt].append(json.loads(row.payload_json))
            except (json.JSONDecodeError, TypeError):
                pass

        mapping_rows = [
            {
                "raw_name": m.raw_name,
                "canonical_name": m.canonical_name,
                "method": m.method,
                "confidence": m.confidence,
            }
            for m in session.scalars(select(EntityMappingRow))
        ]

    tab_map = {
        "STARTUP": "startups",
        "PRODUCT": "products",
        "RESEARCH_PAPER": "research_papers",
        "JOB": "jobs",
        "NEWS": "news",
    }

    for rt, filename in tab_map.items():
        rows = rows_by_type.get(rt, [])
        if not rows:
            continue
        headers = sorted({k for row in rows for k in _flatten(row).keys()})
        flat_rows = [_flatten(row) for row in rows]
        out_path = output_dir / f"{filename}.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(flat_rows)
        print(f"  {filename}.csv: {len(rows)} rows -> {out_path}")

    out_path = output_dir / "entity_mapping.csv"
    if mapping_rows:
        headers = ["raw_name", "canonical_name", "method", "confidence"]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(mapping_rows)
        print(f"  entity_mapping.csv: {len(mapping_rows)} rows -> {out_path}")

    print(f"\nExport complete: {output_dir}")


if __name__ == "__main__":
    export_csv()
