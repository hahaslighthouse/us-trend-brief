import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional

import aiohttp
import feedparser
from dateutil import parser as date_parser

from src.config import Source

logger = logging.getLogger(__name__)


class Article:
    def __init__(
        self,
        title: str,
        link: str,
        description: str,
        source_name: str,
        category: str,
        published_at: Optional[datetime] = None,
        image_url: Optional[str] = None,
        categories: Optional[List[str]] = None,
    ):
        self.title = title.strip()
        self.link = link.strip()
        self.description = self._clean_description(description)
        self.source_name = source_name
        self.category = category
        self.published_at = published_at or datetime.now(timezone.utc)
        self.image_url = image_url
        self.categories = categories or []
        self.id = hashlib.sha256(f"{source_name}:{link}".encode()).hexdigest()[:16]

    @staticmethod
    def _unescape_url(url: str) -> str:
        if not url:
            return url
        return url.replace("&amp;", "&")

    @staticmethod
    def _clean_description(raw: str) -> str:
        if not raw:
            return ""
        # Strip common HTML tags roughly; feed content often contains CDATA.
        import re

        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "description": self.description,
            "source_name": self.source_name,
            "category": self.category,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "image_url": self.image_url,
            "categories": self.categories,
        }


def _extract_categories(entry) -> List[str]:
    terms = []
    for key in ("tags", "category"):
        value = entry.get(key)
        if not value:
            continue
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    term = item.get("term", "")
                else:
                    term = str(item)
                if term:
                    terms.append(term)
        elif isinstance(value, dict):
            terms.append(value.get("term", ""))
        else:
            terms.append(str(value))
    # Decode XML entities like &amp; in category names
    return [t.replace("&amp;", "&") for t in terms if t]


def _extract_image(entry) -> Optional[str]:
    # Try media:content / media:thumbnail
    if "media_content" in entry:
        for media in entry.media_content:
            if isinstance(media, dict) and media.get("url"):
                return media["url"]
    if "media_thumbnail" in entry:
        for thumb in entry.media_thumbnail:
            if isinstance(thumb, dict) and thumb.get("url"):
                return thumb["url"]
    # Try content:encoded first image
    content = entry.get("content", [{}])[0].get("value", "")
    if not content:
        content = entry.get("summary", "")
    import re

    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if m:
        return m.group(1)
    return None


def _parse_pub_date(entry) -> Optional[datetime]:
    for key in ("published", "updated", "pubDate"):
        if key in entry:
            try:
                return date_parser.parse(entry[key])
            except Exception:
                continue
    return None


async def _fetch_one(
    session: aiohttp.ClientSession, source: Source
) -> List[Article]:
    logger.info(f"Fetching {source.name} from {source.url}")
    try:
        async with session.get(
            source.url, timeout=aiohttp.ClientTimeout(total=30), headers={"User-Agent": "us-trend-brief/1.0"}
        ) as resp:
            resp.raise_for_status()
            xml_bytes = await resp.read()
    except Exception as e:
        logger.error(f"Failed to fetch {source.name}: {e}")
        return []

    feed = feedparser.parse(xml_bytes)
    articles = []
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue
        description = entry.get("summary", entry.get("description", ""))
        published = _parse_pub_date(entry)
        image = Article._unescape_url(_extract_image(entry))
        categories = _extract_categories(entry)
        articles.append(
            Article(
                title=title,
                link=link,
                description=description,
                source_name=source.name,
                category=source.category,
                published_at=published,
                image_url=image,
                categories=categories,
            )
        )
    logger.info(f"Fetched {len(articles)} articles from {source.name}")
    return articles


async def fetch_all(sources: List[Source], max_concurrent: int = 6) -> List[Article]:
    connector = aiohttp.TCPConnector(limit=max_concurrent)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [_fetch_one(session, s) for s in sources]
        results = await asyncio.gather(*tasks)
    all_articles = [a for sublist in results for a in sublist]
    all_articles.sort(key=lambda x: x.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return all_articles
