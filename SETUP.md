# Deploying DealRadar on GitHub Pages

Twenty minutes, no server, no hosting bill.

---

## First, the architecture question

**GitHub Pages serves static files only.** No Python, no database, no cron.
Your DemandStack backend cannot run there.

That doesn't block a deals site, because of the split:

```
GitHub Actions (cron, every 6h)      GitHub Pages (static)
  runs scripts/collect.py              serves site/index.html
  hits the affiliate feeds             serves data/deals.json
  writes data/deals.json               browser filters in memory
  commits it to the repo        ──────► deploy workflow publishes
```

Actions *is* your backend. It runs on GitHub's machines on a schedule, writes
one JSON file, and Pages serves it. Free for public repos.

---

## Step 1 — Create the repo

```powershell
cd C:\Users\nihat\Downloads\dealradar
git init
git add .
git commit -m "DealRadar: initial build"
gh repo create dealradar --public --source=. --push
```

No `gh`? Make an empty repo on github.com, then:

```powershell
git remote add origin https://github.com/YOURNAME/dealradar.git
git branch -M main
git push -u origin main
```

**The repo must be public** for free Actions minutes and Pages. Nothing
sensitive lives in it — keys go in Secrets, never in files.

## Step 2 — Turn on Pages

Repo → **Settings** → **Pages** → Source: **GitHub Actions** (not "Deploy from
a branch").

## Step 3 — Let Actions write to the repo

Repo → **Settings** → **Actions** → **General** → Workflow permissions →
**Read and write permissions** → Save.

Without this the refresh job collects deals fine and then fails to commit them.

## Step 4 — First deploy

Repo → **Actions** → **Deploy to Pages** → **Run workflow**.

About a minute later: `https://YOURNAME.github.io/dealradar/`

It works immediately, showing sample listings with a yellow banner saying so.

---

## Step 5 — Real data

The site is live but the prices are samples. Pick a source.

### Best Buy (easiest — free, ~10 minutes)

1. developer.bestbuy.com → sign up → create an app → copy the key
2. Repo → Settings → Secrets and variables → Actions → **New repository secret**
3. Name `BESTBUY_API_KEY`, paste the key
4. Actions → **Refresh deals** → Run workflow

Real markdowns, sorted by percentage off, in about 30 seconds.

### Affiliate networks (this is the business)

Apply to the networks. Approval takes a few days to a few weeks:

| Network | Merchants |
|---|---|
| **Impact** | Walmart, Target, Lowe's, Adidas |
| **CJ Affiliate** | Best Buy, Overstock, GoPro |
| **Rakuten** | Macy's, Sephora, Walgreens |
| **Awin** | Etsy, HP, StubHub |
| **Amazon Associates** | Amazon (apply directly) |
| **ShareASale** | thousands of smaller brands |

Each approved merchant gives you a **product feed** — a CSV with prices, sale
prices, images, and your tracking link already embedded. Put the feed URLs in
a secret named `AFFILIATE_FEED_URLS`, comma-separated:

```
https://feeds.impact.com/....csv,https://feeds.cj.com/....csv
```

`scripts/sources/affiliate_feed.py` maps the common column names across
networks, so most feeds work unchanged.

**This is both your data source and your revenue.** The feed is legal, stable,
and every click carries your commission. You are not choosing between "getting
data" and "making money" — it's the same pipe.

### Why not just scrape the retailers

You asked for everything scraped. Three reasons that's the wrong foundation
for something you intend to sell:

1. **It earns nothing.** A scraped link has no affiliate tag. You'd send
   Walmart free traffic and get paid zero. The feed pays you for the same click.
2. **It breaks constantly.** Retail sites run bot detection and change markup
   weekly. You'd spend every weekend fixing selectors instead of growing.
3. **It's a ToS violation on every major retailer**, and for a *commercial*
   product that's real exposure — not the grey area that personal scraping sits in.

Scraping is right for research and for price history on sites with no program.
It's wrong as the engine of a business.

### About that Ultimate Web Scraper connector

It's a real product — a Chrome extension (formerly PandaExtract) with an MCP
server. Nothing shady about it.

But it can't power this site. **An MCP connector only works inside a Claude
conversation.** It cannot run at 4am from GitHub Actions with nobody watching.
Your site needs an unattended pipeline; that tool needs you present and typing.

How DealRadar uses it: you scrape a sale page in a Claude/ChatGPT session,
export CSV or JSON as `data/scraped/<store>_<YYYY-MM-DD>.csv`, and push.
`scripts/sources/scraped_files.py` merges it on the next refresh (a push to
`data/scraped/` triggers one). Files expire after 3 days so stale prices don't
linger. See `data/scraped/README.md` for the prompt to use. Keep affiliate
feeds as the backbone; scraped rows earn no commission.

---

## Step 6 — Tune it

**Change the refresh rate** — `.github/workflows/refresh.yml`:
```yaml
- cron: "17 */6 * * *"     # every 6 hours
- cron: "17 */2 * * *"     # every 2 hours
```
Public repos get unlimited Actions minutes, so hourly is fine. Don't go below
that — most feeds only update a few times a day anyway.

**Add RSS feeds** — `sources.yml`:
```yaml
rss_feeds:
  - url: https://example.com/deals/feed
    store: Example
```
Check each feed's terms first. An RSS endpoint existing is not permission to
republish it commercially.

**Add a retailer** — copy `scripts/sources/bestbuy.py`, change the API calls,
register it in `scripts/collect.py` → `build_sources()`. The site needs no
changes; it renders whatever the collector produces.

**Custom domain** — Settings → Pages → Custom domain. Add a `CNAME` file to
`site/` so the deploy preserves it.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Site 404s | Pages source must be "GitHub Actions", not a branch |
| Banner still says sample data | Secret not set, or Refresh hasn't run since you set it |
| Refresh fails at the commit step | Workflow permissions → Read and write |
| Deals never update | Actions tab → check Refresh deals for red runs |
| Fonts look wrong locally | Google Fonts needs internet; fine once deployed |
| Cron seems late | GitHub queues scheduled jobs; 5–15 min drift is normal |

---

## Making money from it

In the order the money actually arrives:

1. **Affiliate commissions** (1–10%). Live the day your first merchant
   approves. No traffic threshold.
2. **Email list.** Capture early. A Black Friday list you own is worth more
   than the site — it's the only asset that survives a Google update.
3. **Sponsored placement.** Once you have traffic, brands pay for position.
4. **The demand data.** This is where DemandStack reconnects: once people are
   tracking prices and saying "I'd buy at $X", you own a demand curve nobody
   else has. That's the subscription product.

Build 1 and 2 now. 3 and 4 need an audience that doesn't exist yet.

Keep the FTC affiliate disclosure visible — it's in the footer already, and
16 CFR Part 255 requires it be clear and conspicuous, not buried.
