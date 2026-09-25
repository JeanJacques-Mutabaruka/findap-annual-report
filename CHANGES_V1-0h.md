# V1-0h

## Company & Report Data — save and reload
- New tab **💾 Save / load** on page 3: download everything on the page (company, auditor, signatures,
  per-year tax / equity / cash-flow data, inventory movements, fixed-asset registers, report options,
  notes) as **Excel** (readable, editable) or **JSON** (exact copy), and load a saved file back.
  Only the sections present in the file are replaced; the trial balance is never touched.
  A project file (…_project.json) is accepted too.

## Files with several trial balances
- On upload, the app lists the sheets that contain a trial balance (years found, number of lines,
  balanced ✅/❌) and asks which one to use; other sheets (instructions, lists, codes…) are hidden unless
  "Show every sheet of the file" is ticked.
- The TB template generator can produce files with several TB sheets and extra information sheets.

## Template previews
- Templates page: a picture of 4 pages of each template filled with the demo data (cover, corporate
  information, statement of comprehensive income, first notes). Pictures are stored as
  `templates/<id>/preview.png`; `scripts/make_previews.py` (administrator) rebuilds them; when a template has
  no picture, a "Build a preview" button makes one on the fly if LibreOffice is available.
- `requirements.txt` adds PyMuPDF (PDF → picture).
