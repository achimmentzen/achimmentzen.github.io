#!/usr/bin/env python3
"""Erzeugt sitemap.xml aus allen HTML-Seiten (lastmod = letzter Git-Commit)."""
import os, subprocess, re
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = "https://achimmentzen.github.io/"
files = subprocess.run(["git", "ls-files", "*.html"], capture_output=True, text=True).stdout.split()
urls = []
for f in sorted(files):
    if f.startswith((".github/", "tools/")) or f.startswith("google"):
        continue
    s = open(f, encoding="utf-8", errors="ignore").read(4000).lower()
    if 'name="robots" content="noindex' in s or 'http-equiv="refresh"' in s:
        continue
    d = subprocess.run(["git", "log", "-1", "--format=%cs", "--", f], capture_output=True, text=True).stdout.strip() or "2026-10-28"
    loc = BASE + (f[:-10] if f.endswith("index.html") else f)
    depth = loc.count("/") - 3
    prio = "1.0" if loc == BASE else ("0.8" if depth <= 1 else "0.6")
    urls.append(f"  <url><loc>{loc}</loc><lastmod>{d}</lastmod><priority>{prio}</priority></url>")
open("sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n")
subprocess.run(["git", "add", "sitemap.xml"])
print(len(urls), "URLs")
