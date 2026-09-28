"""Calculation and document engine of the Annual Report Generator (no Streamlit imports here).

The same scripts are shipped in the `annual-report-generator` AI skill:
build_model.py, render_report.py, export_pdf.py, xlsm_import.py (= xlsm_to_input.py).
"""
from pathlib import Path

VERSION = "V2026-09-28 0153"  # deliveries are indexed by date and time (Munich time)
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CHART = DATA / "chart_of_accounts.json"
NOTES = DATA / "notes_default.json"
TEMPLATE = ROOT / "templates" / "standard-v09" / "template.docx"   # default template (tests, fallback)
DEMO = DATA / "demo" / "demo_input.json"
