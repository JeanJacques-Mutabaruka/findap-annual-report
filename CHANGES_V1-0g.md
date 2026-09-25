# V1-0g

## Templates
- Four new templates next to the standard one, each with different wording and its own default font:
  | Folder | Alias | Default font | Differences |
  |---|---|---|---|
  | `standard-v09` | Annual report — Standard (V09) | Cambria | reference template |
  | `classic-times` | Annual report — Classic (Times New Roman) | Times New Roman | "Audited financial statements" cover, "General information", "Statutory auditor", longer registered-office label |
  | `modern-aptos` | Annual report — Modern (Aptos) | Aptos | "Notes to the accounts", "Board of directors", "The directors present their annual report…", "For and on behalf of the Board" |
  | `sme-arial` | Annual report — SME simplified (Arial) | Arial | "Company information", "External auditor", "Proposed dividend", own shorter notes 21–25 (`notes.json`) |
  | `formal-garamond` | Annual report — Formal (Garamond) | Garamond | "Annual report and financial statements" cover, "authorised for issue", "those charged with governance" |
- Font choice now "Template default (…)" + the 15 fonts: the default follows each template's `default_font`.
- Templates page shows the default font and whether the template has its own notes; `templates/README.md`
  explains how to rename a template (edit `alias` in `template.json` on GitHub).
