# DealRadar

Live US retail markdowns, ranked by how far the price actually dropped.
Static site on GitHub Pages, data refreshed by GitHub Actions. No server.

**[SETUP.md](SETUP.md) — deploy it in about 20 minutes.**

## How it works

```
GitHub Actions (cron, every 6h)          GitHub Pages (static)
  scripts/collect.py                       site/index.html
  → affiliate feeds + retailer APIs        data/deals.json
  → dedupe, rank by % off                  filters run in the browser
  → writes data/deals.json          ─────► published on every push
  → commits it
```

Actions is the backend. Pages is the front end. Both free on a public repo.

## Layout

```
.github/workflows/
  refresh.yml      scheduled collection, commits the data
  deploy.yml       publishes site/ + data/ to Pages
scripts/
  collect.py       orchestrator: fetch, dedupe, rank, tag links, history
  affiliate.py     rewrites every link with your affiliate IDs
  holidays.py      US retail calendar (Black Friday, Cyber Monday, ...)
  sources/
    bestbuy.py         free retailer API                 — tier 1
    affiliate_feed.py  Impact/CJ feeds (Walmart, Target) — tier 1
    shopify.py         public Shopify catalogs, no key
    rss_deals.py       syndicated feeds                  — tier 2
    scraped_files.py   Ultimate Web Scraper exports
    seed.py            labeled sample data
site/              the whole front end, no build step
data/deals.json    generated; committed so Pages can serve it
data/history.json  per-product price history (powers "lowest price" + charts)
```

**[AFFILIATE.md](AFFILIATE.md): how the site makes money.**

## Design

Product cards with the discount badge as the loudest element, because that's
what people scan for. "Hottest" sort weighs % off, dollars saved, freshness
and whether it's the lowest price tracked. Every deal opens a detail view with
its price history, so a real markdown is distinguishable from a fake one.
Filters, sort, saved deals and individual deals all live in the URL, so any
view is a shareable link. Dark mode follows the system and can be toggled.

The one loud moment is the countdown to the next retail event, which the site
computes itself from `holidays.py` rather than anyone editing a date.

## Data sources

Tier 1 is affiliate product feeds: the retailer hands you prices under
agreement with your tracking link attached. Legal, stable, and it *is* the
revenue model.

HTML scraping is deliberately not implemented. For a commercial site it earns
nothing (no affiliate attribution), breaks weekly, and violates retailer ToS.
If a store you want has no feed, apply to their affiliate program.

## Local

```powershell
py -m pip install -r requirements.txt
py scripts\collect.py
Remove-Item -Recurse -Force _site -ErrorAction SilentlyContinue
Copy-Item -Recurse site _site; New-Item -ItemType Directory _site\data | Out-Null
Copy-Item data\deals.json _site\data\
py -m http.server 8000 --directory _site
```

Visit localhost:8000. The Shopify stores in `sources.yml` need no keys, so
real deals appear on the first run.
