#!/usr/bin/env python3
"""Rebuild encrypted site data and push docs/ to GitHub (GitHub Pages serves /docs)."""
import os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)

def run(*cmd, check=True):
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, cwd=PROJ, text=True, capture_output=True)
    print(r.stdout.strip()); print(r.stderr.strip())
    if check and r.returncode:
        sys.exit(r.returncode)
    return r

run(sys.executable, "-W", "ignore", os.path.join(HERE, "build.py"))
# safety: refuse to publish if anything under private/ is tracked
tracked = run("git", "ls-files", "private").stdout.strip()
if tracked:
    sys.exit("ABORT: private/ files are tracked by git:\n" + tracked)
run("git", "add", "docs", "pipeline", ".gitignore", ".gitattributes", "README.md")
if run("git", "diff", "--cached", "--quiet", check=False).returncode == 0:
    print("Nothing changed."); sys.exit(0)
run("git", "commit", "-m", f"Data update {time.strftime('%Y-%m-%d')}")
run("git", "push")
