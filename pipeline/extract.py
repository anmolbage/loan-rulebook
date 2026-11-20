#!/usr/bin/env python3
"""Incremental full-text extraction of every circular in the parent folder.
Writes private/text/<id>.txt (with === PAGE n === markers) and private/manifest.json.
Only new/changed files (by size+mtime) are processed. Scanned PDFs get method='scanned'
(no OCR engine needed: the AI step reads those PDFs visually)."""
import os, re, json, hashlib, sys, time
import pymupdf
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
ROOT = os.path.dirname(PROJ)                      # the circulars folder
PRIV = os.path.join(PROJ, "private")
TEXT = os.path.join(PRIV, "text")
MANIFEST = os.path.join(PRIV, "manifest.json")
SKIP_DIRS = {"_LoanRulebook", "_JGB_pipeline", "ROUGH"}
EXTS = (".pdf", ".docx")

def fid(rel):
    return hashlib.sha1(rel.replace("\\", "/").encode("utf-8")).hexdigest()[:12]

def walk():
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if f.lower().endswith(EXTS):
                yield os.path.join(d, f)

def meta_from_name(fn, rel):
    u = fn.upper()
    typ = "Circular Letter" if ("LETTER" in u) else ("Circular" if "CIRCULAR" in u else "Document")
    m = re.search(r"N[Oo]\.?\s*[-–:.]?\s*0*(\d{1,4})", fn)
    num = m.group(1) if m else ""
    top = rel.replace("\\", "/").split("/")[0]
    fy = top if re.fullmatch(r"\d{4}-\d{4}", top) else ("2022-2023" if "2022-2023" in top else top)
    return typ, num, fy

DATE_RE = re.compile(r"(?:dated?|date)\s*[:\-]?\s*(\d{1,2})[./-](\d{1,2})[./-](20\d{2})", re.I)
ANY_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b")

def find_date(fn, text):
    for rx, s in ((DATE_RE, text[:3000]), (ANY_DATE, fn), (ANY_DATE, text[:1500])):
        m = rx.search(s)
        if m:
            d, mo, y = map(int, m.groups())
            if 1 <= d <= 31 and 1 <= mo <= 12:
                return f"{y:04d}-{mo:02d}-{d:02d}"
    return ""

def extract(path):
    if path.lower().endswith(".docx"):
        import docx
        doc = docx.Document(path)
        parts = [p.text for p in doc.paragraphs]
        for t in doc.tables:
            for r in t.rows:
                parts.append(" | ".join(c.text.strip() for c in r.cells))
        return "=== PAGE 1 ===\n" + "\n".join(parts), 1
    with pymupdf.open(path) as pdf:
        out = []
        for i, page in enumerate(pdf, 1):
            out.append(f"=== PAGE {i} ===\n" + page.get_text("text"))
        return "\n".join(out), len(pdf)

def main():
    man = {}
    if os.path.exists(MANIFEST):
        man = {e["id"]: e for e in json.load(open(MANIFEST, encoding="utf-8"))}
    seen, new, t0 = set(), [], time.time()
    for p in walk():
        rel = os.path.relpath(p, ROOT)
        i = fid(rel); seen.add(i)
        st = os.stat(p); sig = f"{st.st_size}-{int(st.st_mtime)}"
        if i in man and man[i].get("sig") == sig:
            continue
        try:
            text, pages = extract(p)
            body = re.sub(r"=== PAGE \d+ ===", "", text).strip()
            method = "text" if len(body) >= 60 * max(1, pages) * 0.3 else "scanned"
        except Exception as ex:
            text, pages, method = "", 0, f"error:{type(ex).__name__}"
        open(os.path.join(TEXT, i + ".txt"), "w", encoding="utf-8").write(text)
        fn = os.path.basename(p)
        typ, num, fy = meta_from_name(fn, rel)
        man[i] = {"id": i, "rel": rel.replace("\\", "/"), "filename": fn, "fy": fy, "type": typ,
                  "number": num, "date": find_date(fn, text), "pages": pages, "method": method,
                  "chars": len(text), "sig": sig, "added": time.strftime("%Y-%m-%d"),
                  "title": re.sub(r"\s+", " ", os.path.splitext(fn)[0]).strip()}
        new.append(i)
    for gone in set(man) - seen:
        man[gone]["deleted"] = True
    json.dump(sorted(man.values(), key=lambda e: e["rel"]), open(MANIFEST, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    json.dump(new, open(os.path.join(PRIV, "new_this_run.json"), "w"))
    print(f"new/changed: {len(new)} | total: {len(man)} | {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
