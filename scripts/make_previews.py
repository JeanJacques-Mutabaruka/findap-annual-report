#!/usr/bin/env python3
"""
make_previews.py — (administrator) build templates/<id>/preview.png for every template, or for the ids given.

Usage (from the project folder, after run.bat created .venv):
    .venv\\Scripts\\python.exe scripts\\make_previews.py            (all templates)
    .venv\\Scripts\\python.exe scripts\\make_previews.py sme-arial  (one template)
Needs LibreOffice installed. Then upload the new preview.png into the template folder on GitHub.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine import preview, templates  # noqa: E402

wanted = set(sys.argv[1:])
for t in templates.list_templates():
    if wanted and t["id"] not in wanted:
        continue
    png = preview.preview_png(preview.sample_docx(t["docx"], t["notes"], t["default_font"]))
    out = Path(t["docx"]).parent / "preview.png"
    out.write_bytes(png)
    print(f"{t['id']}: {out} ({len(png) // 1024} kB)")
