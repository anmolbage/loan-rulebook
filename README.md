# Loan Rulebook

A password-protected reference for loan product rules, with each rule citing its source circular.

- `docs/`: the site served by GitHub Pages. Bank content is stored only as AES-256-GCM encrypted files (`data.enc`, `search.enc`) and is decrypted in the browser with the access password.
- `pipeline/`: extraction, build and publish scripts. The plaintext working data lives in `private/`, which is never committed.

Weekly update: `pipeline/UPDATE.md`. Manual rebuild: `python pipeline/publish.py`.
