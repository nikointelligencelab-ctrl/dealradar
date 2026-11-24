"""
Affiliate link rewriting - one place, every source.

Each network gives you a way to turn a plain product URL into a tracked one.
Configure yours in sources.yml under `affiliate:` (the IDs end up in every
public link anyway, so they are not secrets). Rules match on store name or
link domain; the first match wins.

  affiliate:
    - match: [walmart.com]                       # Impact deep link
      template: "https://goto.walmart.com/c/1234567/568844/9383?u={url}"
    - match: [target.com]                        # Impact deep link
      template: "https://goto.target.com/c/1234567/81938/2092?u={url}"
    - match: [bestbuy.com]                       # Impact deep link
      template: "https://bestbuy.7tiv.net/c/1234567/614286/10014?u={url}"
    - match: [amazon.com]                        # Amazon Associates
      params: { tag: yourtag-20 }
    - match: [Allbirds, allbirds.com]            # brand program w/ ref code
      params: { ref: dealradar }

  template  {url} is replaced with the URL-encoded product link,
            {raw_url} with the unencoded one.
  params    query parameters appended to the product link.

Copy the exact template from your network's "deep link" / "link builder"
page; the numbers above are placeholders and earn nothing.
"""
from __future__ import annotations

import logging
import os
import urllib.parse

log = logging.getLogger(__name__)


class AffiliateLinker:
    def __init__(self, rules: list[dict] | None):
        self.rules = []
        for r in rules or []:
            match = r.get("match") or []
            if isinstance(match, str):
                match = [match]
            if not match or not (r.get("template") or r.get("params")):
                continue
            self.rules.append({
                "match": [m.lower() for m in match],
                "template": r.get("template"),
                "params": r.get("params") or {},
            })
        # Back-compat with the original Best Buy secret.
        legacy = os.getenv("BESTBUY_AFFILIATE_URL", "").strip()
        if legacy:
            self.rules.append({"match": ["bestbuy.com", "best buy"],
                               "template": legacy + "{url}", "params": {}})

    def _rule_for(self, store: str, url: str) -> dict | None:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        store = (store or "").lower()
        for r in self.rules:
            for m in r["match"]:
                if m == store or host == m or host.endswith("." + m):
                    return r
        return None

    def link(self, store: str, url: str) -> tuple[str, bool]:
        """-> (url to publish, whether it carries affiliate tracking)."""
        if not url:
            return url, False
        r = self._rule_for(store, url)
        if r is None:
            return url, False
        out = url
        if r["params"]:
            parts = urllib.parse.urlsplit(out)
            q = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
            q = [(k, v) for k, v in q if k not in r["params"]]
            q += [(k, str(v)) for k, v in r["params"].items()]
            out = urllib.parse.urlunsplit(parts._replace(
                query=urllib.parse.urlencode(q)))
        if r["template"]:
            out = (r["template"]
                   .replace("{url}", urllib.parse.quote(out, safe=""))
                   .replace("{raw_url}", out))
        return out, True
