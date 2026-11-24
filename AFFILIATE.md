# Making money with DealRadar

Every "Get deal" click can pay you a commission (typically 1–10% of the
order). It takes two things: an approved affiliate account for each store,
and one rule per store in `sources.yml`. Until then links work, but pay
nothing. The collector warns `no affiliate rules matched` on every run.

## 1. Apply

Approval asks for a live site with real content, so deploy first (SETUP.md),
then apply. Expect a few days to a few weeks per program.

| Store | Where to apply | What you get |
|---|---|---|
| **Best Buy** | Impact (search "Best Buy" in the Impact marketplace) | deep links + product feed |
| **Walmart** | Impact ("Walmart Creator" / Walmart affiliate program) | deep links + product catalog |
| **Target** | Impact ("Target Partners") | deep links + product catalog |
| **Micro Center** | check the "Affiliate" link in microcenter.com's footer | depends on their program |
| **Amazon** | affiliate-program.amazon.com | a tag (`yourtag-20`) |
| **Shopify brands** (Allbirds, Everlane, Cotopaxi, …) | each brand's footer → "Affiliates"; most run on Impact, ShareASale, Rakuten or Awin | deep links |

Programs and networks change. Confirm on each store's site before applying.

## 2. Turn on links: `sources.yml`

In each network's dashboard, find the **deep link / link builder**. Make one
link to any product, then replace the product URL in it with `{url}`:

```yaml
affiliate:
  - match: [walmart.com]
    template: "https://goto.walmart.com/c/1234567/568844/9383?u={url}"
  - match: [target.com]
    template: "https://goto.target.com/c/1234567/81938/2092?u={url}"
  - match: [amazon.com]
    params: { tag: yourtag-20 }
```

`match` takes domains or store names. Push, and the next refresh rewrites
every link for that store. The log line `N with affiliate links` confirms it.

## 3. Get Walmart / Target / Micro Center *products* on the site

DealRadar does not scrape these retailers. They run aggressive bot
protection, block cloud servers like GitHub Actions within hours, and forbid
it in their terms. Once approved, the network gives you a **product feed URL**
instead, which is the stable, sanctioned version of the same data. Add it to
the `AFFILIATE_FEED_URLS` repository secret:

```
Walmart=https://...walmart-feed.csv.gz,Target=https://...target-feed.csv
```

`scripts/sources/affiliate_feed.py` reads Impact and CJ column layouts,
keeps rows that are discounted 10%+ and in stock, and caps each store at
120 deals so one huge catalog doesn't bury the rest.

**Best Buy** is available today without approval: get a free key at
developer.bestbuy.com and add it as the `BESTBUY_API_KEY` secret.

## 4. Rules that keep the money coming

- **Disclose.** The footer disclosure is required by the FTC (16 CFR 255).
  Keep it visible.
- **Don't cloak or rewrite prices.** Networks audit; showing a price the
  store isn't charging gets accounts closed.
- **Links are `rel="sponsored"`**, which is what Google requires for paid links.
