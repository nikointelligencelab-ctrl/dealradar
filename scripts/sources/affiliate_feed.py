"""
Affiliate network product feed — TIER 1.

CJ, Impact, Rakuten, Awin, ShareASale and Amazon PA-API all hand you a product
feed once you're approved for a merchant. Formats vary; the shape is always
the same: rows of products with price, sale price, image and your tracking URL.

Set AFFILIATE_FEED_URLS to a comma-separated list of CSV feed URLs. Column
names differ per network, so COLUMN_ALIASES maps the common ones.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import urllib.request

from .base import Deal, Source, classify

log = logging.getLogger(__name__)

COLUMN_ALIASES = {
    "title": ["name", "product_name", "title", "ProductName"],
    "url": ["link", "url", "product_url", "buy_url", "clickUrl"],
    "price": ["sale_price", "price", "SalePrice", "discount_price"],
    "list_price": ["retail_price", "list_price", "RetailPrice", "msrp"],
    "image": ["image_url", "image", "ImageUrl", "imageUrl"],
    "store": ["merchant", "advertiser", "brand", "MerchantName"],
}


def _pick(row: dict, field: str) -> str | None:
    for alias in COLUMN_ALIASES[field]:
        if row.get(alias):
            return row[alias]
    return None


def _money(val: str | None) -> float | None:
    if not val:
        return None
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


class AffiliateFeedSource(Source):
    name = "affiliate"

    def __init__(self, min_discount: int = 10):
        raw = os.getenv("AFFILIATE_FEED_URLS", "").strip()
        self.urls = [u.strip() for u in raw.split(",") if u.strip()]
        self.min_discount = min_discount
        self.enabled = bool(self.urls)

    def fetch(self) -> list[Deal]:
        if not self.enabled:
            log.info("affiliate: no AFFILIATE_FEED_URLS, skipping")
            return []

        deals: list[Deal] = []
        for url in self.urls:
            try:
                with urllib.request.urlopen(url, timeout=60) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
            except Exception as exc:
                log.warning("affiliate feed %s failed: %s", url, exc)
                continue

            for row in csv.DictReader(io.StringIO(text)):
                title = _pick(row, "title")
                link = _pick(row, "url")
                if not title or not link:
                    continue
                price = _money(_pick(row, "price"))
                list_price = _money(_pick(row, "list_price"))
                if price and list_price and list_price > price:
                    pct = round((1 - price / list_price) * 100)
                    if pct < self.min_discount:
                        continue
                deals.append(Deal(
                    title=title.strip(), url=link.strip(),
                    store=(_pick(row, "store") or "Partner").strip(),
                    price=price, list_price=list_price,
                    image=_pick(row, "image"),
                    category=classify(title), source=self.name,
                ))
        log.info("affiliate: %d deals", len(deals))
        return deals
