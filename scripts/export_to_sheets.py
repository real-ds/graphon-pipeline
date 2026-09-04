"""Export all DB records to Google Sheets.

Two modes:
  1. AUTO-CREATE: If GOOGLE_SHEETS_ID is empty, creates a new spreadsheet
     named 'GraphOne AI Intelligence Pipeline' and prints the URL.
  2. UPDATE EXISTING: If GOOGLE_SHEETS_ID is set, updates the existing
     spreadsheet (assumes the service account has been granted Editor access).

Usage:
    python scripts/export_to_sheets.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy import select

from src.config import settings
from src.logger import get_logger
from src.storage.db import EntityMappingRow, RecordRow, SessionLocal

logger = get_logger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

_HEADERS_BY_TAB: dict = {
    "Startups": [
        "schemaVersion",
        "recordType",
        "source.name",
        "source.url",
        "collectedAt",
        "content.entityName",
        "content.data.employeeCount",
    ],
    "Products": [
        "schemaVersion",
        "recordType",
        "source.name",
        "source.url",
        "collectedAt",
        "content.startupName",
        "content.pricingModel",
    ],
    "Research Papers": [
        "schemaVersion",
        "recordType",
        "source.name",
        "source.url",
        "collectedAt",
        "content.title",
        "content.authors",
        "content.paper_url",
        "content.github_url",
        "content.github_stars",
        "content.published_date",
    ],
    "Jobs": [
        "schemaVersion",
        "recordType",
        "source.name",
        "source.url",
        "collectedAt",
        "content.company",
        "content.date",
        "content.is_remote",
        "content.role_family",
    ],
    "News": [
        "schemaVersion",
        "recordType",
        "source.name",
        "source.url",
        "collectedAt",
        "content.headline",
        "content.full_text",
        "content.published_date",
        "content.related_entity",
    ],
    "Entity Mapping Log": [
        "raw_name",
        "canonical_name",
        "method",
        "confidence",
    ],
}

_TAB_FOR_RECORD_TYPE = {
    "STARTUP": "Startups",
    "PRODUCT": "Products",
    "RESEARCH_PAPER": "Research Papers",
    "JOB": "Jobs",
    "NEWS": "News",
}

# Map dotted header path -> value from a (possibly-nested) dict.
def _dig(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return ""
        cur = cur[part]
    if cur is None:
        return ""
    if isinstance(cur, (list, tuple)):
        return ", ".join(str(x) for x in cur)
    return str(cur)


def _client() -> gspread.Client:
    if not settings.google_service_account_json:
        raise RuntimeError("Set GOOGLE_SERVICE_ACCOUNT_JSON in .env before exporting.")
    creds = Credentials.from_service_account_file(
        settings.google_service_account_json, scopes=_SCOPES
    )
    return gspread.authorize(creds)


def _column_letter(idx: int) -> str:
    """1-indexed: 1 -> A, 26 -> Z, 27 -> AA."""
    s = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        s = chr(ord("A") + rem) + s
    return s


def _write_tab(sheet, tab_name: str, headers: list, rows: Iterable[dict]) -> int:
    """Clear the tab, write headers + rows. Returns number of data rows written."""
    try:
        ws = sheet.worksheet(tab_name)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab_name, rows=100, cols=len(headers))

    rows = list(rows)
    if not rows:
        # Still write headers even if no data, so the user can see the schema.
        ws.update(range_name=f"A1:{_column_letter(len(headers))}1", values=[headers])
        ws.format("A1:Z1", {"textFormat": {"bold": True}})
        return 0

    last_col = _column_letter(len(headers))
    values: list = [headers]
    for r in rows:
        values.append([_dig(r, h) for h in headers])

    # Write header + body in one shot to keep them aligned.
    ws.update(range_name=f"A1:{last_col}{len(values)}", values=values)
    ws.format("A1:Z1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)
    logger.info("Wrote %d data rows (+1 header) to tab '%s'", len(rows), tab_name)
    return len(rows)


def export_all() -> str:
    """Returns the spreadsheet URL (created if GOOGLE_SHEETS_ID was empty)."""
    if not settings.google_service_account_json:
        raise RuntimeError("Set GOOGLE_SERVICE_ACCOUNT_JSON in .env before exporting.")

    gc = _client()

    if settings.google_sheets_id:
        print(f"Opening existing spreadsheet {settings.google_sheets_id}...")
        sheet = gc.open_by_key(settings.google_sheets_id)
    else:
        sheet_name = "GraphOne AI Intelligence Pipeline"
        print(f"Creating new spreadsheet '{sheet_name}'...")
        try:
            existing = gc.open(sheet_name)
            print("  Deleting existing sheet to recreate...")
            gc.del_spreadsheet(existing.id)
        except gspread.SpreadsheetNotFound:
            pass
        sheet = gc.create(sheet_name)
        try:
            sheet.del_worksheet(sheet.sheet1)
        except Exception:
            pass

    rows_by_type: dict = {t: [] for t in _TAB_FOR_RECORD_TYPE}
    with SessionLocal() as session:
        for row in session.scalars(select(RecordRow)):
            if row.record_type in rows_by_type:
                try:
                    rows_by_type[row.record_type].append(json.loads(row.payload_json))
                except (json.JSONDecodeError, TypeError):
                    pass

        mapping_rows = []
        for m in session.scalars(select(EntityMappingRow)):
            mapping_rows.append({
                "raw_name": m.raw_name,
                "canonical_name": m.canonical_name,
                "method": m.method,
                "confidence": m.confidence,
            })

    totals: dict = {}
    for record_type, tab_name in _TAB_FOR_RECORD_TYPE.items():
        totals[tab_name] = _write_tab(
            sheet, tab_name, _HEADERS_BY_TAB[tab_name], rows_by_type.get(record_type, [])
        )
    totals["Entity Mapping Log"] = _write_tab(
        sheet, "Entity Mapping Log", _HEADERS_BY_TAB["Entity Mapping Log"], mapping_rows
    )

    url = sheet.url
    print()
    print("=" * 60)
    print("EXPORT COMPLETE")
    print("=" * 60)
    for tab_name, count in totals.items():
        print(f"  {tab_name}: {count} data rows + 1 header row")
    print()
    print(f"Spreadsheet URL: {url}")
    print()
    if not settings.google_sheets_id:
        print("Spreadsheet ID (add to .env as GOOGLE_SHEETS_ID to update later):")
        print(f"  {sheet.id}")
    print()
    print("NEXT STEPS:")
    print("1. Open the URL above")
    print("2. Click 'Share' -> 'Anyone with the link' -> 'Viewer'")
    print("3. Copy the shareable link and submit via the form")
    return url


if __name__ == "__main__":
    try:
        export_all()
    except Exception as exc:
        print(f"\nERROR: {type(exc).__name__}: {exc}")
        print()
        print("If you got 'Spreadsheet not found' or permission errors:")
        print("- Make sure GOOGLE_SHEETS_ID is correct (the long string in the sheet URL)")
        print("- Service account needs Editor access to the sheet")
        print("  Share the sheet with: graphone-sheets@my-projects-auth-504106.iam.gserviceaccount.com")
        sys.exit(1)
