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
  collect.py       orchestrator: fetch, dedupe, rank, write
  holidays.py      US retail calendar (Black Friday, Cyber Monday, ...)
  sources/
    bestbuy.py         free retailer API         — tier 1
    affiliate_feed.py  CJ/Impact/Rakuten CSV     — tier 1
    rss_deals.py       syndicated feeds          — tier 2
    seed.py            labeled sample data
site/              the whole front end, no build step
data/deals.json    generated; committed so Pages can serve it
```

## Design

A price list, not a card grid. The discount percentage is the largest element
in every row because that's what people scan for. Rows sorted by percentage
off, dollars saved as tiebreak — a 60%-off $20 item beats a 5%-off TV.

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

```bash
pip install -r requirements.txt
python scripts/collect.py
cd site && python -m http.server 8000
```

Visit localhost:8000. With no API keys set it writes labeled sample data and
the page shows a banner saying so.
