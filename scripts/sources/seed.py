"""
Seed data so the site renders before any API key exists.

Every row is flagged `"source": "seed"` and the site labels them as sample
data. The moment a real source returns rows, seed output is dropped — see
collect.py. Never let placeholder prices reach a live page unlabeled; a deals
site that shows a wrong price once loses the reader permanently.
"""
from __future__ import annotations

from .base import Deal, Source, classify

SAMPLES = [
    ("Sony WH-1000XM6 Wireless Noise Cancelling Headphones", "Best Buy", 278.00, 449.99),
    ("LG C4 65\" OLED evo 4K Smart TV", "Best Buy", 1296.99, 2099.99),
    ("Apple MacBook Air 15\" M4 16GB 512GB", "B&H", 1099.00, 1399.00),
    ("Nintendo Switch 2 Mario Kart World Bundle", "Walmart", 449.00, 499.99),
    ("Dyson V15 Detect Absolute Cordless Vacuum", "Dyson", 479.99, 749.99),
    ("Bose QuietComfort Ultra Earbuds", "Target", 189.00, 299.00),
    ("Samsung 990 PRO 2TB NVMe SSD", "Amazon", 139.99, 249.99),
    ("iPad Air 13\" M3 128GB Wi-Fi", "Costco", 549.99, 799.00),
    ("Ninja Crispi 4-in-1 Air Fryer", "Target", 89.99, 169.99),
    ("LEGO Icons Millennium Falcon 75192", "Walmart", 679.99, 849.99),
    ("DeWalt 20V MAX XR 5-Tool Combo Kit", "Home Depot", 399.00, 649.00),
    ("Garmin Fenix 8 AMOLED 47mm", "REI", 849.99, 1099.99),
    ("Anker Prime 27,650mAh Power Bank", "Amazon", 109.99, 179.99),
    ("Sonos Arc Ultra Soundbar", "Sonos", 699.00, 999.00),
    ("ASUS ROG Strix RTX 5080 16GB", "Newegg", 1149.99, 1399.99),
    ("Nike Pegasus 41 Running Shoes", "Nike", 87.97, 140.00),
    ("Instant Pot Pro Plus 6qt", "Amazon", 94.95, 169.99),
    ("Hisense U8N 75\" Mini-LED 4K TV", "Amazon", 1197.99, 1899.99),
    ("Patagonia Nano Puff Hoody", "Backcountry", 148.99, 239.00),
    ("Kindle Paperwhite Signature 32GB", "Amazon", 139.99, 199.99),
]


class SeedSource(Source):
    name = "seed"

    def fetch(self) -> list[Deal]:
        return [
            Deal(
                title=t, url="https://example.com/sample-listing",
                store=store, price=price, list_price=lp,
                category=classify(t), source="seed",
            )
            for t, store, price, lp in SAMPLES
        ]
