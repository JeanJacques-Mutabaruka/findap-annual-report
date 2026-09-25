"""Template preview: a picture of 4 pages (cover, corporate information, P&L, first generated notes) of a
template filled with the demo data. Needs LibreOffice (docx -> pdf) and PyMuPDF (pdf -> png).

Previews are normally prepared once by the administrator and stored as  templates/<id>/preview.png
(see scripts/make_previews.py); the app can also build one on the fly when LibreOffice is installed.
"""
from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

from . import CHART, DEMO, NOTES, build_model, export_pdf, render_report

KEY_TEXTS = ("CORPORATE INFORMATION|GENERAL INFORMATION|COMPANY INFORMATION",
             "STATEMENT OF COMPREHENSIVE INCOME",
             "Revenues")


def sample_docx(docx: str | Path, notes: str | Path | None = None, font: str | None = None) -> bytes:
    d = json.loads(Path(DEMO).read_text(encoding="utf-8"))
    nt = json.loads(Path(notes or NOTES).read_text(encoding="utf-8"))
    model = build_model.build(d, json.loads(Path(CHART).read_text(encoding="utf-8")), nt)
    out = io.BytesIO()
    render_report.render(str(docx), model, out, allow_blocking=True, font_name=font)
    return out.getvalue()


def pick_pages(doc) -> list[int]:
    """Page indexes: cover, then the first page containing each KEY_TEXTS pattern (after the contents page)."""
    import re
    pages = [0]
    for pat in KEY_TEXTS:
        for i in range(2, doc.page_count):
            if re.search(pat, doc[i].get_text()) and i not in pages:
                pages.append(i)
                break
    return pages[:4]


def preview_png(docx_bytes: bytes, width_per_page: int = 360) -> bytes:
    """docx -> pdf (LibreOffice) -> 4 pages side by side as one PNG."""
    import pymupdf
    with tempfile.TemporaryDirectory() as tmp:
        dx, pdf = Path(tmp) / "sample.docx", Path(tmp) / "sample.pdf"
        dx.write_bytes(docx_bytes)
        export_pdf.export(dx, pdf)
        doc = pymupdf.open(pdf)
        pages = pick_pages(doc)
        pix = [doc[i].get_pixmap(matrix=pymupdf.Matrix(width_per_page / doc[i].rect.width, width_per_page / doc[i].rect.width))
               for i in pages]
        gap = 12
        w = sum(p.width for p in pix) + gap * (len(pix) + 1)
        h = max(p.height for p in pix) + 2 * gap
        canvas = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h), False)
        canvas.clear_with(0xDDE3EA)
        x = gap
        for p in pix:
            p = pymupdf.Pixmap(pymupdf.csRGB, p) if p.n != 3 or p.alpha else p
            p.set_origin(x, gap)
            canvas.copy(p, p.irect)
            x += p.width + gap
        return canvas.tobytes("png")
