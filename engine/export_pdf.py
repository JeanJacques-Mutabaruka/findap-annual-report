#!/usr/bin/env python3
"""
export_pdf.py — convert the generated .docx to PDF with the table of contents and page fields refreshed
(LibreOffice UNO). The .docx itself is NOT modified: Word refreshes its TOC on opening (updateFields=true).

Usage: python export_pdf.py report.docx [report.pdf]
Needs LibreOffice (soffice) with its python-uno bridge. Falls back to a plain conversion (stale TOC) if UNO fails.
"""
import os, shutil, subprocess, sys, tempfile, time
from pathlib import Path


def soffice_env():
    env = os.environ.copy()
    env["SAL_USE_VCLPLUGIN"] = "svp"
    for cand in ("/mnt/skills/public/docx/scripts",):
        if Path(cand, "office", "soffice.py").exists():
            sys.path.insert(0, cand)
            try:
                from office.soffice import get_soffice_env
                env = get_soffice_env()
            except Exception:
                pass
    return env


def find_soffice():
    """soffice executable on PATH or in the usual Windows / macOS install folders (None if absent)."""
    for name in ("soffice", "libreoffice"):
        if shutil.which(name):
            return shutil.which(name)
    for cand in (r"C:\Program Files\LibreOffice\program\soffice.exe",
                 r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                 "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if Path(cand).exists():
            return cand
    return None


def export(docx, pdf):
    soffice = find_soffice()
    if soffice is None:
        raise FileNotFoundError("LibreOffice (soffice) not found — install it to produce PDFs, or open the .docx in Word and save as PDF.")
    docx, pdf = Path(docx).resolve(), Path(pdf).resolve()
    profile = tempfile.mkdtemp(prefix="lo_uno_")
    port = 2002 + os.getpid() % 500
    try:
        import uno  # noqa: F401  (LibreOffice python bridge; absent in most venvs -> plain conversion)
        has_uno = True
    except ImportError:
        has_uno = False
    if not has_uno:
        return _plain(soffice, docx, pdf)
    proc = subprocess.Popen([soffice, f"-env:UserInstallation={Path(profile).as_uri()}", "--headless", "--invisible",
                             "--nologo", "--norestore", f"--accept=socket,host=127.0.0.1,port={port};urp;"],
                            env=soffice_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import uno
        from com.sun.star.beans import PropertyValue
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        ctx = None
        for _ in range(60):
            try:
                ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
                break
            except Exception:
                time.sleep(0.5)
        if ctx is None:
            raise RuntimeError("could not connect to soffice")
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)

        def pv(n, v):
            p = PropertyValue(); p.Name = n; p.Value = v; return p

        doc = desktop.loadComponentFromURL(docx.as_uri(), "_blank", 0, (pv("Hidden", True),))
        for _ in range(2):  # twice: page numbers change once the TOC length changes
            idx = doc.getDocumentIndexes()
            for i in range(idx.getCount()):
                idx.getByIndex(i).update()
            doc.getTextFields().refresh()
            doc.refresh()
        doc.storeToURL(pdf.as_uri(), (pv("FilterName", "writer_pdf_Export"),))
        doc.close(True)
        print(f"PDF (TOC refreshed): {pdf}")
        return True
    except Exception as e:
        print(f"UNO export failed ({e}); falling back to plain conversion (TOC may be stale)")
        return _plain(soffice, docx, pdf)
    finally:
        try:
            proc.terminate(); proc.wait(10)
        except Exception:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


def _plain(soffice, docx, pdf):
    """Plain headless conversion: the TOC keeps the template's page numbers (Word refreshes the .docx)."""
    docx, pdf = Path(docx).resolve(), Path(pdf).resolve()
    out, prof = tempfile.mkdtemp(), tempfile.mkdtemp()
    subprocess.run([soffice, f"-env:UserInstallation={Path(prof).as_uri()}", "--headless",
                    "--convert-to", "pdf", "--outdir", out, str(docx)], env=soffice_env(),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)
    produced = Path(out) / (docx.stem + ".pdf")
    if not produced.exists():
        raise RuntimeError("LibreOffice did not produce a PDF")
    shutil.move(str(produced), pdf)
    shutil.rmtree(prof, ignore_errors=True)
    return False


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else str(Path(src).with_suffix(".pdf"))
    export(src, dst)
