"""
Affiliate network product feed — TIER 1.

This is how Walmart, Target and most big retailers hand out their catalog:
once you're approved on Impact (Walmart, Target, Best Buy) or CJ / Rakuten /
Awin, the merchant gives you a product feed - rows of products with price,
sale price, image and usually your tracking link already embedded.

Set the AFFILIATE_FEED_URLS secret to a comma-separated list. Prefix an entry
with a store name to label it, otherwise the feed's merchant column is used:

  Walmart=https://.../walmart.csv,Target=https://.../target.csv.gz

CSV, TSV, and gzip-compressed versions of either are accepted. Column names
differ per network; matching ignores case, spaces and underscores.
"""
from __future__ import annotations

import csv
import gzip
import io
import logging
import os
import re
import urllib.request

from .base import Deal, Source, classify

log = logging.getLogger(__name__)

MAX_ROWS = 200_000   # big-box catalogs run to millions of rows; stop early

SALE_ALIASES = ["saleprice", "currentprice", "discountprice", "dealprice",
                "specialprice", "promoprice"]
REGULAR_ALIASES = ["retailprice", "listprice", "originalprice", "regularprice",
                   "msrp", "wasprice", "compareatprice"]
COLUMN_ALIASES = {
    "title": ["name", "productname", "title", "producttitle"],
    "url": ["buyurl", "clickurl", "trackingurl", "affiliateurl", "url",
            "link", "producturl", "producturlweb"],
    "image": ["imageurl", "image", "largeimage", "imagelink", "imageurllarge"],
    "store": ["advertisername", "merchantname", "merchant", "advertiser",
              "programname", "store"],
    "stock": ["stockavailability", "availability", "instock", "stock"],
}


def _norm(k: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (k or "").lower())


def _pick(row: dict, aliases: list[str]) -> str | None:
    for a in aliases:
        v = row.get(a)
        if v not in (None, ""):
            return v.strip()
    return None


def _money(val: str | None) -> float | None:
    if not val:
        return None
    m = re.search(r"\d[\d,]*(?:\.\d+)?", val)
    try:
        return float(m.group().replace(",", "")) if m else None
    except ValueError:
        return None


def _prices(row: dict) -> tuple[float | None, float | None]:
    """
    Networks disagree on what 'price' means. CJ: PRICE is regular, SALEPRICE
    is the deal. Impact: Current Price / Original Price. Handle both.
    """
    sale = _money(_pick(row, SALE_ALIASES))
    regular = _money(_pick(row, REGULAR_ALIASES))
    plain = _money(row.get("price"))
    if sale is not None:
        return sale, regular or plain
    return plain, regular


def _entries(raw: str) -> list[tuple[str | None, str]]:
    out = []
    for item in (s.strip() for s in raw.split(",")):
        if not item:
            continue
        m = re.match(r"^([^=:/]+)=(https?://.+)$", item)
        out.append((m.group(1).strip(), m.group(2)) if m else (None, item))
    return out


class AffiliateFeedSource(Source):
    name = "affiliate"

    def __init__(self, min_discount: int = 10):
        self.feeds = _entries(os.getenv("AFFILIATE_FEED_URLS", ""))
        self.min_discount = min_discount
        self.enabled = bool(self.feeds)

    def _read(self, url: str) -> io.StringIO:
        req = urllib.request.Request(url, headers={"User-Agent": "DealRadar/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
        if body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        return io.StringIO(body.decode("utf-8-sig", errors="replace"))

    def fetch(self) -> list[Deal]:
        if not self.enabled:
            log.info("affiliate: no AFFILIATE_FEED_URLS, skipping")
            return []

        deals: list[Deal] = []
        for label, url in self.feeds:
            try:
                text = self._read(url)
            except Exception as exc:
                log.warning("affiliate feed %s failed: %s", label or url[:60], exc)
                continue

            sample = text.read(4096)
            text.seek(0)
            dialect = "excel-tab" if sample.count("\t") > sample.count(",") else "excel"
            reader = csv.DictReader(text, dialect=dialect)
            reader.fieldnames = [_norm(f) for f in (reader.fieldnames or [])]

            kept = 0
            for i, row in enumerate(reader):
                if i >= MAX_ROWS:
                    break
                title = _pick(row, COLUMN_ALIASES["title"])
                link = _pick(row, COLUMN_ALIASES["url"])
                if not title or not link:
                    continue
                stock = (_pick(row, COLUMN_ALIASES["stock"]) or "").lower()
                if stock in ("out of stock", "outofstock", "no", "false", "0"):
                    continue
                price, list_price = _prices(row)
                if not price or not list_price or list_price <= price:
                    continue
                if round((1 - price / list_price) * 100) < self.min_discount:
                    continue
                deals.append(Deal(
                    title=title, url=link,
                    store=label or _pick(row, COLUMN_ALIASES["store"]) or "Partner",
                    price=price, list_price=list_price,
                    image=_pick(row, COLUMN_ALIASES["image"]),
                    category=classify(title), source=self.name,
                ))
                kept += 1
            log.info("affiliate: %s -> %d deals", label or url[:60], kept)
        return deals
