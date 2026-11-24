"""
Collector. Runs in GitHub Actions on a schedule, writes data/deals.json,
and the workflow commits the result. GitHub Pages serves that JSON as a
static file — no server, no database, no hosting bill.

Run locally:  py scripts/collect.py
"""
from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import yaml  # noqa: E402
from affiliate import AffiliateLinker  # noqa: E402
from holidays import current_window, next_window  # noqa: E402
from sources import (  # noqa: E402
    AffiliateFeedSource, BestBuySource, RssDealSource, ScrapedFileSource,
    SeedSource, ShopifySource,
)

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("collect")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONFIG = ROOT / "sources.yml"
HISTORY = DATA / "history.json"

MAX_DEALS = 1000         # ~600 KB raw, ~100 KB gzipped by Pages
PER_STORE_CAP = 120      # one giant feed shouldn't bury every other store
MIN_DISCOUNT = 10
HISTORY_POINTS = 30      # price points kept per product
HISTORY_TTL_DAYS = 90    # forget products not seen for this long


def load_config() -> dict:
    if not CONFIG.exists():
        return {}
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}


def build_sources(cfg: dict) -> list:
    return [
        BestBuySource(min_discount=MIN_DISCOUNT),
        AffiliateFeedSource(min_discount=MIN_DISCOUNT),
        RssDealSource(cfg.get("rss_feeds", [])),
        ScrapedFileSource(min_discount=MIN_DISCOUNT),
        ShopifySource(cfg.get("shopify_stores", []), min_discount=MIN_DISCOUNT),
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
    Percentage off first, absolute dollars saved as the tiebreak. A 60%-off
    $20 item beats a 5%-off $900 TV for feed position.
    """
    def key(d):
        return (-(d.discount_pct or 0), -(d.savings or 0))
    return sorted(deals, key=key)


def cap_per_store(deals: list, cap: int) -> list:
    seen: Counter = Counter()
    out = []
    for d in deals:
        if seen[d.store] < cap:
            seen[d.store] += 1
            out.append(d)
    return out


def load_history() -> dict:
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def update_history(history: dict, rows: list[dict], now: datetime) -> dict:
    """
    One price point per product per day. Gives the site 'new today',
    'lowest price we've tracked' and a small price chart, without a database.
    """
    today = now.date().isoformat()
    for r in rows:
        h = history.setdefault(r["id"], {"first_seen": now.isoformat(timespec="seconds"),
                                         "points": []})
        pts = h["points"]
        if pts and pts[-1][0] == today:
            pts[-1][1] = min(pts[-1][1], r["price"])
        else:
            pts.append([today, r["price"]])
        del pts[:-HISTORY_POINTS]
        h["last_seen"] = today

    cutoff = (now.date() - timedelta(days=HISTORY_TTL_DAYS)).isoformat()
    return {k: v for k, v in history.items() if v.get("last_seen", today) >= cutoff}


def annotate(rows: list[dict], history: dict) -> None:
    for r in rows:
        h = history.get(r["id"])
        if not h:
            continue
        prices = [p[1] for p in h["points"]]
        r["first_seen"] = h["first_seen"]
        r["low_price"] = min(prices)
        # Only claim "lowest" once there is more than one day to compare.
        r["is_lowest"] = len(prices) > 1 and r["price"] <= min(prices)
        r["history"] = h["points"][-14:]


def main() -> int:
    cfg = load_config()
    linker = AffiliateLinker(cfg.get("affiliate"))
    today = date.today()
    now = datetime.now(timezone.utc)

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

    deals = cap_per_store(rank(dedupe(collected)), PER_STORE_CAP)[:MAX_DEALS]

    rows = []
    tagged = 0
    for d in deals:
        row = d.to_dict()
        row["url"], row["affiliate"] = linker.link(d.store, d.url)
        tagged += row["affiliate"]
        rows.append(row)

    if not using_seed:
        history = update_history(load_history(), rows, now)
        annotate(rows, history)
        HISTORY.write_text(json.dumps(history, separators=(",", ":")), encoding="utf-8")

    cur, nxt = current_window(today), next_window(today)
    store_counts = Counter(r["store"] for r in rows)
    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "is_sample_data": using_seed,
        "counts": report,
        "total": len(rows),
        "affiliate_tagged": tagged,
        "stores": sorted(store_counts),
        "store_counts": dict(store_counts),
        "categories": sorted({r["category"] for r in rows}),
        "holiday": {
            "live": cur.to_dict() if cur else None,
            "next": nxt.to_dict(),
            "days_until_next": nxt.days_until(today),
        },
        "deals": rows,
    }

    DATA.mkdir(exist_ok=True)
    out = DATA / "deals.json"
    out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    log.info("wrote %s (%d deals, %.0f KB, %d with affiliate links)",
             out.relative_to(ROOT), len(rows), out.stat().st_size / 1024, tagged)
    log.info("sources: %s", report)
    if using_seed:
        log.warning("SAMPLE DATA - add BESTBUY_API_KEY or affiliate feeds for real deals")
    elif not tagged:
        log.warning("no affiliate rules matched - links earn nothing. "
                    "See `affiliate:` in sources.yml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
