# Scraper exports

Put Ultimate Web Scraper exports (CSV or JSON) here, then commit and push.
The Refresh deals workflow runs on the push and merges them into the site.

**Name files `<store>_<YYYY-MM-DD>.csv`**, e.g. `puma_2026-11-23.csv`.
Files older than 3 days are skipped (`SCRAPED_MAX_AGE_DAYS`), so scrape again
before a sale weekend.

## Prompt to use

Open the store's **sale** page (not the full catalog; full-price items get
dropped), then ask:

> Use Ultimate Web Scraper to extract every product from this page with these
> columns: title, url (full product link), price (current sale price),
> original price (the crossed-out price), image url, availability, currency.

**Without the original price there is no discount, and the row is dropped.**
The Puma demo export (description, price, availability, currency, brand) would
give zero deals for that reason. Always ask for the original price.

Column names don't need to match exactly. `scripts/sources/scraped_files.py`
accepts common variants ("Sale Price", "Was Price", "Product Link", ...).
