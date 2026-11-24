from .base import Deal, Source, classify
from .bestbuy import BestBuySource
from .rss_deals import RssDealSource
from .affiliate_feed import AffiliateFeedSource
from .scraped_files import ScrapedFileSource
from .seed import SeedSource
from .shopify import ShopifySource

__all__ = ["Deal", "Source", "classify", "BestBuySource",
           "RssDealSource", "AffiliateFeedSource", "ScrapedFileSource",
           "SeedSource", "ShopifySource"]
