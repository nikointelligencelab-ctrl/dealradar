"""
Generic RSS/Atom deal feed — TIER 2.

Point it at feeds whose publisher offers them for syndication. Configure in
sources.yml; nothing is hardcoded, because which feeds you may republish
commercially is a question about your agreements, not about code.

Prices are parsed from titles on a best-effort basis. Feed titles are written
for humans, so treat anything extracted here as approximate and never present
it as a verified price.
"""
from __future__ import annotations

import logging
import re
import urllib.request
import xml.etree.ElementTree as ET

from .base import Deal, Source, classify

log = logging.getLogger(__name__)

PRICE_RE = re.compile(r"\$\s?([0-9][0-9,]*(?:\.[0-9]{2})?)")
UA = "DealRadar/1.0 (+https://github.com/)"


class RssDealSource(Source):
    name = "rss"

    def __init__(self, feeds: list[dict]):
        self.feeds = feeds or []
        self.enabled = bool(self.feeds)

    @staticmethod
    def _prices(text: str) -> tuple[float | None, float | None]:
        """First $ is usually the deal price, second the list price."""
        found = [float(m.replace(",", "")) for m in PRICE_RE.findall(text)]
        if not found:
            return None, None
        if len(found) == 1:
            return found[0], None
        lo, hi = min(found[:2]), max(found[:2])
        return lo, hi

    def _one(self, feed: dict) -> list[Deal]:
        url, store = feed["url"], feed.get("store", "Various")
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                root = ET.fromstring(resp.read())
        except Exception as exc:
            log.warning("rss %s failed: %s", url, exc)
            return []

        items = root.findall(".//item") or root.findall(
            ".//{http://www.w3.org/2005/Atom}entry"
        )
        out: list[Deal] = []
        for it in items:
            title_el = it.find("title") or it.find(
                "{http://www.w3.org/2005/Atom}title"
            )
            if title_el is None or not title_el.text:
                continue
            title = title_el.text.strip()

            link_el = it.find("link")
            link = (link_el.text if link_el is not None and link_el.text
                    else (link_el.get("href") if link_el is not None else ""))
            if not link:
                continue

            price, list_price = self._prices(title)
            out.append(Deal(
                title=title, url=link.strip(), store=store,
                price=price, list_price=list_price,
                category=classify(title), source=f"rss:{store}",
            ))
        log.info("rss %s: %d items", store, len(out))
        return out

    def fetch(self) -> list[Deal]:
        deals: list[Deal] = []
        for feed in self.feeds:
            deals.extend(self._one(feed))
        return deals
