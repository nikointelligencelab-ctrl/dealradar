"""
Best Buy product API — TIER 1.

Best Buy publishes a free developer API with real prices and sale flags.
Get a key at developer.bestbuy.com; it is free and approval is quick.
Set BESTBUY_API_KEY as a GitHub Actions secret and this source turns itself on.

This is the model to copy for every other retailer: a sanctioned feed, with
your affiliate link attached, instead of scraping their HTML.
"""
from __future__ import annotations

import os
import urllib.parse
import urllib.request
import json
import logging

from .base import Deal, Source, classify

log = logging.getLogger(__name__)

ENDPOINT = "https://api.bestbuy.com/v1/products"


class BestBuySource(Source):
    name = "bestbuy"

    def __init__(self, page_size: int = 100, min_discount: int = 15):
        self.api_key = os.getenv("BESTBUY_API_KEY", "").strip()
        self.affiliate_tag = os.getenv("BESTBUY_AFFILIATE_URL", "").strip()
        self.page_size = page_size
        self.min_discount = min_discount
        self.enabled = bool(self.api_key)

    def _affiliate(self, url: str) -> str:
        """Wrap in your tracking link if configured. No tag = plain link."""
        if not self.affiliate_tag:
            return url
        return self.affiliate_tag + urllib.parse.quote(url, safe="")

    def fetch(self) -> list[Deal]:
        if not self.enabled:
            log.info("bestbuy: no BESTBUY_API_KEY, skipping")
            return []

        # onSale=true is the whole point — ask for markdowns, not the catalog.
        query = "(onSale=true)"
        params = {
            "apiKey": self.api_key,
            "format": "json",
            "pageSize": str(self.page_size),
            "sort": "percentSavings.desc",
            "show": ",".join([
                "sku", "name", "salePrice", "regularPrice", "percentSavings",
                "url", "image", "onlineAvailability",
            ]),
        }
        url = f"{ENDPOINT}{query}?{urllib.parse.urlencode(params)}"

        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                payload = json.load(resp)
        except Exception as exc:
            log.warning("bestbuy fetch failed: %s", exc)
            return []

        deals: list[Deal] = []
        for p in payload.get("products", []):
            sale, regular = p.get("salePrice"), p.get("regularPrice")
            if not sale or not regular or sale >= regular:
                continue
            pct = round((1 - sale / regular) * 100)
            if pct < self.min_discount:
                continue
            title = p.get("name", "").strip()
            deals.append(Deal(
                title=title,
                url=self._affiliate(p.get("url", "")),
                store="Best Buy",
                price=float(sale),
                list_price=float(regular),
                category=classify(title),
                image=p.get("image"),
                source=self.name,
            ))
        log.info("bestbuy: %d deals", len(deals))
        return deals
