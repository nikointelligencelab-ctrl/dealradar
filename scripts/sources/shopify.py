"""
Shopify storefronts - no API key.

Every Shopify store serves its catalog at /products.json, the same data its
own pages are built from. Each variant carries `price` and `compare_at_price`
(the crossed-out price), which is exactly the markdown DealRadar ranks.

Stores are listed in sources.yml under `shopify_stores`. Not every brand runs
on Shopify, and some block the endpoint (404/403); those are logged and
skipped. Prices are in the store's base currency, so list US stores only.

Politeness: one request per page, a pause between pages, a capped page count.
Scraped links carry no affiliate tag - many of these brands have programs on
Impact/CJ/Rakuten if you want the clicks to pay.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request

from .base import Deal, Source, classify

log = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
PAGE_SIZE = 250
MAX_PAGES = 4          # 1,000 products per store is plenty for a deals list
PER_STORE_CAP = 40     # one store with everything on sale shouldn't fill the page
PAUSE = 1.0


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _f(val) -> float | None:
    try:
        return float(val) if val not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _sized(src: str | None, width: int = 480) -> str | None:
    """Shopify's CDN resizes on request; full-size originals run 2-5 MB."""
    if not src:
        return None
    if src.startswith("//"):
        src = "https:" + src
    return f"{src}{'&' if '?' in src else '?'}width={width}"


def _best_variant(variants: list[dict]) -> tuple[float, float] | None:
    """Largest markdown among in-stock variants -> (price, list_price)."""
    best = None
    for v in variants:
        if v.get("available") is False:
            continue
        price, was = _f(v.get("price")), _f(v.get("compare_at_price"))
        if not price or not was or was <= price:
            continue
        if best is None or price / was < best[0] / best[1]:
            best = (price, was)
    return best


class ShopifySource(Source):
    name = "shopify"

    def __init__(self, stores: list[dict], min_discount: int = 10):
        self.stores = [s for s in stores if s.get("domain")]
        self.min_discount = min_discount
        self.enabled = bool(self.stores)

    def _store(self, domain: str, label: str, fallback_cat: str | None = None) -> list[Deal]:
        deals: list[Deal] = []
        for page in range(1, MAX_PAGES + 1):
            url = f"https://{domain}/products.json?limit={PAGE_SIZE}&page={page}"
            try:
                products = _get(url).get("products", [])
            except Exception as exc:
                log.warning("shopify: %s page %d failed: %s", domain, page, exc)
                break
            for p in products:
                best = _best_variant(p.get("variants") or [])
                if not best:
                    continue
                price, was = best
                if round((1 - price / was) * 100) < self.min_discount:
                    continue
                title = (p.get("title") or "").strip()
                if not title:
                    continue
                images = p.get("images") or []
                cat = classify(f"{title} {p.get('product_type') or ''}")
                if cat == "other" and fallback_cat:
                    cat = fallback_cat
                deals.append(Deal(
                    title=title,
                    url=f"https://{domain}/products/{p.get('handle')}",
                    store=label, price=price, list_price=was,
                    image=_sized(images[0].get("src")) if images else None,
                    category=cat,
                    source=self.name,
                ))
            if len(products) < PAGE_SIZE:
                break
            time.sleep(PAUSE)

        deals.sort(key=lambda d: -(d.discount_pct or 0))
        return deals[:PER_STORE_CAP]

    def fetch(self) -> list[Deal]:
        out: list[Deal] = []
        for s in self.stores:
            domain = s["domain"].replace("https://", "").strip("/")
            label = s.get("store") or domain
            got = self._store(domain, label, s.get("category"))
            log.info("shopify: %s -> %d deals", label, len(got))
            out.extend(got)
        return out
