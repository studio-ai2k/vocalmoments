"""Print every page URL listed in the site's XML sitemaps."""
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
site = sys.argv[1].rstrip("/")
seen, pages = set(), set()


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        print(f"# sitemap fetch failed {url}: {e}", file=sys.stderr)
        return ""


def walk(url):
    if url in seen or len(seen) > 200:
        return
    seen.add(url)
    xml = fetch(url)
    for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml):
        loc = loc.replace("&amp;", "&")
        if loc.endswith(".xml") or "sitemap" in loc.rsplit("/", 1)[-1]:
            walk(loc)
        else:
            pages.add(loc)


for start in ("/wp-sitemap.xml", "/sitemap_index.xml", "/sitemap.xml"):
    walk(site + start)

for p in sorted(pages):
    print(p)
