"""
Source adapter contract.

Every source returns the same normalized Deal. Adding a retailer means writing
one adapter, not touching the site.

ON WHERE DATA COMES FROM
------------------------
Adapters here fall into three tiers. Use them in this order:

  TIER 1 - Affiliate product feeds (bestbuy.py, affiliate_feed.py)
    The retailer hands you structured product data and prices, under a signed
    agreement, with your tracking link attached. Legal, stable, and it IS the
    revenue model. This is where a commercial deals site gets its data.

  TIER 2 - Public feeds the publisher offers for syndication (rss_deals.py)
    RSS/Atom that a site publishes specifically to be consumed. Check each
    feed's terms; "it has an RSS endpoint" is not the same as "you may
    republish it commercially."

  TIER 3 - HTML scraping
    Deliberately not implemented here. Scraping retail sites for a commercial
    product means ToS violation, IP bans within days, brittle selectors that
    break on every redesign, and in some cases litigation. It also gives you
    no affiliate attribution, so the traffic you send earns nothing.

If a retailer you want has no feed, the move is to apply to their affiliate
program, not to scrape them.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Deal:
    title: str
    url: str
    store: str
    price: float | None = None
    list_price: float | None = None
    currency: str = "USD"
    category: str = "other"
    image: str | None = None
    coupon: str | None = None
    expires: str | None = None
    source: str = "unknown"
    seen_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def discount_pct(self) -> int | None:
        if not self.price or not self.list_price or self.list_price <= 0:
            return None
        if self.price >= self.list_price:
            return None
        return round((1 - self.price / self.list_price) * 100)

    @property
    def savings(self) -> float | None:
        if self.price is None or self.list_price is None:
            return None
        diff = round(self.list_price - self.price, 2)
        return diff if diff > 0 else None

    def fingerprint(self) -> str:
        """Stable id so the same deal from two sources collapses to one row."""
        norm = re.sub(r"[^a-z0-9]+", "", f"{self.store}{self.title}".lower())
        return hashlib.sha1(norm.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.fingerprint()
        d["discount_pct"] = self.discount_pct
        d["savings"] = self.savings
        return d


class Source:
    """Subclass this. Keep fetch() total-failure-safe: return [] on error."""

    name: str = "base"
    enabled: bool = True

    def fetch(self) -> list[Deal]:
        raise NotImplementedError


# Order matters: the first match wins, so put the specific patterns above
# the broad ones. \b guards stop "tv" matching inside "Advent" and so on.
CATEGORY_RULES = [
    (r"lego|\btoy\b|doll|puzzle|board game|action figure", "toys"),
    (r"playstation|\bps5\b|xbox|nintendo|\bswitch\b|\brtx\b|\bgpu\b|"
     r"graphics card|gaming (chair|mouse|keyboard|headset)", "gaming"),
    (r"laptop|macbook|chromebook|notebook pc|desktop pc|monitor|"
     r"\bssd\b|nvme|hard drive|keyboard|\bmouse\b|\bram\b|motherboard",
     "computers"),
    (r"iphone|galaxy|pixel|smartphone|\btablet\b|ipad|power bank|"
     r"charger|airtag|\bcase\b", "phones-tablets"),
    (r"\btv\b|oled|qled|mini-?led|roku|soundbar|projector|"
     r"headphone|earbud|airpod|speaker|turntable|receiver|\bhi-?fi\b",
     "tv-audio"),
    (r"vacuum|air fryer|mattress|cookware|blender|instant pot|"
     r"pressure cooker|coffee|espresso|mixer|\bpan\b|sheets|towel",
     "home"),
    (r"jacket|shoe|sneaker|\bboot|hood(ie|y)|jeans|\bwatch\b|"
     r"parka|fleece|\bvest\b|backpack|sandal", "apparel"),
    (r"drill|\bsaw\b|tool|generator|mower|wrench|compressor|ladder",
     "tools"),
    (r"kindle|e-?reader|fitbit|garmin|smartwatch|fenix", "other"),
]


def classify(title: str) -> str:
    low = title.lower()
    for pattern, cat in CATEGORY_RULES:
        if re.search(pattern, low):
            return cat
    return "other"
