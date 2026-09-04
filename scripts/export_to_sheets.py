#!/usr/bin/env python
"""Run this after the pipeline has populated the local DB to push everything to
the required 6-tab Google Sheet.

Usage: python scripts/export_to_sheets.py
"""
from src.storage.sheets_exporter import export_all

if __name__ == "__main__":
    export_all()
