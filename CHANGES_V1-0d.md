# V1-0d

## Several lines per CIT code — unique descriptions
- A CIT code may be used on several TB lines (e.g. two bank accounts under BS 3.1.3.2): lines are added up in
  the statements and listed one by one in the notes.
- **Each line must have its own account description** (comparison ignores case, accents, spaces and
  punctuation). A repeated description is now **BLOCKING** (`DUPLICATE_ACCOUNT`), because the notes list the
  accounts by name.
- New tab **2 · Checks & Corrections → 👯 Duplicates**: for each duplicated description, rename the lines in
  place (with a "line above" hint, e.g. the asset an accumulated-depreciation line belongs to) or **merge**
  them into one line (amounts added per year, comments joined; only when they share the same CIT code).
  One button merges every group sharing the same code.
- TB template: duplicated descriptions turn **red** (conditional formatting) + instruction added.
- ➕ Add a line (Find a code) refuses a description that already exists.

## Less scrolling
- **1 · Trial Balance**: six tabs — Upload TB · TB template · Resume / Excel generator · 🔎 Find a code ·
  ✏️ Edit lines · 📅 Years. The add-a-line amounts are one compact row. Edit lines shows Account first,
  then CIT code and amounts; Statement line / Group / Section after.
- **2 · Checks & Corrections**: verdict on top, then one tab per check with its status in the tab name
  (⚖️ Balance · 🧾 Line issues · 👯 Duplicates · 🏷️ CIT codes · 🛠️ Quick fixes · 📋 Report controls);
  report controls of several years in sub-tabs; the full code review in a pop-over.
- **5 · Generate & Download**: checklist and blocking list folded into expanders (open automatically when
  something fails).
