"""6 · Templates — see, download and choose the Word templates (managed by the administrator)."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import state  # noqa: E402
from app.downloads import download_button  # noqa: E402
from app.style import info_banner, ok_banner, red_alert, warn_banner  # noqa: E402
from engine import CHART, DEMO, build_model, export_pdf, preview, render_report, templates  # noqa: E402

state.init_state()
state.page_setup("🗂️ Templates")

tlist = templates.list_templates()
cur = state.current_template()
m = state.project()["meta"]
info_banner("Word templates available for the annual report. Templates are added or changed by the "
            "administrator only; here you can look at them, download them and choose the one for your project. "
            f"Current choice: <b>{cur['alias'] if cur else '—'}</b> · font: <b>{m.get('font_name') or 'template fonts'}</b>.")
if not tlist:
    red_alert("No template found in the templates/ folder.")
    st.stop()


@st.cache_data(show_spinner=False)
def sample(docx_path: str, notes_path: str | None, font: str | None) -> bytes:
    """The template filled with the 2-year demo data (DRAFT), to see how a finished report looks."""
    d = json.loads(DEMO.read_text(encoding="utf-8"))
    notes = json.loads(Path(notes_path).read_text(encoding="utf-8")) if notes_path else state.notes_default()
    mdl = build_model.build(d, json.loads(CHART.read_text(encoding="utf-8")), notes)
    out = io.BytesIO()
    render_report.render(docx_path, mdl, out, allow_blocking=True, font_name=font)
    return out.getvalue()


tabs = st.tabs([("✅ " if cur and t["id"] == cur["id"] else "") + t["alias"] for t in tlist])
for tab, t in zip(tabs, tlist):
    with tab:
        if t["error"]:
            red_alert(t["error"])
            continue
        st.markdown(t["description"] or "")
        if t.get("preview"):
            st.image(str(t["preview"]), caption="Preview with the demo data — cover · corporate information · "
                     "statement of comprehensive income · first notes (click the image to enlarge). "
                     "Fonts not installed on the server are shown with a close substitute.", width="stretch")
        elif export_pdf.find_soffice():
            if st.button("🖼️ Build a preview", key=f"arg_tpl_prev_{t['id']}"):
                with st.spinner("Filling the template and taking pictures of 4 pages…"):
                    try:
                        st.session_state[f"arg_tpl_prev_{t['id']}"] = preview.preview_png(
                            preview.sample_docx(t["docx"], t["notes"], t["default_font"]))
                    except Exception as e:  # noqa: BLE001
                        st.warning(f"Preview not available: {e}")
            if st.session_state.get(f"arg_tpl_prev_{t['id']}"):
                st.image(st.session_state[f"arg_tpl_prev_{t['id']}"], width="stretch")
        else:
            st.caption("No preview picture for this template yet (the administrator can add preview.png).")
        c = st.columns(4)
        c[0].metric("Version", t["version"] or "—")
        c[1].metric("Language", (t["language"] or "").upper())
        chk = templates.check(t["docx"])
        c[2].metric("Default font", t["default_font"] or chk["main_font"])
        c[3].metric("Notes", "own notes" if t["notes"] else "standard")
        if chk["ok"]:
            ok_banner("Compatible with the generator: the 4 statement tables and the notes block are in place.")
        else:
            red_alert("Not fully compatible: " + "; ".join(chk["problems"]))
        with st.expander("Details (for the administrator)"):
            st.markdown("**Fields printed:** " + (", ".join(chk["fields"]) or "none"))
            st.markdown("**Statement tables:** " + ", ".join(chk["tables"]))
            if chk["unknown"]:
                warn_banner("Bookmarks not recognised (ignored): " + ", ".join(chk["unknown"]))
            if chk["loose_placeholders"]:
                warn_banner("Text in braces outside any bookmark (will stay as typed): " + ", ".join(chk["loose_placeholders"]))
            st.caption(f"Folder: templates/{t['id']}/ · notes: {'own notes.json' if t['notes'] else 'default notes'} · "
                       f"{len(chk['fields'])} printed fields. To rename this template, edit \"alias\" in "
                       f"templates/{t['id']}/template.json on GitHub.")
        b1, b2, b3 = st.columns(3)
        with b1:
            download_button("⬇️ Download the template (.docx)", Path(t["docx"]).read_bytes(),
                            f"Template_{t['id']}.docx", key=f"arg_tpl_dl_{t['id']}")
        with b2:
            dlab = f"Template default ({t['default_font'] or 'fonts of the Word file'})"
            font = st.selectbox("Font for the sample", [dlab] + templates.FONTS, key=f"arg_tpl_font_{t['id']}",
                                label_visibility="collapsed")
            if st.button("🧪 Prepare a sample with the demo data", key=f"arg_tpl_mk_{t['id']}", width="stretch"):
                with st.spinner("Filling the template with the demo data…"):
                    st.session_state[f"arg_tpl_sample_{t['id']}"] = sample(str(t["docx"]), str(t["notes"]) if t["notes"] else None,
                                                                             t["default_font"] if font == dlab else font)
            if st.session_state.get(f"arg_tpl_sample_{t['id']}"):
                download_button("⬇️ Download the sample (.docx)", st.session_state[f"arg_tpl_sample_{t['id']}"],
                                f"Sample_{t['id']}.docx", key=f"arg_tpl_sdl_{t['id']}", primary=True)
        with b3:
            if cur and t["id"] == cur["id"]:
                st.button("✅ Template of this project", disabled=True, width="stretch", key=f"arg_tpl_cur_{t['id']}")
            elif st.button("✔️ Use this template", key=f"arg_tpl_use_{t['id']}", type="primary", width="stretch"):
                m["template_id"] = t["id"]
                state.mark_dirty()
                st.rerun()
