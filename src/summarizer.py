import json
import logging
import os
import re
from abc import ABC, abstractmethod
from collections import Counter
from typing import Any, Dict, List, Optional

import requests

from src.config import get_openai_api_key, get_openai_base_url, get_openai_model
from src.fetcher import Article
from src.processor import CANDIDATE_TAGS

logger = logging.getLogger(__name__)


class SummaryResult:
    def __init__(
        self,
        headline: str,
        trends: List[Dict[str, Any]],
        article_summaries: Dict[str, str],
    ):
        self.headline = headline
        self.trends = trends
        self.article_summaries = article_summaries

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "trends": self.trends,
            "article_summaries": self.article_summaries,
        }


class Summarizer(ABC):
    @abstractmethod
    def summarize(self, articles: List[Article]) -> SummaryResult:
        raise NotImplementedError


class OpenAISummarizer(Summarizer):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or get_openai_api_key()
        self.base_url = (base_url or get_openai_base_url()).rstrip("/")
        self.model = model or get_openai_model()

    def summarize(self, articles: List[Article]) -> SummaryResult:
        if not self.api_key:
            raise RuntimeError("OpenAI API key not configured")

        payload_articles = [
            {
                "id": a.id,
                "title": a.title,
                "source": a.source_name,
                "category": a.category,
                "description": a.description[:400],
            }
            for a in articles[:60]  # cap context
        ]

        system_prompt = (
            "You are a concise US fashion trend analyst. Given a list of recent fashion articles, "
            "identify the dominant trends and summarize each article in one sentence. "
            "Return ONLY valid JSON with no markdown formatting."
        )

        user_prompt = f"""Analyze these recent US fashion articles and return JSON:

{json.dumps(payload_articles, ensure_ascii=False, indent=2)}

Return this exact JSON structure:
{{
  "headline": "One sentence capturing today's overall trend signal",
  "trends": [
    {{
      "name": "Trend name (e.g. Quiet Luxury, Sneaker Collaborations)",
      "keywords": ["keyword1", "keyword2"],
      "summary": "2-3 sentences explaining why this trend matters today",
      "article_ids": ["id1", "id2"]
    }}
  ],
  "article_summaries": {{
    "id1": "One-line summary of the article",
    "id2": "One-line summary of the article"
  }}
}}

Rules:
- Pick 3-7 trends maximum.
- Each article id in article_summaries must correspond to an input id.
- article_ids under each trend should reference relevant articles.
- Be specific and fashion-forward."""

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.5,
                    "response_format": {"type": "json_object"},
                },
                timeout=120,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return SummaryResult(
                headline=parsed.get("headline", "Today's US fashion brief"),
                trends=parsed.get("trends", []),
                article_summaries=parsed.get("article_summaries", {}),
            )
        except Exception as e:
            logger.error(f"OpenAI summarization failed: {e}")
            raise


class RuleSummarizer(Summarizer):
    """Fallback summarizer when no LLM API key is available."""

    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
        "with", "by", "from", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "this", "that", "these", "those", "it",
        "its", "as", "you", "your", "we", "our", "us", "i", "my", "he", "she",
        "his", "her", "they", "them", "what", "when", "where", "how", "why", "who",
        "which", "there", "their", "them", "than", "then", "now", "here", "just",
        "only", "also", "back", "still", "already", "even", "more", "most", "some",
        "many", "much", "such", "very", "well", "about", "around", "over", "under",
        "into", "onto", "upon", "out", "off", "up", "down", "through", "between",
        "among", "during", "before", "after", "above", "below", "within", "without",
        "available", "like", "including", "included", "says", "said", "say", "get",
        "gets", "got", "getting", "make", "makes", "made", "making", "take", "takes",
        "took", "taking", "come", "comes", "came", "coming", "look", "looks", "looked",
        "looking", "use", "uses", "used", "using", "work", "works", "worked", "working",
        "time", "year", "years", "day", "days", "way", "ways", "new", "old", "first",
        "last", "next", "one", "two", "three", "good", "great", "best", "big", "small",
        "high", "low", "long", "short", "right", "left", "real", "really", "see", "seen",
        "know", "known", "think", "thought", "want", "wanted", "need", "needed", "find",
        "found", "give", "given", "every", "each", "other", "another", "same", "different",
    }

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r"\b[a-zA-Z][a-zA-Z\-']{3,}\b", text.lower())
        return [w for w in words if w not in self.STOPWORDS and not w.isdigit()]

    def summarize(self, articles: List[Article]) -> SummaryResult:
        if not articles:
            return SummaryResult(
                headline="No new articles today.", trends=[], article_summaries={}
            )

        all_text = " ".join(f"{a.title} {a.description}" for a in articles)
        tokens = self._tokenize(all_text)

        # Prefer fashion-specific candidate tags
        candidate_tags_lower = [tag.lower() for tag in CANDIDATE_TAGS]
        tag_counter = Counter(
            tag for tag in candidate_tags_lower
            for _ in range(all_text.lower().count(tag))
        )
        top_tags = [tag.title() for tag, _ in tag_counter.most_common(6)]

        # Fallback to general tokens if no candidate tags found
        if not top_tags:
            top_tags = [w for w, _ in Counter(tokens).most_common(6)]

        # Simple category trend detection
        cat_counter = Counter(a.category for a in articles)
        trends = []
        for category, count in cat_counter.most_common(4):
            cat_articles = [a for a in articles if a.category == category]
            sample_titles = [a.title for a in cat_articles[:3]]
            # Find tags most frequent within this category
            cat_text = " ".join(f"{a.title} {a.description}" for a in cat_articles)
            cat_tag_counter = Counter(
                tag for tag in candidate_tags_lower
                for _ in range(cat_text.lower().count(tag))
            )
            cat_keywords = [tag.title() for tag, _ in cat_tag_counter.most_common(4)]
            if not cat_keywords:
                cat_keywords = top_tags[:4]
            trends.append(
                {
                    "name": self._category_to_trend_name(category),
                    "keywords": cat_keywords,
                    "summary": (
                        f"{count} articles in this section today. "
                        f"Highlights include: {', '.join(sample_titles[:2])}."
                    ),
                    "article_ids": [a.id for a in cat_articles[:6]],
                }
            )

        article_summaries = {}
        for a in articles:
            article_summaries[a.id] = self._one_liner(a)

        category_names = ", ".join(
            self._category_to_trend_name(c) for c in cat_counter.keys()
        )
        headline = (
            f"Today sees {len(articles)} updates across {category_names}. "
            f"Top signals: {', '.join(top_tags[:5])}."
        )
        return SummaryResult(
            headline=headline, trends=trends, article_summaries=article_summaries
        )

    @staticmethod
    def _category_to_trend_name(category: str) -> str:
        mapping = {
            "industry": "Industry News",
            "streetwear": "Streetwear & Sneakers",
            "womenswear": "Women's Style",
        }
        return mapping.get(category, category.title())

    @staticmethod
    def _one_liner(a: Article) -> str:
        desc = a.description[:160].rsplit(" ", 1)[0]
        if desc and not desc.endswith((".", "!", "?")):
            desc += "..."
        return desc or a.title


def create_summarizer(prefer_llm: bool = True) -> Summarizer:
    if prefer_llm and get_openai_api_key():
        return OpenAISummarizer()
    logger.info("Using rule-based summarizer (no OPENAI_API_KEY configured)")
    return RuleSummarizer()
