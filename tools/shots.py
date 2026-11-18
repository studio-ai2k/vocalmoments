"""Screenshot key pages on the live site and on the static copy, side by side.

The static copy is served from ./out on localhost. Requests the static pages make to
www.vocalmoments.com are answered from ./out too, which is what happens once the domain
points at GitHub Pages; anything missing there is logged as a 404.
"""
import http.server
import os
import re
import threading
import urllib.parse

from playwright.sync_api import sync_playwright

SITE = os.environ.get("SITE", "https://www.vocalmoments.com").rstrip("/")
OUT = os.path.abspath("out")
SHOTS = os.path.join(OUT, "_build", "shots")
PAGES = ["/", "/about-us/", "/contact-us/", "/imprint/", "/privacy-policy/",
         "/portfolio/porsche-museum/", "/testimonials/"]
os.makedirs(SHOTS, exist_ok=True)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=OUT, **k)

    def log_message(self, *a):
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), Quiet)
threading.Thread(target=srv.serve_forever, daemon=True).start()
LOCAL = "http://127.0.0.1:8765"

log = []


def local_path(url_path):
    p = urllib.parse.unquote(url_path.split("?", 1)[0])
    rel = p.lstrip("/")
    for c in ([os.path.join(rel, "index.html")] if p.endswith("/") or not rel else [rel, rel + "/index.html"]):
        f = os.path.join(OUT, c)
        if os.path.isfile(f):
            return f
    return None


def serve_from_out(route):
    path = urllib.parse.urlsplit(route.request.url).path
    f = local_path(path)
    if f:
        route.fulfill(path=f)
    else:
        log.append(f"  404 (would be missing after DNS switch): {path}")
        route.fulfill(status=404, body="")


def settle(page):
    page.wait_for_timeout(2500)
    h = page.evaluate("document.body.scrollHeight")
    for y in range(0, h, 500):
        page.evaluate(f"window.scrollTo(0,{y})")
        page.wait_for_timeout(120)
    page.evaluate("window.scrollTo(0,0)")
    page.wait_for_timeout(1500)


with sync_playwright() as p:
    browser = p.chromium.launch()
    for path in PAGES:
        name = path.strip("/").replace("/", "_") or "home"
        for kind in ("live", "static"):
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m, e=errors: e.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda exc, e=errors: e.append(f"JS: {exc}"))
            if kind == "static":
                page.route(re.compile(r"^https?://(www\.)?vocalmoments\.com/"), serve_from_out)
                url = LOCAL + path
            else:
                url = SITE + path
            try:
                page.goto(url, wait_until="load", timeout=60000)
                settle(page)
                page.screenshot(path=os.path.join(SHOTS, f"{name}-{kind}.png"), full_page=True)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"FAILED: {exc}")
            if kind == "static" or errors:
                log.append(f"[{kind}] {path}")
                log.extend(f"  console: {e[:300]}" for e in errors)
            ctx.close()
    browser.close()

seen, uniq = set(), []
for line in log:
    if line not in seen or line.startswith("["):
        uniq.append(line)
        seen.add(line)
with open(os.path.join(SHOTS, "report.txt"), "w") as f:
    f.write("\n".join(uniq) + "\n")
print("\n".join(uniq))
srv.shutdown()
