#!/usr/bin/env python3
"""Daily runner: fetch, filter, summarize, and generate US Trend Brief."""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from src.config import load_config
from src.fetcher import fetch_all
from src.generator import SiteGenerator
from src.processor import Processor, attach_rule_tags
from src.summarizer import create_summarizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> int:
    config = load_config()
    logger.info(f"Loaded {len(config.sources)} sources")

    # 1. Fetch
    raw_articles = await fetch_all(config.sources)
    logger.info(f"Total raw articles: {len(raw_articles)}")

    # 2. Filter & deduplicate
    processor = Processor(config)
    articles = processor.filter_articles(raw_articles)
    logger.info(f"After filtering: {len(articles)}")

    if not articles:
        logger.warning("No articles matched today's criteria; skipping generation")
        return 0

    # 3. Attach rule-based tags regardless of LLM usage
    attach_rule_tags(articles)

    # 4. Summarize
    summarizer = create_summarizer(prefer_llm=True)
    try:
        summary = summarizer.summarize(articles)
    except Exception as e:
        logger.error(f"LLM summarizer failed, falling back to rule-based: {e}")
        summary = create_summarizer(prefer_llm=False).summarize(articles)

    # 5. Generate site
    date_label = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    generator = SiteGenerator(config)
    generator.copy_assets()
    index_path = generator.generate(articles, summary, date_label=date_label)

    logger.info(f"Generated brief at {index_path}")
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted")
        exit_code = 1
    sys.exit(exit_code)
