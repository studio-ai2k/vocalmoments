"""Site-specific edits applied to ./out after fixup.py.

- removes the theme's sample blog posts and their archive pages (never linked from the real pages)
- replaces the contact form (needs a mail server) with an email + phone block
- removes Contact Form 7 scripts, which only work with WordPress behind them
"""
import os
import posixpath
import re
import shutil

OUT = "out"
EMAIL = "wolfgang.rauch@hotmail.com"
PHONE_TEL, PHONE_TXT = "+491634845355", "+49 163 4845355"

DEMO_PAGES = [
    "a-little-journey", "a-little-journey-2", "beautiful-typography", "beautiful-typography-2",
    "daily-inspiration", "evaluate-your-product", "hello-world-2", "new-design-trends",
    "stages-of-the-startup-lifecycle", "what-make-a-brand-success",
    "category", "tag", "2015", "2016",
]

removed = set()
for d in DEMO_PAGES:
    full = os.path.join(OUT, d)
    if os.path.isdir(full):
        for r, _ds, fs in os.walk(full):
            for f in fs:
                if f.endswith(".html"):
                    removed.add(os.path.normpath(os.path.join(r, f)))
        shutil.rmtree(full)

CONTACT_BLOCK = f"""<div class="vm-contact" style="padding:30px 0;font-size:18px;line-height:1.9">
<p style="margin:0 0 18px">We look forward to hearing from you. Write to us or give us a call:</p>
<p style="margin:0"><strong>Email:</strong> <a href="mailto:{EMAIL}">{EMAIL}</a></p>
<p style="margin:0"><strong>Phone:</strong> <a href="tel:{PHONE_TEL}">{PHONE_TXT}</a></p>
</div>"""

CF7_JUNK = [
    re.compile(r"<script[^>]+src=['\"][^'\"]*contact-form-7/[^'\"]*['\"][^>]*>\s*</script>\s*", re.I),
    re.compile(r"<script[^>]+id=['\"](?:contact-form-7|swv)[^'\"]*['\"][^>]*>.*?</script>\s*", re.S | re.I),
]
LINK_RE = re.compile(r"<a\b([^>]*?)href=([\"'])([^\"'#]+)\2([^>]*)>(.*?)</a>", re.S)

stats = {"unlinked": 0, "forms": 0}
for root, _dirs, files in os.walk(OUT):
    for name in files:
        if not name.endswith(".html"):
            continue
        fpath = os.path.join(root, name)
        with open(fpath, encoding="utf-8") as f:
            s = f.read()
        orig = s

        def unlink(m, fpath=fpath):
            href = m.group(3)
            if href.startswith(("http", "//", "mailto:", "tel:")):
                return m.group(0)
            target = os.path.normpath(posixpath.join(os.path.dirname(fpath), href))
            if target in removed:
                stats["unlinked"] += 1
                return m.group(5)
            return m.group(0)

        s = LINK_RE.sub(unlink, s)
        s, n = re.subn(r"<form[^>]+class=\"wpcf7-form[^\"]*\"[^>]*>.*?</form>", CONTACT_BLOCK, s, flags=re.S)
        stats["forms"] += n
        for rx in CF7_JUNK:
            s = rx.sub("", s)
        if s != orig:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(s)

# 404 page is served at any missing URL, so its relative links must resolve from the site root.
p404 = os.path.join(OUT, "404.html")
if os.path.exists(p404):
    with open(p404, encoding="utf-8") as f:
        s = f.read()
    if "<base " not in s:
        s = re.sub(r"<head([^>]*)>", r'<head\1>\n<base href="/">', s, count=1)
    with open(p404, "w", encoding="utf-8") as f:
        f.write(s)

# Marker the crawler checks before running (see tools/crawl.sh).
with open(os.path.join(OUT, "static-copy.txt"), "w") as f:
    f.write("Static copy of the former WordPress site, hosted on GitHub Pages.\n")

print(f"Removed {len(removed)} demo pages, unlinked {stats['unlinked']} links to them, "
      f"replaced {stats['forms']} contact form(s).")
