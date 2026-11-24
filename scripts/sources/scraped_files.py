"""
Scraper exports - TIER 3, used on purpose.

Ultimate Web Scraper (or any other scraper) runs where a person is signed in:
in Claude Code, Claude or ChatGPT, through its MCP server
(https://mcp.ultimatewebscraper.com/mcp). That server signs in with OAuth, so it
cannot run unattended in GitHub Actions. The bridge is a file: export the
result table as CSV or JSON, put it in data/scraped/, commit it, and the
6-hourly refresh merges it with the other sources.

File naming:  data/scraped/<store>_<YYYY-MM-DD>.csv    e.g. puma_2026-11-23.csv
  <store>       shown on the site when the file has no store/brand column
  <YYYY-MM-DD>  the day it was scraped. Files older than SCRAPED_MAX_AGE_DAYS
                are skipped, because a scraped price does not refresh itself
                and a wrong price costs more trust than a missing one.

Columns the scraper picks its own names for, so matching ignores case,
spaces and underscores. A row needs a title, a product URL, a current price
and an original price; without the original price there is no discount to
rank, and DealRadar is a list of markdowns.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
from datetime import date, datetime, time, timezone
from pathlib import Path

from .base import Deal, Source, classify

log = logging.getLogger(__name__)

SCRAPED_DIR = Path(__file__).resolve().parents[2] / "data" / "scraped"

COLUMN_ALIASES = {
    "title": ["title", "name", "product name", "product title",
              "product description", "product", "description"],
    "url": ["url", "product url", "link", "product link", "href", "page url"],
    "price": ["sale price", "current price", "price", "final price",
              "discounted price", "deal price", "now price"],
    "list_price": ["original price", "list price", "regular price",
                   "was price", "compare at price", "msrp", "retail price",
                   "full price", "old price", "strikethrough price"],
    "image": ["image", "image url", "imageurl", "thumbnail", "img"],
    # Not "brand": on a retailer's sale page the brand is Nike, the store is
    # Nordstrom. The file name supplies the store otherwise.
    "store": ["store", "retailer", "merchant", "seller"],
    "currency": ["currency", "pricecurrency"],
    "availability": ["availability", "stock", "in stock", "stock status"],
}

DATE_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


_ALIAS_INDEX = {
    field: [_norm(a) for a in aliases] for field, aliases in COLUMN_ALIASES.items()
}


def _pick(row: dict, field: str) -> str | None:
    normed = {_norm(k): v for k, v in row.items() if k}
    for alias in _ALIAS_INDEX[field]:
        val = normed.get(alias)
        if val not in (None, ""):
            return str(val).strip()
    return None


def _money(val: str | None) -> float | None:
    """'$1,299.99', '1299.99 USD', 'US$45' -> float. A range keeps the low end."""
    if not val:
        return None
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(val))
    if not m:
        return None
    try:
        return float(m.group().replace(",", ""))
    except ValueError:
        return None


def _rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, dict):  # {"rows": [...]} or {"data": [...]}
            data = next((v for v in data.values() if isinstance(v, list)), [])
        return [r for r in data if isinstance(r, dict)]
    return list(csv.DictReader(text.splitlines()))


def _file_meta(path: Path) -> tuple[str, date | None]:
    stem = path.stem
    m = DATE_IN_NAME.search(stem)
    scraped_on = None
    if m:
        try:
            scraped_on = date.fromisoformat(m.group(1))
        except ValueError:
            pass
        stem = stem.replace(m.group(1), "")
    store = re.sub(r"[_\-]+", " ", stem).strip().title() or "Scraped"
    return store, scraped_on


class ScrapedFileSource(Source):
    name = "scraped"

    def __init__(self, min_discount: int = 10, folder: Path = SCRAPED_DIR):
        self.folder = folder
        self.min_discount = min_discount
        self.max_age = int(os.getenv("SCRAPED_MAX_AGE_DAYS", "3"))
        self.files = sorted(
            p for p in folder.glob("*")
            if p.suffix.lower() in (".csv", ".json")
        ) if folder.is_dir() else []
        self.enabled = bool(self.files)

    def fetch(self) -> list[Deal]:
        deals: list[Deal] = []
        today = date.today()
        for path in self.files:
            store_from_name, scraped_on = _file_meta(path)
            if scraped_on is None:
                log.warning("scraped: %s has no YYYY-MM-DD in its name; "
                            "can't tell how old it is", path.name)
            elif (today - scraped_on).days > self.max_age:
                log.info("scraped: skipping %s, older than %d days",
                         path.name, self.max_age)
                continue

            try:
                rows = _rows(path)
            except Exception as exc:
                log.warning("scraped: can't read %s: %s", path.name, exc)
                continue

            seen_at = (
                datetime.combine(scraped_on, time(), timezone.utc)
                .isoformat(timespec="seconds")
                if scraped_on else None
            )
            kept = no_was_price = 0
            for row in rows:
                title, link = _pick(row, "title"), _pick(row, "url")
                if not title or not link or not link.startswith("http"):
                    continue
                avail = (_pick(row, "availability") or "").lower().replace(" ", "")
                if "outofstock" in avail or "soldout" in avail:
                    continue
                currency = (_pick(row, "currency") or "USD").upper()
                if currency not in ("USD", "$"):
                    continue
                price = _money(_pick(row, "price"))
                list_price = _money(_pick(row, "list_price"))
                if not price or not list_price or list_price <= price:
                    no_was_price += 1
                    continue
                if round((1 - price / list_price) * 100) < self.min_discount:
                    continue
                deal = Deal(
                    title=title, url=link,
                    store=_pick(row, "store") or store_from_name,
                    price=price, list_price=list_price,
                    image=_pick(row, "image"),
                    category=classify(title), source=self.name,
                )
                if seen_at:
                    deal.seen_at = seen_at
                deals.append(deal)
                kept += 1

            log.info("scraped: %s -> %d deals (%d rows, %d without a markdown)",
                     path.name, kept, len(rows), no_was_price)
            if rows and not any(_pick(r, "title") and _pick(r, "url") for r in rows):
                log.warning("scraped: %s has no rows with both a title and a "
                            "product URL. Ask the scraper for 'url'.", path.name)
            elif rows and kept == 0 and no_was_price == len(rows):
                log.warning("scraped: %s has no original-price column DealRadar "
                            "recognizes. Ask the scraper for 'original price'.",
                            path.name)
        return deals
