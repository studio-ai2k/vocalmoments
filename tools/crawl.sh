#!/usr/bin/env bash
# Mirror the live WordPress site into ./raw using wget.
set -uo pipefail

SITE="${SITE:-https://www.vocalmoments.com}"
HOST="${SITE#https://}"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# URLs we never want in the static copy (shop, admin, feeds, API, search, comments).
REJECT='(/product/|/products/|/shop/|/cart/|/checkout/|/my-account/|/product-category/|/product-tag/|add-to-cart|add_to_wishlist|/wp-json|/feed/?$|/feed/|xmlrpc\.php|wp-login\.php|/wp-admin|replytocom|[?&]s=|/comments/|/embed/?$|[?&]p=|/author/|wc-ajax|orderby=|/trackback/)'

rm -rf raw && mkdir -p raw

# Seed list: homepage + every URL in the WordPress sitemaps (core, Yoast or Rank Math).
python3 tools/sitemap_urls.py "$SITE" > seeds.txt || true
echo "$SITE/" >> seeds.txt
sort -u seeds.txt | grep -Ev "$REJECT" > seeds.clean.txt
echo "Seed URLs:"; cat seeds.clean.txt

wget \
  --mirror --page-requisites --adjust-extension --convert-links \
  --execute robots=off --no-verbose \
  --user-agent="$UA" --wait=0.15 --random-wait --tries=3 --timeout=30 \
  --domains="$HOST" --reject-regex="$REJECT" \
  --no-host-directories --directory-prefix=raw \
  --input-file=seeds.clean.txt 2>&1 | tail -n 400 > crawl.log
echo "wget exit status: ${PIPESTATUS[0]}"

echo "Files downloaded: $(find raw -type f | wc -l)"
