# V1-0f — Word templates managed by the administrator, choice of font

## Templates
- New folder **`templates/`** at the root: one sub-folder per template (`template.json` manifest with the
  **alias** shown to users, description, version, language, default font, order, active; `template.docx`;
  optional `notes.json`). Guide: `templates/README.md`. The standard template moved to `templates/standard-v09/`.
- Only the administrator adds / replaces templates (by committing the folder on GitHub). The former "upload
  another Word template" option on page 3 is **removed**.
- New page **🗂️ Templates**: one tab per template — description, version, language, main font, compatibility
  check, **download the template**, **prepare a sample filled with the demo data** (with a font of your choice),
  **use this template**.
- Page 3 → Report options: choose the **template** (by alias) and the **font**.
- Renderer: generic bookmark names for new templates (`str_<field>__<n>`, `tbl_pnl`, `tbl_balancesheet`,
  `tbl_equity`, `tbl_cashflow`, `var_notes`); V09 names still work. New fields `yearcy`, `yearpy`, `currency`.

## Font
- 15 common fonts (Aptos, Arial, Book Antiqua, Calibri, Cambria, Century Gothic, Garamond, Georgia, Helvetica,
  Amasis MT Pro, Palatino Linotype, Segoe UI, Tahoma, Times New Roman, Verdana) or "template fonts".
  The chosen font replaces every text font of the report (body, headers, footers, styles, theme, tables).
- `packages.txt` adds `fonts-liberation` (Arial / Times New Roman metrics) for online PDFs.

## Separate deliverable
- **annual-report-template-builder** skill (zip): lets an AI convert any Word report into a template
  (placeholders → bookmarks), check it, fill it with demo data and package the folder to upload.
