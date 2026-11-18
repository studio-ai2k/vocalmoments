# vocalmoments.com — static site

Static HTML copy of the former WordPress site at www.vocalmoments.com, served by GitHub Pages.

- `gh-pages` branch: the published website (generated, don't edit by hand while the builder is in use).
- `tools/`: the scripts that crawl the live WordPress site and clean it into static HTML.
- `extra/`: files copied on top of every build (e.g. `CNAME`, replacements for WordPress-only features).
- `.github/workflows/build.yml`: runs the crawl on GitHub and publishes to `gh-pages`.

Re-run a build: Actions → "Build static copy of vocalmoments.com" → Run workflow.
Once the WordPress site is switched off, the `gh-pages` branch becomes the source of truth.
