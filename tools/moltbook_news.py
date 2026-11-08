#!/usr/bin/env python3
"""Holt alle Moltbook-Posts von achimmentzenagent samt Kommentaren und
Antworten über die öffentliche Moltbook-API und schreibt news.json.

Läuft stündlich als GitHub Action (.github/workflows/moltbook-news.yml),
braucht keinen API-Key und kein Claude-Guthaben.

Zusätzlich: Wenn GITHUB_TOKEN gesetzt ist, werden die giscus-IDs
(Repository und Discussion-Kategorie) per GraphQL ermittelt und in
news.json geschrieben, damit news.html die Kommentarfunktion lädt.
"""
import json, os, re, sys, time, urllib.request, urllib.parse

AGENT = "achimmentzenagent"
API = "https://www.moltbook.com/api/v1"
REPO = os.environ.get("GITHUB_REPOSITORY", "achimmentzen/achimmentzen.github.io")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "news.json")

# Grenzen des Projekts: Familie, Arbeitgeber, Straße/Hausnummer bleiben draußen.
# Enthält ein Post oder Kommentar einen dieser Begriffe, wird er nicht übernommen.
BLOCK = [
    r"bündten", r"buendten", r"südbadenbus", r"suedbadenbus", r"\bsbg\b",
    r"db regio", r"deutsche bahn", r"deutschebahn", r"ehefrau", r"meine frau",
    r"his wife", r"tochter", r"daughter", r"\bsohn\b", r"\bson\b",
]
BLOCK_RE = re.compile("|".join(BLOCK), re.I)


def get(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": "achimmentzen-news/1.0", "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(5)


def ok(text):
    return not BLOCK_RE.search(text or "")


def clean_comments(items):
    out = []
    for c in items or []:
        if c.get("is_deleted") or c.get("is_spam") or not ok(c.get("content")):
            continue
        out.append({
            "id": c["id"],
            "author": (c.get("author") or {}).get("name", "unbekannt"),
            "content": c.get("content", ""),
            "created_at": c.get("created_at"),
            "replies": clean_comments(c.get("replies")),
        })
    return out


def count(cs):
    return sum(1 + count(c["replies"]) for c in cs)


def giscus_ids():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    owner, name = REPO.split("/")
    q = {"query": 'query($o:String!,$n:String!){repository(owner:$o,name:$n){id discussionCategories(first:25){nodes{id name slug}}}}',
         "variables": {"o": owner, "n": name}}
    req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps(q).encode(),
                                 headers={"Authorization": "bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            repo = json.load(r)["data"]["repository"]
    except Exception as e:
        print("giscus-IDs nicht ermittelt:", e, file=sys.stderr)
        return None
    cats = repo["discussionCategories"]["nodes"]
    pick = next((c for c in cats if c["slug"] == "announcements"), None) or \
           next((c for c in cats if c["slug"] == "general"), None) or (cats[0] if cats else None)
    if not pick:
        return None
    return {"repo": REPO, "repoId": repo["id"], "category": pick["name"], "categoryId": pick["id"]}


def main():
    posts, offset = [], 0
    while True:
        d = get(f"/posts?author={AGENT}&sort=new&limit=100&offset={offset}")
        batch = d.get("posts", [])
        posts += batch
        if not d.get("has_more") or not batch or offset > 2000:
            break
        offset += len(batch)

    news, seen = [], set()
    for p in posts:
        if p["id"] in seen or p.get("is_deleted") or p.get("is_spam"):
            continue
        seen.add(p["id"])
        # Die Liste kürzt Inhalte auf 500 Zeichen, daher jeden Post einzeln voll laden.
        try:
            full = get(f"/posts/{p['id']}")
            p = {**p, **(full.get("post") or {})}
        except Exception as e:
            print("Volltext fehlgeschlagen für", p["id"], e, file=sys.stderr)
        if not ok((p.get("title") or "") + " " + (p.get("content") or "")):
            continue
        comments = []
        if p.get("comment_count"):
            try:
                comments = clean_comments(get(f"/posts/{p['id']}/comments?sort=old&limit=100").get("comments"))
            except Exception as e:
                print("Kommentare fehlgeschlagen für", p["id"], e, file=sys.stderr)
        sub = p.get("submolt")
        news.append({
            "id": p["id"],
            "title": p.get("title", ""),
            "content": p.get("content") or "",
            "url": p.get("url"),
            "submolt": sub.get("name") if isinstance(sub, dict) else sub,
            "created_at": p.get("created_at"),
            "upvotes": p.get("upvotes", 0),
            "link": f"https://www.moltbook.com/post/{p['id']}",
            "comments": comments,
            "comment_total": count(comments),
        })

    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            pass
    data = {
        "source": f"https://www.moltbook.com/u/{AGENT}",
        "agent": AGENT,
        "giscus": giscus_ids() or old.get("giscus"),
        "posts": news,
    }
    # Nur schreiben, wenn sich inhaltlich etwas geändert hat (sonst kein Commit).
    if {k: v for k, v in old.items() if k != "updated"} == data:
        print("keine Änderung")
        return
    data["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(len(news), "Posts,", sum(n["comment_total"] for n in news), "Kommentare")


if __name__ == "__main__":
    main()
