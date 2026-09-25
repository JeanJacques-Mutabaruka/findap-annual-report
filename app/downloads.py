"""Download helpers (one place for file names and MIME types)."""
from __future__ import annotations

import streamlit as st

MIME = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pdf": "application/pdf",
    ".json": "application/json",
    ".md": "text/markdown",
    ".zip": "application/zip",
}


def mime_for(name: str) -> str:
    for ext, m in MIME.items():
        if name.lower().endswith(ext):
            return m
    return "application/octet-stream"


def download_button(label: str, data: bytes, filename: str, key: str, primary: bool = False) -> None:
    st.download_button(label, data=data, file_name=filename, mime=mime_for(filename), key=key,
                       type="primary" if primary else "secondary", width="stretch")
