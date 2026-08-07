import re
from datetime import datetime, timedelta, timezone
from typing import List

from src.config import Config
from src.fetcher import Article


class Processor:
    def __init__(self, config: Config):
        self.config = config
        self.keywords = [kw.lower() for kw in config.filters.keywords]
        self.required_in_title = [kw.lower() for kw in config.filters.required_in_title]
        self.exclude = [ex.lower() for ex in config.filters.exclude]
        self._source_by_name = {s.name: s for s in config.sources}

    def _find_source_config(self, source_name: str):
        return self._source_by_name.get(source_name)

    def filter_articles(self, articles: List[Article]) -> List[Article]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=self.config.settings.lookback_hours)
        filtered = []
        seen_links = set()

        for a in articles:
            if a.link in seen_links:
                continue
            seen_links.add(a.link)

            if a.published_at and a.published_at < cutoff:
                continue

            title_lower = a.title.lower()
            desc_lower = a.description.lower()
            combined = f"{title_lower} {desc_lower}"

            if any(ex in title_lower for ex in self.exclude):
                continue

            # Require at least one keyword if keywords are configured
            if self.keywords and not any(kw in combined for kw in self.keywords):
                continue

            # Require at least one strong fashion-related word in the title
            if self.required_in_title and not any(kw in title_lower for kw in self.required_in_title):
                continue

            # Source-level category filter (if configured)
            if source_cfg := self._find_source_config(a.source_name):
                if source_cfg.allowed_categories:
                    allowed = {c.lower() for c in source_cfg.allowed_categories}
                    entry_cats = {c.lower() for c in a.categories}
                    if not entry_cats.intersection(allowed):
                        continue

            filtered.append(a)

        # Cap per source
        per_source = {}
        capped = []
        for a in filtered:
            per_source[a.source_name] = per_source.get(a.source_name, 0) + 1
            if per_source[a.source_name] <= self.config.settings.max_per_source:
                capped.append(a)

        return capped

    @staticmethod
    def group_by_category(articles: List[Article]) -> dict:
        groups = {}
        for a in articles:
            groups.setdefault(a.category, []).append(a)
        return groups

    @staticmethod
    def extract_tags(text: str, candidates: List[str]) -> List[str]:
        """Extract matching trend tags from text (simple rule-based)."""
        text_lower = text.lower()
        found = []
        for tag in candidates:
            if tag.lower() in text_lower and tag not in found:
                found.append(tag)
        return found[:5]


CANDIDATE_TAGS = [
    "Quiet Luxury",
    "Balletcore",
    "Gorpcore",
    "Streetwear",
    "Sneakers",
    "Vintage",
    "Denim",
    "Leather",
    "Oversized",
    "Minimalism",
    "Sustainable Fashion",
    "Runway",
    "Collaboration",
    "Capsule",
    "Preppy",
    "Athleisure",
    "Tailoring",
    "Outerwear",
    "Footwear",
    "Accessories",
    "Womenswear",
    "Menswear",
    "Knitwear",
    "Prints",
    "Sheer",
    "Cutouts",
    "Boho",
    "Y2K",
    "Retro",
    "Workwear",
    "Jewelry",
    "Bags",
    "Swimwear",
    "Back to School",
    "Nike",
    "Adidas",
    "Jordan",
    "Zara",
    "H&M",
    "Beauty",
    "Makeup",
    "Watches",
    "Luxury",
    "Celebrity Style",
    "Copenhagen",
    "Fashion Week",
]


def attach_rule_tags(articles: List[Article]) -> None:
    for a in articles:
        text = f"{a.title} {a.description}"
        a.tags = Processor.extract_tags(text, CANDIDATE_TAGS)
