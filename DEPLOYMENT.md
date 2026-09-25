# Deploying the Annual Report Generator for testers

## Quick route — manual upload to a GitHub repository (no Git needed)

1. github.com → **New** → name (e.g. `findap-annual-report-generator`) → Public or Private → tick **nothing**
   → **Create repository**.
2. On the empty repository page: **uploading an existing file**. Open the unzipped `annual-report-app` folder
   in Windows Explorer, select **everything inside it** (Ctrl+A — including the folders `.streamlit` and
   `.github`) and drag it into the browser. The folder `app` must end up at the **root** of the repository
   (not inside another `annual-report-app` folder). GitHub accepts up to 100 files per upload: if it refuses,
   upload in two batches (e.g. `app`, `engine`, `data`, `templates` first, then the rest).
3. **Commit changes**. Check that `app/Home.py`, `requirements.txt`, `packages.txt` and `.streamlit/config.toml`
   are at the root level shown by GitHub.
4. Continue with **Part 3** below (Streamlit Community Cloud). To update later: open the file on GitHub →
   ✏️ edit, or *Add file → Upload files* with the changed files (same paths) → Commit; the app redeploys.
5. **Templates**: to add one, open `templates/` on GitHub → *Add file → Upload files* → drag the template
   folder (e.g. `audit-company-01` containing `template.json` + `template.docx`) → Commit.

**Public repository:** anyone can read the code, the chart of CIT codes, the demo data and the Word
templates. An app deployed from a public repository is normally public as well — check in **Share**
whether "Only specific people can view this app" is offered; if not, anyone with the link can open it.
No data is stored by the app, but do not put client names or client documents in the repository.

---


GitHub (private code) → Streamlit Community Cloud (online app) → invited testers.

Time needed: about **45 minutes** the first time, then **1 minute** per update.

```
Your PC (tested with run.bat)
      │  github_first_push.bat  (once)  /  github_update.bat  (each change)
      ▼
GitHub — PRIVATE repository  (code only, never client data)
      │  automatic redeploy on every push
      ▼
Streamlit Community Cloud — https://<your-name>.streamlit.app
      │  Sharing: "Only specific people can view this app"
      ▼
Testers — invited by e-mail, sign in with Google or an e-mailed link
```

---

## Part 1 — Pre-flight check (on your PC, 10 min)

1. Run `run.bat` and click through the 2-year and 5-year demos: every page opens, a DRAFT report is generated.
2. Run the automatic tests (in the project folder, from a terminal):
   ```
   .venv\Scripts\python.exe -m pip install pytest
   .venv\Scripts\python.exe -m pytest -q
   ```
   Expected: `19 passed`. `github_update.bat` runs them again before every update.
3. Check that the folder contains **no client file** (TB, reports, `*_project.json`). Only the demo data
   in `data/demo/` is allowed. `.gitignore` already excludes `.venv/`, `.streamlit/secrets.toml`,
   `*_input.json`, `*_model.json` and `output/`.
4. Decide the **version name** shown to testers (in `engine/__init__.py`, `VERSION = "V1-0e"`).
5. Prepare the **feedback form** (Part 6) — you will paste its link in Part 4.

---

## Part 2 — GitHub: private repository and first upload (15 min)

### 2.1 Account
Create or use your account on <https://github.com>. Turn on two-factor authentication
(avatar → Settings → Password and authentication) — recommended for a repository that holds your tool.

### 2.2 Create an EMPTY private repository
1. **+** (top right) → **New repository**.
2. Name: `annual-report-app`. Description: *Annual report generator (TB → Word / PDF)*.
3. Select **Private**.
4. Leave **all** "Initialize this repository with" boxes **unticked** (no README, no .gitignore, no licence).
5. **Create repository**. Copy the address shown, e.g. `https://github.com/your-username/annual-report-app.git`.

### 2.3 Install Git (once)
<https://git-scm.com/download/win> → install with the default options. They include *Git Credential
Manager*, which opens your browser to sign in to GitHub the first time you upload — no token to create.

### 2.4 First upload — one click
Double-click **`github_first_push.bat`** in the project folder:
- first time only, it asks your name and e-mail for the history;
- it asks the repository address (paste it from 2.2);
- a browser window may open: sign in to GitHub and authorise;
- at the end, refresh the repository page: the files are there. **Check that `.venv` is not listed.**

<details><summary>Manual alternative (same result)</summary>

```
git init
git add .
git commit -m "Annual Report Generator - first version for testers"
git branch -M main
git remote add origin https://github.com/your-username/annual-report-app.git
git push -u origin main
```
</details>

---

## Part 3 — Streamlit Community Cloud: put the app online (10 min + build)

1. <https://share.streamlit.io> → **Continue with GitHub**. When asked, **authorise access to private
   repositories** (otherwise your private repository will not appear in the list).
2. **Create app** → **Deploy a public app from GitHub**.
   *"Public" here only means "reachable by URL" — you restrict who can view it in Part 4.*
3. Fill in:
   | Field | Value |
   |---|---|
   | Repository | `your-username/annual-report-app` |
   | Branch | `main` |
   | Main file path | `app/Home.py` |
   | App URL | choose a short sub-domain, e.g. `arg-convergencium` → `https://arg-convergencium.streamlit.app` |
4. **Advanced settings**:
   - **Python version: 3.12**
   - **Secrets** — paste (with your real form link):
     ```toml
     tester_mode = true
     feedback_url = "https://forms.gle/your-form"
     ```
     `tester_mode` shows *"TEST VERSION … use the demo or anonymised data only"* in the sidebar;
     `feedback_url` adds a **💬 Send feedback** button on every page.
5. **Deploy**. The first build takes **5–10 minutes**: `packages.txt` installs LibreOffice (for the PDFs)
   and the fonts Caladea / Carlito (metric-compatible with Cambria / Calibri, so the PDF pages break like in Word).
6. When the app opens: load the 2-year demo, generate a DRAFT with the PDF box ticked, download the ZIP and
   check the Word and PDF files.

**If the build is too slow or fails on LibreOffice:** empty `packages.txt`, push again (`github_update.bat`).
The app then produces Word only; the PDF box is greyed out with an explanation.

---

## Part 4 — Restrict access and invite the testers (5 min)

1. Open the app → **Share** (top right) — or *App settings → Sharing*.
2. **Who can view this app → "Only specific people can view this app".**
   An app deployed from a private repository is private by default; check it anyway.
3. Enter each tester's e-mail → **Invite**. Each tester receives an e-mail with the link.
4. Testers sign in with **Google** if their address is a Google account, otherwise with a **single-use link
   sent by e-mail**. They do not need a GitHub account.

Good to know:
- The free Community Cloud plan limits the number of **private** apps per account (one, historically).
  Keep this app as your private one, or check the current limit in your workspace.
- If an invited tester loops between two Streamlit pages after signing in: remove and re-invite them, or
  switch the app to public and back to private — a known glitch reported by other users.
- You can remove a tester at any time from the same screen.

---

## Part 5 — Onboard the testers

Send each tester:
1. the app address;
2. **`TESTERS_GUIDE.md`** (or its PDF) — 10 test scenarios with the expected result;
3. the ground rules: **demo or anonymised data only**, download the project file before closing the tab,
   report every problem with the 💬 button.

Suggested WhatsApp / e-mail message:

> Hello — thank you for testing the **Annual Report Generator** (test version V1-0e).
> Link: https://arg-convergencium.streamlit.app — sign in with the e-mail address this message was sent to.
> Start with *Home → LOAD DEMO — 2 YEARS*, then follow the attached guide (about 45 minutes).
> Please use only the demo or anonymised trial balances. Report anything odd with the 💬 button in the
> left menu (a screenshot helps a lot). Deadline for feedback: <date>.

---

## Part 6 — Collect the feedback

Recommended: a **Google Form** (free; testers do not need any account). Suggested questions:

1. Your name *(short text)*
2. Version shown in the sidebar *(short text, e.g. V1-0e)*
3. Page *(list: Home · 1 Trial Balance · 2 Checks & Corrections · 3 Company & Report Data · 4 Statements Preview · 5 Generate & Download · Word report · PDF)*
4. Type *(list: Bug / error message · Wrong figure · Unclear text or screen · Missing feature · Suggestion)*
5. What did you do, step by step? *(paragraph)*
6. What happened, and what did you expect? *(paragraph)*
7. Screenshot or file *(file upload — requires testers to sign in with Google; otherwise ask them to send it by e-mail)*
8. Severity *(1 = cosmetic … 4 = blocks my work)*
9. Scenario number from the testers' guide *(optional)*

Link the form's responses to a Google Sheet: it becomes your bug list. Paste the form link into the app
Secrets (`feedback_url`) — no redeploy needed, the app restarts by itself.

GitHub **Issues** (templates in `.github/ISSUE_TEMPLATE/`) are for you and any developer you add as a
collaborator; testers without GitHub access cannot see a private repository's issues.

---

## Part 7 — Updating the app during the test phase

1. Change the code on your PC, test with `run.bat`, raise `VERSION` in `engine/__init__.py`
   (V1-0e → V1-0f) and add a `CHANGES_V1-0f.md`.
2. Double-click **`github_update.bat`** — it runs the automatic tests first and **sends nothing if a test
   fails**; then it asks a short description and uploads.
3. Streamlit Cloud redeploys within 1–2 minutes. Testers see the new version number in the sidebar.
4. Tell the testers what changed (copy the CHANGES file into your message).

Sessions of people using the app at that moment are reset — announce updates, or push outside working hours.

Optional: mark each tested version on GitHub (*Releases → Draft a new release → tag `v1-0e`*) so you can
return to it.

---

## Part 8 — Operating the online app

| Topic | What to know |
|---|---|
| Sleep | An app without visitors for a while goes to sleep; the next visitor sees a *"wake up"* button and waits about a minute. |
| Resources | Community Cloud apps have limited memory and CPU. Generating every year pair **with PDFs** is the heaviest action — if it is slow, generate Word first, PDFs for one year at a time. |
| Logs | *Manage app* (bottom right of the app, visible to you) → logs of errors. |
| Reboot | *Manage app → Reboot app* if the app misbehaves after an update. |
| Secrets | *App settings → Secrets* — change `tester_mode` / `feedback_url` without touching the code. |
| Data | Nothing is stored on the server. Files exist only in the tester's browser session until downloaded. |
| Table of contents in PDF | On the cloud the PDF may keep the template's page numbers in the table of contents; the Word file is refreshed by Word ("Update fields" → Yes). |

---

## Part 9 — Troubleshooting

| Symptom | Fix |
|---|---|
| `github_first_push.bat`: "failed to push" | The repository was not empty (created with a README): delete and recreate it empty, or ask for help to merge. |
| Private repository not listed on share.streamlit.io | In your Community Cloud account settings, re-authorise GitHub and allow access to private repositories. |
| Build error "Error installing requirements" | *Manage app → logs*; check that `requirements.txt` is at the root of the repository. |
| Build stuck on apt / LibreOffice | Empty `packages.txt`, push, reboot. |
| `ModuleNotFoundError: app` or `engine` | Main file path must be `app/Home.py` (not `Home.py`). |
| Tester: "You do not have access" | Check the e-mail invited is the one they sign in with; re-invite. |
| Tester: upload refused | File above 50 MB — raise `maxUploadSize` in `.streamlit/config.toml`. |
| PDF missing after generation | Look at the message under *Generate*; LibreOffice may have timed out — retry with one year. |

---

## Part 10 — Security checklist before inviting testers

- [ ] Repository is **Private**; `.venv` and `secrets.toml` are not in it.
- [ ] No client data in the repository (search the repository for a client name).
- [ ] App sharing = **Only specific people**; the invited list is correct.
- [ ] `tester_mode = true` in Secrets (banner visible in the sidebar).
- [ ] Feedback button works (click it once).
- [ ] Demo generation with PDF works on the online app.
- [ ] Testers received the guide and the data rule (demo / anonymised only).
