# Word templates — administrator guide

Users choose a template on **3 · Company & Report Data → Report options** and can see / download every
template on the **🗂️ Templates** page. **Only the administrator adds or changes templates**, by committing
files to this folder on GitHub (web upload is enough). The app picks them up at its next restart
(Streamlit Cloud restarts automatically after each commit).

## One folder per template

```
templates/
├── standard-v09/                 ← folder name = template id (lower case, no spaces)
│   ├── template.json             ← manifest (required)
│   ├── template.docx             ← the Word template (required)
│   ├── notes.json                ← optional: notes specific to this template (else data/notes_default.json)
│   └── preview.png               ← optional: picture shown on the Templates page (scripts/make_previews.py)
└── _example-new-template/        ← scaffold (inactive): copy, rename, fill, set "active": true
```

## Changing the name (alias) of a template

On GitHub: open `templates/<folder>/template.json` → ✏️ **Edit this file** → change the text after
`"alias":` (keep the quotes and the comma) → **Commit changes**. The app restarts by itself in 1–2 minutes and
shows the new name everywhere (Report options, Templates page). Projects already saved keep working: they
remember the folder name, not the alias. The same way you can change `description`, `default_font`,
`order` (position in the lists) or hide a template with `"active": false`. Never rename the folder of a
template users already chose (their saved projects would fall back to the first template).

Templates delivered with V1-0g: `standard-v09` (Cambria), `classic-times` (Times New Roman),
`modern-aptos` (Aptos), `sme-arial` (Arial, own shorter notes 21–25), `formal-garamond` (Garamond).

## template.json

| Key | Meaning |
|---|---|
| `alias` | Name shown to users, e.g. `Annual report — Audit company 01` |
| `description` | One or two sentences shown on the Templates page |
| `version` | Your version of the template (e.g. `V01`) |
| `language` | `en`, `fr`… (information) |
| `file` | Word file name in the folder (default `template.docx`) |
| `notes_file` | `notes.json` or `null` |
| `default_font` | Font proposed by default (e.g. `"Times New Roman"`), `null` = fonts of the Word file |
| `order` | Position in the lists (1 = first) |
| `active` | `false` hides the template without deleting it |

## What the Word file must contain

Text fields are **bookmarks** named `str_<field>` or `str_<field>__<n>` (n = 1, 2… when a field appears
several times), e.g. `str_companyname__1`. Fields: `companyname, periodend, yearcy, yearpy, currency,
auditcompanyname, auditcompanyfulladdress, directors, registeredoffice, bankers, mainactivity,
auditorframework, accountingframework, proposeddividend, signaturedate, companyrepresentative,
fssigningdate, companydirector`.

Statement tables: one paragraph each holding a bookmark `tbl_pnl`, `tbl_balancesheet`, `tbl_equity`,
`tbl_cashflow`. Notes block: one paragraph holding the bookmark `var_notes`. Styles `Heading 2`, `Heading 3`
(numbered notes), `Heading 4` and `List Paragraph` must exist. The V09 bookmark names keep working.

The **annual-report-template-builder** skill (separate zip) lets an AI prepare a new template from any
existing Word report: it inserts the bookmarks, writes `template.json`, checks the file and produces a
sample filled with the demo data. Always open the 🗂️ Templates page after adding a template: it shows
whether the template is compatible and lets you download a sample.

## Rules

- Never put a real client's figures in a template. A client name in an alias is visible to every user of
  the app (and to everyone if the repository is public).
- To replace a template, upload the new `template.docx` into the same folder (same name) and raise
  `version` in `template.json`.
