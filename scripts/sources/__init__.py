from .base import Deal, Source, classify
from .bestbuy import BestBuySource
from .rss_deals import RssDealSource
from .affiliate_feed import AffiliateFeedSource
from .seed import SeedSource

__all__ = ["Deal", "Source", "classify", "BestBuySource",
           "RssDealSource", "AffiliateFeedSource", "SeedSource"]
