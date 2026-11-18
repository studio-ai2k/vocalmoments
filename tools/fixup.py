"""Turn the raw wget mirror (./raw) into a clean static site (./out).

- strips ?ver=... query strings from asset file names and references
- downloads assets wget missed (slider images, fonts in CSS, lazy-load attributes, JSON in inline scripts)
- rewrites links to the live domain into relative links where the file exists locally
- removes WordPress-only tags (REST API, oEmbed, RSD, emoji script, generator)
- writes out/_report.txt with anything that could not be resolved
"""
import os
import posixpath
import re
import shutil
import sys
import urllib.parse
import urllib.request

SITE = os.environ.get("SITE", "https://www.vocalmoments.com").rstrip("/")
DOMAIN_RE = r"(?:www\.)?vocalmoments\.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
SRC, OUT = "raw", "out"
TEXT_EXT = {".html", ".htm", ".css", ".js", ".json", ".xml", ".svg", ".txt"}
ASSET_EXT = {
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".avif",
    ".woff", ".woff2", ".ttf", ".eot", ".otf", ".mp3", ".mp4", ".webm", ".pdf", ".json",
}
SKIP_PATH = re.compile(r"^/(wp-admin|wp-json|xmlrpc\.php|wp-login\.php|feed|comments)(/|$)")

report = {"fetched": [], "failed": [], "unresolved_pages": set()}

# ---------------------------------------------------------------- copy & rename
if os.path.exists(OUT):
    shutil.rmtree(OUT)
shutil.copytree(SRC, OUT)

for root, _dirs, files in os.walk(OUT):
    for name in files:
        if "?" in name:
            clean = name.split("?", 1)[0]
            src, dst = os.path.join(root, name), os.path.join(root, clean)
            if os.path.exists(dst):
                os.remove(src)
            else:
                os.rename(src, dst)


def local_file_for(path):
    """Map a URL path (no query) to a file inside OUT, or None."""
    path = urllib.parse.unquote(path)
    rel = path.lstrip("/")
    cand = []
    if path.endswith("/") or rel == "":
        cand.append(posixpath.join(rel, "index.html"))
    else:
        cand += [rel, rel + "/index.html", rel + ".html"]
    for c in cand:
        full = os.path.join(OUT, c)
        if os.path.isfile(full):
            return full
    return None


def fetch_asset(path):
    """Download an asset from the live site into OUT at the same path."""
    url = SITE + urllib.parse.quote(urllib.parse.unquote(path), safe="/%")
    dst = os.path.join(OUT, urllib.parse.unquote(path).lstrip("/"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(data)
        report["fetched"].append(path)
        return dst
    except Exception as e:  # noqa: BLE001
        report["failed"].append(f"{path}  ({e})")
        return None


attempted = set()


def resolve(path, current_file, escaped):
    """Return replacement text for a site URL path, or None to leave it."""
    path, _, frag = path.partition("#")
    path = path.split("?", 1)[0] or "/"
    if SKIP_PATH.match(path):
        return None
    target = local_file_for(path)
    ext = posixpath.splitext(path)[1].lower()
    if target is None and ext in ASSET_EXT and path not in attempted:
        attempted.add(path)
        target = fetch_asset(path)
        if target and posixpath.splitext(target)[1].lower() in TEXT_EXT:
            queue.append(target)
    if target is None:
        if ext not in ASSET_EXT:
            report["unresolved_pages"].add(path)
        return None
    if current_file.endswith(".js"):
        # JS resolves URLs against the page, not the script: keep it root-relative.
        new = "/" + os.path.relpath(target, OUT).replace(os.sep, "/")
    else:
        new = os.path.relpath(target, os.path.dirname(current_file)).replace(os.sep, "/")
    new = urllib.parse.quote(new, safe="/.-_~%")
    if frag:
        new += "#" + frag
    return new.replace("/", "\\/") if escaped else new


ABS_RE = re.compile(r"(?:https?:)?//" + DOMAIN_RE + r"(/[^\"'\s)<>&\\]*)?")
ABS_ESC_RE = re.compile(r"(?:https?:)?\\/\\/" + DOMAIN_RE + r"((?:\\/[^\"'\s)<>&\\]*)*)")
ROOTREL_RE = re.compile(r"(?<=[\"'(\s,=])(/wp-(?:content|includes)/[^\"'\s)<>&\\]*)")
QUERY_RE = re.compile(
    r"(\.(?:css|js|png|jpe?g|gif|webp|svg|woff2?|ttf|eot|otf|ico))(?:%3F|\?)[^\"'\s)<>]*?(?=[\"'\s)<>]|&quot;|$)"
)

JUNK = [
    r"<link[^>]+rel=['\"](?:EditURI|wlwmanifest|shortlink|pingback|https://api\.w\.org/)['\"][^>]*>\s*",
    r"<link[^>]+type=['\"]application/(?:json|xml\+oembed|json\+oembed|rss\+xml|atom\+xml)['\"][^>]*>\s*",
    r"<link[^>]+href=['\"][^'\"]*wp-json[^'\"]*['\"][^>]*>\s*",
    r"<meta[^>]+name=['\"]generator['\"][^>]*>\s*",
    r"<link[^>]+rel=['\"]dns-prefetch['\"][^>]+s\.w\.org[^>]*>\s*",
    r"<script[^>]*>\s*window\._wpemojiSettings.*?</script>\s*",
    r"<script[^>]+wp-emoji-release[^>]*></script>\s*",
    r"<style[^>]*>\s*img\.wp-smiley.*?</style>\s*",
    r"<style[^>]+id=['\"]wp-emoji-styles-inline-css['\"][^>]*>.*?</style>\s*",
]
JUNK_RE = [re.compile(p, re.S | re.I) for p in JUNK]


def process(fpath):
    try:
        with open(fpath, encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        return
    orig = text
    text = QUERY_RE.sub(r"\1", text)
    text = ABS_ESC_RE.sub(lambda m: resolve((m.group(1) or "\\/").replace("\\/", "/"), fpath, True) or m.group(0), text)
    text = ABS_RE.sub(lambda m: resolve(m.group(1) or "/", fpath, False) or m.group(0), text)
    if fpath.endswith((".html", ".css")):
        text = ROOTREL_RE.sub(lambda m: resolve(m.group(1), fpath, False) or m.group(0), text)
    if fpath.endswith(".html"):
        for rx in JUNK_RE:
            text = rx.sub("", text)
    if text != orig:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(text)


queue = []
for root, _dirs, files in os.walk(OUT):
    for name in files:
        if os.path.splitext(name)[1].lower() in TEXT_EXT:
            queue.append(os.path.join(root, name))

done = set()
while queue:
    p = queue.pop()
    if p in done:
        continue
    done.add(p)
    process(p)

# GitHub Pages: serve files/folders starting with "_" as-is
open(os.path.join(OUT, ".nojekyll"), "w").close()

with open(os.path.join(OUT, "_report.txt"), "w") as f:
    f.write(f"Assets fetched after crawl: {len(report['fetched'])}\n")
    f.writelines(f"  + {p}\n" for p in sorted(report["fetched"]))
    f.write(f"\nAssets that failed to download: {len(report['failed'])}\n")
    f.writelines(f"  ! {p}\n" for p in sorted(report["failed"]))
    f.write(f"\nPage links not in the copy (left pointing at the live site): {len(report['unresolved_pages'])}\n")
    f.writelines(f"  ? {p}\n" for p in sorted(report["unresolved_pages"]))

print(open(os.path.join(OUT, "_report.txt")).read()[:4000])
n = sum(len(fs) for _, _, fs in os.walk(OUT))
print(f"Files in static site: {n}")
sys.exit(0)
