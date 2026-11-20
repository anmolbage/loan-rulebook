#!/usr/bin/env python3
"""Build the encrypted site data.

Reads  private/products/*.json, private/manifest.json, private/text/*.txt, private/password.txt
Writes docs/data.enc   (products + circular index + rates + gold + changelog)
       docs/search.enc (full text of circulars, lazy-loaded for search / reading)
       docs/version.json (public: build time + counts only, no bank content)

Encryption: PBKDF2-SHA256 (310k iterations) -> AES-256-GCM, gzip inside.
File layout: b"JRB1" | salt(16) | iv(12) | ciphertext+tag
"""
import os, re, json, gzip, glob, time, secrets, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
PRIV = os.path.join(PROJ, "private")
DOCS = os.path.join(PROJ, "docs")
ITER = 310000

# circulars that add bulk but never matter for loan proposals (still kept in the index, just not full text)
NOISE = re.compile(r"seniority|suspension|holiday|strike|investment declaration|tds|posting|transfer of officers|"
                   r"promotion (result|list)|results? of|medical insurance|lodging|mileage|ltc|leave|vacation|"
                   r"sexual harassment|dress code|attendance|annexure|slippage|due for renewal|audit observation", re.I)
MAX_UNCITED_PAGES = 40   # long uncited documents are mostly account lists; keep only the guidance pages

def load(p, default=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError:
        return default

def enc(obj, password, path):
    raw = gzip.compress(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    salt, iv = secrets.token_bytes(16), secrets.token_bytes(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(password.encode())
    ct = AESGCM(key).encrypt(iv, raw, None)
    open(path, "wb").write(b"JRB1" + salt + iv + ct)
    return len(raw)

def _fy(y): return f"{y}-{y+1}"
_t = time.localtime(); _cur = _t.tm_year if _t.tm_mon >= 4 else _t.tm_year - 1
PDF_YEARS = {_fy(_cur), _fy(_cur - 1)}   # rolling: current + previous FY uploaded in full, plus every cited circular

def sync_pdfs(man, cited, password):
    """Encrypt selected original PDFs into docs/pdf/<id>.enc (AES-256-GCM, key = PBKDF2(password, fixed salt)).
    Incremental: a file is re-encrypted only when the source or the password changes."""
    import hashlib
    root = os.path.dirname(PROJ)
    keyf = os.path.join(PRIV, "pdf_key.json")
    kd = load(keyf) or {"salt": secrets.token_hex(16)}
    salt = bytes.fromhex(kd["salt"])
    pwh = hashlib.sha256(salt + password.encode()).hexdigest()
    if kd.get("pwhash") != pwh:
        kd = {"salt": kd["salt"], "pwhash": pwh}; json.dump(kd, open(keyf, "w"))
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(password.encode())
    statef = os.path.join(PRIV, "pdf_state.json"); state = load(statef, {})
    outdir = os.path.join(DOCS, "pdf"); os.makedirs(outdir, exist_ok=True)
    want = [e for e in man if e["rel"].lower().endswith(".pdf")
            and (e["id"] in cited or (e["fy"] in PDF_YEARS and not NOISE.search(e["title"])))]
    keep, done, total = set(), 0, 0
    for e in want:
        src = os.path.join(root, e["rel"]); dst = os.path.join(outdir, e["id"] + ".enc")
        tag = f"{e['sig']}|{pwh}"; keep.add(e["id"] + ".enc")
        if state.get(e["id"]) != tag or not os.path.exists(dst):
            raw = open(src, "rb").read()
            iv = secrets.token_bytes(12)
            open(dst, "wb").write(b"JRP1" + iv + AESGCM(key).encrypt(iv, raw, None))
            state[e["id"]] = tag; done += 1
        total += os.path.getsize(dst)
    for f in os.listdir(outdir):
        if f not in keep:
            os.remove(os.path.join(outdir, f)); state.pop(f[:-4], None)
    json.dump(state, open(statef, "w"))
    print(f"pdfs: {len(keep)} online ({total/1e6:.0f} MB), {done} (re)encrypted")
    return {"salt": kd["salt"], "ids": sorted(k[:-4] for k in keep)}

def label(e):
    t = "CL" if e["type"] == "Circular Letter" else ("Cir" if e["type"] == "Circular" else "Doc")
    n = f" {e['number']}" if e.get("number") else ""
    fy = e["fy"] if re.fullmatch(r"\d{4}-\d{4}", e["fy"]) else ""
    fy = f"/{fy[:4]}-{fy[7:]}" if fy else ""
    d = e.get("date") or ""
    d = f" dt {d[8:10]}.{d[5:7]}.{d[:4]}" if d else ""
    return f"{t}{n}{fy}{d}".strip()

def main():
    pw_file = os.path.join(PRIV, "password.txt")
    if not os.path.exists(pw_file):
        sys.exit("private/password.txt missing - put the site password in it (one line).")
    password = open(pw_file, encoding="utf-8").read().strip()
    man = [e for e in load(os.path.join(PRIV, "manifest.json"), []) if not e.get("deleted")]
    byid = {e["id"]: e for e in man}

    products, problems = [], []
    for f in sorted(glob.glob(os.path.join(PRIV, "products", "*.json"))):
        if os.path.basename(f).startswith("_"):
            continue
        try:
            p = json.load(open(f, encoding="utf-8"))
        except Exception as ex:
            problems.append(f"{os.path.basename(f)}: {ex}")
            continue
        def walk(o):
            if isinstance(o, dict):
                if "cid" in o and o["cid"] not in byid:
                    problems.append(f"{p.get('id')}: unknown cid {o['cid']}")
                for v in o.values(): walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        walk(p)
        products.append(p)

    cited = set()
    def collect(o):
        if isinstance(o, dict):
            if "cid" in o: cited.add(o["cid"])
            for v in o.values(): collect(v)
        elif isinstance(o, list):
            for v in o: collect(v)
    collect(products)

    circ = {e["id"]: {"l": label(e), "t": e["title"], "fy": e["fy"], "d": e.get("date", ""), "ty": e["type"],
                      "p": e["pages"], "r": e["rel"], "m": e["method"], "a": e.get("added", "")} for e in man}

    pdf = sync_pdfs(man, cited, password)
    data = {
        "built": time.strftime("%Y-%m-%d %H:%M"),
        "pdf": pdf,
        "products": products,
        "circulars": circ,
        "rates": load(os.path.join(PRIV, "products", "_rates.json")),
        "gold": load(os.path.join(PRIV, "products", "_gold_values.json"), []),
        "ratecard": load(os.path.join(PRIV, "products", "_ratecard.json")),
        "changelog": load(os.path.join(PRIV, "changelog.json"), []),
        "root": "E:\\OneDrive\\5. ALL CIRCULARS\\",
    }
    os.makedirs(DOCS, exist_ok=True)
    n1 = enc(data, password, os.path.join(DOCS, "data.enc"))

    texts = {}
    for e in man:
        if NOISE.search(e["title"]) and e["id"] not in cited:
            continue
        p = os.path.join(PRIV, "text", e["id"] + ".txt")
        if os.path.exists(p):
            t = open(p, encoding="utf-8").read()
            if e["id"] not in cited and e["pages"] > MAX_UNCITED_PAGES:
                cut = t.find(f"=== PAGE {MAX_UNCITED_PAGES + 1} ===")
                if cut > 0:
                    t = t[:cut] + f"\n[... remaining {e['pages'] - MAX_UNCITED_PAGES} pages omitted]"
            t = re.sub(r"[ \t\u00a0]+", " ", t)
            t = re.sub(r"\n\s*\n+", "\n", t).strip()
            if len(t) > 40:
                texts[e["id"]] = t
    n2 = enc(texts, password, os.path.join(DOCS, "search.enc"))

    json.dump({"built": data["built"], "products": len(products), "circulars": len(circ)},
              open(os.path.join(DOCS, "version.json"), "w"))
    print(f"products {len(products)} | circulars {len(circ)} | fulltext {len(texts)} | "
          f"data {n1/1e6:.2f}MB | search {n2/1e6:.2f}MB (gz)")
    if problems:
        print("PROBLEMS:\n  " + "\n  ".join(problems[:50]))

if __name__ == "__main__":
    main()
