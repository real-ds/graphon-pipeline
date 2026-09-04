"""Exports the DB's records into the 6 required Google Sheets tabs:
Startups, Products, Research Papers, Jobs, News, Entity Mapping Log.

Requires a Google Cloud service account with Sheets API access; set
GOOGLE_SERVICE_ACCOUNT_JSON (path to the key file) and GOOGLE_SHEETS_ID in .env.
Share the target sheet with the service account's email before running.

TODO: fill in real credentials and run `python scripts/export_to_sheets.py` —
the query + row-shaping logic below is complete; only the credential wiring is
environment-specific.
"""
from __future__ import annotations

import json

import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy import select

from ..config import settings
from ..logger import get_logger
from .db import EntityMappingRow, RecordRow, SessionLocal

logger = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_TAB_FOR_RECORD_TYPE = {
    "STARTUP": "Startups",
    "PRODUCT": "Products",
    "RESEARCH_PAPER": "Research Papers",
    "JOB": "Jobs",
    "NEWS": "News",
}


def _client() -> gspread.Client:
    creds = Credentials.from_service_account_file(
        settings.google_service_account_json, scopes=_SCOPES
    )
    return gspread.authorize(creds)


def export_all() -> None:
    if not settings.google_sheets_id or not settings.google_service_account_json:
        raise RuntimeError(
            "Set GOOGLE_SHEETS_ID and GOOGLE_SERVICE_ACCOUNT_JSON in .env before exporting."
        )

    gc = _client()
    sheet = gc.open_by_key(settings.google_sheets_id)

    rows_by_type: dict[str, list[dict]] = {t: [] for t in _TAB_FOR_RECORD_TYPE}
    with SessionLocal() as session:
        for row in session.scalars(select(RecordRow)):
            if row.record_type in rows_by_type:
                rows_by_type[row.record_type].append(json.loads(row.payload_json))

        mapping_rows = [
            {
                "raw_name": m.raw_name,
                "canonical_name": m.canonical_name,
                "method": m.method,
                "confidence": m.confidence,
            }
            for m in session.scalars(select(EntityMappingRow))
        ]

    for record_type, tab_name in _TAB_FOR_RECORD_TYPE.items():
        _write_tab(sheet, tab_name, rows_by_type[record_type])
    _write_tab(sheet, "Entity Mapping Log", mapping_rows)

    logger.info("Export complete: %s", {t: len(rows_by_type.get(t, [])) for t in rows_by_type})


def _write_tab(sheet: gspread.Spreadsheet, tab_name: str, rows: list[dict]) -> None:
    try:
        ws = sheet.worksheet(tab_name)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab_name, rows=max(len(rows) + 10, 100), cols=20)

    if not rows:
        return

    headers = sorted({key for row in rows for key in _flatten(row).keys()})
    flat_rows = [_flatten(row) for row in rows]
    values = [headers] + [[str(row.get(h, "")) for h in headers] for row in flat_rows]
    ws.update(values)


def _flatten(d: dict, prefix: str = "") -> dict:
    """Flattens nested dicts (e.g. content.entityName) into single-level keys
    so they render as normal spreadsheet columns.
    """
    flat: dict = {}
    for key, value in d.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, full_key))
        else:
            flat[full_key] = value
    return flat
