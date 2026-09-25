# V1-0e — ready for testers (deployment)

## Deployment
- `DEPLOYMENT.md` rewritten: pre-flight check, private GitHub repository, Streamlit Community Cloud
  (Python 3.12, Secrets), access restricted to invited testers, onboarding message, feedback form,
  updates during the test phase, operations, troubleshooting, security checklist.
- `github_first_push.bat` (first upload, once) and `github_update.bat` (runs the tests, then uploads;
  sends nothing if a test fails).
- `TESTERS_GUIDE.md`: 10 scenarios (~45 min) with expected results, rules on data, known limitations.
- `.github/ISSUE_TEMPLATE/`: bug report and improvement templates (for you and collaborators).

## App
- Optional **tester mode** and **💬 Send feedback** button, driven by Streamlit *Secrets*
  (`tester_mode`, `feedback_url` or `feedback_email`) — see `.streamlit/secrets.toml.example`.
- `requirements.txt` with tested version ranges; `packages.txt` adds the Caladea / Carlito fonts
  (Cambria / Calibri metrics) so online PDFs paginate like Word.
