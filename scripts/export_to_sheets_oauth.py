"""Export all DB records to Google Sheets using OAuth2 (your own Google account).

This avoids the service-account-creation restriction in many GCP organizations.
You'll authenticate with your own Google account in a browser window, and the
script will create a new spreadsheet (or update an existing one) with the 6 tabs.

Usage:
    python scripts/export_to_sheets_oauth.py

First run will open a browser for OAuth2 consent. Token is cached at
credentials/oauth_token.json for subsequent runs.

Requirements:
    - credentials/oauth_client.json (download from GCP → APIs → Credentials →
      Create OAuth 2.0 Client ID → Desktop app)

If you don't want to set up OAuth2, use scripts/export_to_csv.py and
manually upload the CSVs to a Google Sheet.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from gspread import Client, authorize
from sqlalchemy import select

from src.logger import get_logger
from src.storage.db import EntityMappingRow, RecordRow, SessionLocal

logger = get_logger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",  # needed to create sheets
]
_CLIENT_SECRET = Path("credentials/oauth_client.json")
_TOKEN_FILE = Path("credentials/oauth_token.json")

_TAB_FOR_RECORD_TYPE = {
    "STARTUP": "Startups",
    "PRODUCT": "Products",
    "RESEARCH_PAPER": "Research Papers",
    "JOB": "Jobs",
    "NEWS": "News",
}


def _flatten(d: dict, prefix: str = "") -> dict:
    flat = {}
    for key, value in d.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, full_key))
        else:
            flat[full_key] = value
    return flat


def get_client() -> Client:
    """Authenticate via OAuth2 and return a gspread client."""
    if not _CLIENT_SECRET.exists():
        raise FileNotFoundError(
            f"OAuth client secrets not found at {_CLIENT_SECRET}.\n"
            "Create one at: https://console.cloud.google.com → APIs & Services → "
            "Credentials → Create Credentials → OAuth 2.0 Client ID → Desktop app.\n"
            "Save the JSON as credentials/oauth_client.json"
        )

    creds: Credentials | None = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(_CLIENT_SECRET), _SCOPES)
            creds = flow.run_local_server(port=0)
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(creds.to_json())

    return authorize(creds)


def export_via_oauth(spreadsheet_name: str = "GraphOne AI Intelligence Pipeline") -> str:
    """Create (or replace) a new spreadsheet and populate the 6 required tabs.
    Returns the spreadsheet URL.
    """
    gc = get_client()

    # Delete any existing sheet with the same name (avoid duplicate sheets)
    try:
        existing = gc.open(spreadsheet_name)
        logger.info("Found existing sheet '%s' — deleting", spreadsheet_name)
        gc.del_spreadsheet(existing.id)
    except Exception:
        pass

    sh = gc.create(spreadsheet_name)
    logger.info("Created spreadsheet: %s (id=%s)", spreadsheet_name, sh.id)

    # Remove the default Sheet1
    try:
        sh.del_worksheet(sh.sheet1)
    except Exception:
        pass

    rows_by_type: dict[str, list[dict]] = {}
    with SessionLocal() as session:
        for row in session.scalars(select(RecordRow)):
            rt = row.record_type
            if rt not in _TAB_FOR_RECORD_TYPE:
                continue
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

    for record_type, tab_name in _TAB_FOR_RECORD_TYPE.items():
        _write_tab(sh, tab_name, rows_by_type.get(record_type, []))
    _write_tab(sh, "Entity Mapping Log", mapping_rows)

    return sh.url


def _write_tab(sh, tab_name: str, rows: list[dict]) -> None:
    ws = sh.add_worksheet(title=tab_name, rows=max(len(rows) + 10, 100), cols=20)
    if not rows:
        return

    headers = sorted({key for row in rows for key in _flatten(row).keys()})
    flat_rows = [_flatten(row) for row in rows]
    values = [headers] + [[str(row.get(h, "")) for h in headers] for row in flat_rows]

    # gspread's update is rate-limited; batch by 1000 rows
    for i in range(0, len(values), 1000):
        chunk = values[i : i + 1000]
        ws.update(f"A1:{chr(ord('A') + len(headers) - 1)}{len(chunk)}", chunk)
    logger.info("  Wrote %d rows to tab '%s'", len(rows), tab_name)


if __name__ == "__main__":
    print("=" * 60)
    print("GraphOne Pipeline → Google Sheets (OAuth2)")
    print("=" * 60)
    print()
    print("This will create a new Google Sheet called:")
    print("  'GraphOne AI Intelligence Pipeline'")
    print()
    print("On first run, a browser will open for OAuth2 consent.")
    print("The OAuth token is cached at credentials/oauth_token.json.")
    print()
    try:
        url = export_via_oauth()
        print()
        print("=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print(f"Spreadsheet URL: {url}")
        print()
        print("Next steps:")
        print("1. Open the URL above")
        print("2. Click Share → 'Anyone with the link' → 'Viewer'")
        print("3. Copy the shareable link and submit via the form")
    except FileNotFoundError as exc:
        print(f"\nERROR: {exc}")
        print()
        print("Alternative: use scripts/export_to_csv.py and upload CSVs manually.")
        sys.exit(1)
