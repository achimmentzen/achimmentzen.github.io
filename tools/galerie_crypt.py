#!/usr/bin/env python3
"""Verschlüsselt alle Bilder in galerie/ (AES-256-GCM) und stellt die
HTML-Seiten auf Entschlüsselung im Browser nach der Altersabfrage um.
Direkte Bildadressen auf GitHub/IPFS liefern danach nur Datensalat.
Idempotent: kann bei jedem Push laufen."""
import os, re, glob, subprocess, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
KEY_HEX = open("tools/galerie.key").read().strip()
KEY = bytes.fromhex(KEY_HEX)
PAGES = ["galerie/index.html", "en/galerie/index.html", "lebenslauf.html"]
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
PIXEL = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=="

JS = """<script id="galcrypt">(function(){var K='%s',done=false;
function hx(h){var a=new Uint8Array(h.length/2);for(var i=0;i<a.length;i++)a[i]=parseInt(h.substr(i*2,2),16);return a}
function mime(u){return /\\.png\\.bin$/.test(u)?'image/png':/\\.webp\\.bin$/.test(u)?'image/webp':'image/jpeg'}
function ok(){try{return localStorage.getItem('age18')==='1'}catch(e){return false}}
function run(){if(done||!ok()||!window.crypto||!crypto.subtle)return;done=true;
crypto.subtle.importKey('raw',hx(K),'AES-GCM',false,['decrypt']).then(function(k){
var cache={};document.querySelectorAll('[data-enc]').forEach(function(el){var u=el.getAttribute('data-enc');
if(!cache[u])cache[u]=fetch(u).then(function(r){return r.arrayBuffer()}).then(function(b){
return crypto.subtle.decrypt({name:'AES-GCM',iv:new Uint8Array(b,0,12)},k,new Uint8Array(b,12))}).then(function(p){
return URL.createObjectURL(new Blob([p],{type:mime(u)}))});
cache[u].then(function(url){if(el.tagName==='IMG')el.src=url;else{el.href=url;el.target='_blank'}})})})}
document.addEventListener('click',function(){setTimeout(run,0)},true);
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else run();})();</script>"""

def git(*a):
    subprocess.run(["git", *a], check=False)

# 1) Bilder verschlüsseln
os.makedirs("galerie/enc", exist_ok=True)
aes = AESGCM(KEY)
for p in sorted(glob.glob("galerie/*")):
    if not p.lower().endswith(IMG_EXT):
        continue
    name = os.path.basename(p)
    out = f"galerie/enc/{name}.bin"
    if not os.path.exists(out):
        iv = os.urandom(12)
        with open(p, "rb") as f:
            data = f.read()
        with open(out, "wb") as f:
            f.write(iv + aes.encrypt(iv, data, None))
        print("verschlüsselt:", name)
    git("rm", "-q", "--cached", "--ignore-unmatch", p)
    os.remove(p)

# 2) Seiten umstellen
attr = re.compile(r'(href|src)="((?:\.\./)*(?:galerie/)?)([\w.-]+\.(?:jpe?g|png|webp))"', re.I)
ipfs = re.compile(r'\s*·\s*<a class="gold" href="https?://[^"]*/ipfs/[^"]*\.(?:jpe?g|png|webp)">IPFS</a>', re.I)
for page in PAGES:
    if not os.path.exists(page):
        continue
    html = open(page, encoding="utf-8").read()
    orig = html
    base = os.path.dirname(page)
    def rep(m):
        kind, prefix, name = m.groups()
        target = os.path.normpath(os.path.join(base, prefix, name))
        if not target.startswith("galerie" + os.sep) or os.path.dirname(target) != "galerie":
            return m.group(0)
        if not os.path.exists(os.path.join("galerie/enc", name + ".bin")):
            return m.group(0)
        enc = f"{prefix}enc/{name}.bin"
        if kind == "src":
            return f'src="{PIXEL}" data-enc="{enc}"'
        return f'href="#" data-enc="{enc}"'
    html = attr.sub(rep, html)
    html = ipfs.sub("", html)
    SUF = " · achimmentzen20@gmail.com · +49 174 6134194 · https://achimmentzen.github.io"
    def _alt(m):
        t = m.group(0)
        if "data-enc" not in t or "gmail.com" in t:
            return t
        def r(a):
            v = a.group(1)
            if not v.startswith("Achim Mentzen"):
                v = "Achim Mentzen – " + v
            return 'alt="' + v + SUF + '"'
        return re.sub(r'alt="([^"]*)"', r, t)
    html = re.sub(r"<img [^>]*>", _alt, html)
    if 'id="galcrypt"' not in html and "data-enc=" in html:
        html = html.replace("</body>", (JS % KEY_HEX) + "</body>", 1)
    if html != orig:
        open(page, "w", encoding="utf-8").write(html)
        print("umgestellt:", page)
git("add", "-A", "galerie", "en/galerie", "lebenslauf.html")
