#!/usr/bin/env python3
"""Meldet alle URLs aus sitemap.xml an IndexNow (Bing, Yandex, Seznam, Naver, Yep)."""
import json, re, urllib.request, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEY = "803ef1414c5142e3b334328516165326"
urls = re.findall(r"<loc>([^<]+)</loc>", open("sitemap.xml").read())
body = json.dumps({"host": "achimmentzen.github.io", "key": KEY,
                   "keyLocation": f"https://achimmentzen.github.io/{KEY}.txt", "urlList": urls}).encode()
for ep in ["https://api.indexnow.org/indexnow", "https://www.bing.com/indexnow", "https://yandex.com/indexnow"]:
    try:
        r = urllib.request.urlopen(urllib.request.Request(ep, data=body, headers={"Content-Type": "application/json; charset=utf-8"}), timeout=30)
        print(ep, r.status, len(urls), "URLs")
    except Exception as e:
        print(ep, "Fehler:", e)
