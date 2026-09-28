# V1-0j

## AI mapping prompt — map a TB without CIT codes with any AI assistant
- New download **CIT_code_mapping_AI_prompt.md** on **1 · Trial Balance → 📄 TB template & AI prompt** and on
  **2 · Checks & Corrections → 🏷️ CIT codes → 🤖 AI mapping prompt**.
- The user attaches the TB (Excel) and the prompt in any AI assistant; the AI returns the **same TB** (same lines,
  amounts, years, order) with a **CIT code** column, and at the end **AI statement line (check)**, **AI confidence**
  (High / Medium / Low) and **Comments** — for every doubtful line: proposed code, reason, alternative. CSV fallback
  when the AI cannot produce Excel, and a summary of the Medium / Low lines.
- Built from the app's own chart and keyword rules at download time: always the codes of this version, with the
  usual balance (debit / credit) and example keywords for each code, the Rwanda-specific rules (BS 1.09, BS 5.07,
  stock codes, codes computed by the app, total lines, suspense accounts) and a worked example.
- Confidentiality notice in the file and next to both buttons (the TB is sent to the AI provider chosen by the user).
- The file returned by the AI is uploaded like any TB — no new import step.

## Stronger in-app CIT-code suggestions (2 · Checks & Corrections → 🏷️ CIT codes)
- Suggestions now use the **balance direction** as well as the name: bank in credit → overdraft BS 8.1.4;
  depreciation in credit → BS 1.09; interest in credit → PL 8.01; VAT / WHT in credit → BS 8.1.6; loan in debit →
  BS 3.2.3; director account in debit → BS 3.2.6; supplier in debit / customer in credit flagged as advances;
  when the first keyword gives the wrong side, the next keyword on the right side is used (e.g. "Fines & Penalty -
  PAYE" → PL 5.10, not PAYE payable).
- Exact wording of a statement line ("Rent", "Share premium") → high confidence.
- **Confidence** per line 🟢 High / 🟡 Medium / 🔴 Low / ⚪ none, with a counter per level, the reason (*Why*) and an
  **Alternative** code.
- Toggles: **Pre-tick CONFIRM on 🟢 High**, **Show only the lines to review**, **Write the doubts in the Comments
  column** (on by default: the proposal, reason and alternative are added to the comment of Medium / Low lines).
- New VAT rule (plain "VAT" / "TVA").

## Delete lines
- **1 · Trial Balance → 🗑️ Delete lines** (new tab): lines with 0 (or nothing) in every year listed, all ticked —
  untick to keep, delete in one click; any other line can be chosen and deleted (warning that the totals change,
  confirmation required).
- **2 · Checks & Corrections → 🛠️ Quick fixes** also offers the zero-line deletion (tab title shows the count);
  the Line issues tab points to it.
- **↩️ UNDO THE LAST DELETION** restores the TB as it was just before.

## Upload
- Column detection prefers a column titled exactly "CIT code" over a ledger "Code" column, and "Account name" /
  "Description" over "Account code" / "Account No." — so a TB returned by an AI (ledger code + CIT code) is mapped
  correctly.

## Tests
- 27 tests (4 new): balance-direction suggestions and confidence, zero-line detection and deletion, AI prompt
  completeness and re-upload of an AI-mapped TB, page test of the mapping (pre-tick, apply) and deletion with undo.
