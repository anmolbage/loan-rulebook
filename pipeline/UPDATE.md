# Weekly update procedure (run by the scheduled task)

Working folder: the `_LoanRulebook` project folder (parent of this `pipeline` folder).
Everything under `private/` is plaintext and gitignored; never commit it. Only `docs/` is published.

1. **Extract.** Run `python -W ignore pipeline/extract.py` (set `PYTHONIOENCODING=utf-8`).
   It writes `private/new_this_run.json` (ids of new or changed circulars).
   If the list is empty, stop and report "No new circulars".

2. **Triage.** For each new id, look it up in `private/manifest.json` and read `private/text/<id>.txt`
   (if `method` is `scanned`, read the original PDF at `<circulars folder>/<rel>` with the Read tool).
   Decide whether it affects lending: a loan product, ROI/MCLR/EBLR, processing fees, gold value,
   the loan policy, delegation of powers, CIBIL, documentation, a campaign or concession, or a guarantee scheme.
   Ignore HR, holidays, suspensions and similar.

3. **Update the rules** for every lending-relevant circular, following `pipeline/SCHEMA.md` exactly:
   - Edit the affected `private/products/<id>.json`. When a rule changes, put the new text first and move
     the old text, with its citations, into `superseded`. Update `checks` if a number changed. Add the
     circular to `governing`.
   - For a new scheme, create a new product file.
   - For a monthly gold-value letter, add the month to the top of `private/products/_gold_values.json`
     (a "revised" letter replaces the same month).
   - For an MCLR/EBLR/base-rate letter, move the current values of `private/products/_rates.json` into
     `history` and write the new ones.
   - Mark rules that come from a scanned or unclear source with `"confidence": "low"`.
   - Validate every JSON file you touched with `python -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" <file>`.

4. **Changelog.** Add an entry at the top of `private/changelog.json` (create `[]` if missing):
   `{"date":"YYYY-MM-DD","summary":"one line in plain English","products":["ids changed"],"circulars":["new ids that mattered"]}`.

5. **Build and publish.** Run `python pipeline/publish.py`. It rebuilds the encrypted files and pushes `docs/` to GitHub.
   If it prints PROBLEMS, fix the product files and run it again.

6. **Report** in 3-5 lines: how many new circulars, which products changed, and anything marked low confidence.
