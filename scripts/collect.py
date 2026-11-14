"""
Collector. Runs in GitHub Actions on a schedule, writes data/deals.json,
and the workflow commits the result. GitHub Pages serves that JSON as a
static file — no server, no database, no hosting bill.

Run locally:  python scripts/collect.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import yaml  # noqa: E402
from holidays import current_window, next_window  # noqa: E402
from sources import (  # noqa: E402
    AffiliateFeedSource, BestBuySource, RssDealSource, SeedSource,
)

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("collect")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONFIG = ROOT / "sources.yml"

MAX_DEALS = 600          # keep the JSON small enough to load fast on mobile
MIN_DISCOUNT = 10


def load_config() -> dict:
    if not CONFIG.exists():
        return {}
    return yaml.safe_load(CONFIG.read_text()) or {}


def build_sources(cfg: dict) -> list:
    return [
        BestBuySource(min_discount=MIN_DISCOUNT),
        AffiliateFeedSource(min_discount=MIN_DISCOUNT),
        RssDealSource(cfg.get("rss_feeds", [])),
    ]


def dedupe(deals: list) -> list:
    """
    Same product from two sources collapses to one row. Keep the cheaper
    price — if two feeds disagree, the reader should see the one they can
    actually get, and a too-high price is the failure that loses trust.
    """
    best: dict[str, object] = {}
    for d in deals:
        fp = d.fingerprint()
        prev = best.get(fp)
        if prev is None:
            best[fp] = d
            continue
        if d.price is not None and (prev.price is None or d.price < prev.price):
            best[fp] = d
    return list(best.values())


def rank(deals: list) -> list:
    """
    Sort by what makes a deal worth a reader's attention: percentage off
    first, absolute dollars saved as the tiebreak. A 60%-off $20 item beats
    a 5%-off $900 TV for feed position — percentage is what people scan for.
    """
    def key(d):
        return (-(d.discount_pct or 0), -(d.savings or 0))
    return sorted(deals, key=key)


def main() -> int:
    cfg = load_config()
    today = date.today()

    collected: list = []
    report: dict[str, int] = {}

    for src in build_sources(cfg):
        if not src.enabled:
            report[src.name] = 0
            continue
        try:
            got = src.fetch()
        except Exception:
            log.exception("source %s crashed", src.name)
            got = []
        report[src.name] = len(got)
        collected.extend(got)

    using_seed = False
    if not collected:
        log.warning("no live sources configured - writing labeled sample data")
        collected = SeedSource().fetch()
        using_seed = True
        report["seed"] = len(collected)

    deals = rank(dedupe(collected))[:MAX_DEALS]

    cur, nxt = current_window(today), next_window(today)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "is_sample_data": using_seed,
        "counts": report,
        "total": len(deals),
        "stores": sorted({d.store for d in deals}),
        "categories": sorted({d.category for d in deals}),
        "holiday": {
            "live": cur.to_dict() if cur else None,
            "next": nxt.to_dict(),
            "days_until_next": nxt.days_until(today),
        },
        "deals": [d.to_dict() for d in deals],
    }

    DATA.mkdir(exist_ok=True)
    out = DATA / "deals.json"
    out.write_text(json.dumps(payload, indent=1))

    log.info("wrote %s (%d deals, %.0f KB)",
             out.relative_to(ROOT), len(deals), out.stat().st_size / 1024)
    log.info("sources: %s", report)
    if using_seed:
        log.warning("SAMPLE DATA - add BESTBUY_API_KEY or affiliate feeds for real deals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
