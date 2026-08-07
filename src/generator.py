import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import Config
from src.fetcher import Article
from src.processor import Processor
from src.summarizer import SummaryResult


CATEGORY_NAMES = {
    "industry": "Industry News",
    "streetwear": "Streetwear & Sneakers",
    "womenswear": "Women's Style",
}


class SiteGenerator:
    def __init__(self, config: Config, public_dir: Optional[Union[Path, str]] = None):
        self.config = config
        self.repo_root = Path(__file__).resolve().parent.parent
        self.public_dir = Path(public_dir) if public_dir else self.repo_root / "public"
        self.archive_dir = self.public_dir / "archive"
        self.data_dir = self.repo_root / "data"
        self.template_dir = Path(__file__).resolve().parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate(
        self,
        articles: List[Article],
        summary: SummaryResult,
        date_label: Optional[str] = None,
    ) -> Path:
        self.public_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        date_str = date_label or now.strftime("%Y-%m-%d")

        groups = Processor.group_by_category(articles)

        # Prepare article display metadata
        for a in articles:
            a.published_at_short = self._format_short_date(a.published_at)

        # Build tag cloud data
        tag_cloud = self._build_tag_cloud(articles)

        # Render index.html
        template = self.env.get_template("index.html")
        html = template.render(
            site_name=self.config.settings.site_name,
            site_description=self.config.settings.site_description,
            date_str=date_str,
            generated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
            articles=articles,
            groups=groups,
            category_names=CATEGORY_NAMES,
            summary=summary,
            tag_cloud=tag_cloud,
        )

        index_path = self.public_dir / "index.html"
        index_path.write_text(html, encoding="utf-8")

        # Archive copy
        archive_path = self.archive_dir / f"{date_str}.html"
        archive_path.write_text(html, encoding="utf-8")

        # JSON data for downstream use
        data = {
            "date": date_str,
            "generated_at": now.isoformat(),
            "summary": summary.to_dict(),
            "articles": [a.to_dict() for a in articles],
        }
        data_path = self.data_dir / f"{date_str}.json"
        data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Archive listing page
        self._generate_archive_index()

        return index_path

    def _generate_archive_index(self) -> None:
        archive_pages = sorted(
            [p for p in self.archive_dir.glob("*.html") if p.name != "index.html"],
            reverse=True,
        )
        links = [f'<li><a href="{p.name}">{p.stem}</a></li>' for p in archive_pages]
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Archive — {self.config.settings.site_name}</title>
  <link rel="stylesheet" href="../assets/style.css">
</head>
<body>
  <header class="site-header">
    <div class="container">
      <h1>Archive</h1>
      <p class="subtitle">Past daily briefs</p>
    </div>
  </header>
  <main class="container">
    <ul class="archive-list">
      {''.join(links)}
    </ul>
  </main>
  <footer class="site-footer">
    <div class="container">
      <p><a href="../">← Back to latest</a></p>
    </div>
  </footer>
</body>
</html>"""
        (self.archive_dir / "index.html").write_text(html, encoding="utf-8")

    @staticmethod
    def _build_tag_cloud(articles: List[Article]) -> List[Dict[str, Any]]:
        tag_map: Dict[str, List[str]] = defaultdict(list)
        for a in articles:
            for tag in a.tags:
                tag_map[tag].append(a.id)
        # Sort by count desc, then name
        sorted_tags = sorted(tag_map.items(), key=lambda x: (-len(x[1]), x[0]))
        max_count = max((len(ids) for _, ids in sorted_tags), default=1)
        return [
            {
                "name": tag,
                "count": len(ids),
                "article_ids": ids,
                "weight": round(0.75 + 1.25 * (len(ids) / max_count), 2),
            }
            for tag, ids in sorted_tags
        ]

    @staticmethod
    def _format_short_date(dt: Optional[datetime]) -> str:
        if not dt:
            return ""
        return dt.strftime("%b %d, %H:%M")

    def copy_assets(self) -> None:
        src_assets = self.repo_root / "public" / "assets"
        dst_assets = self.public_dir / "assets"
        if src_assets.exists() and dst_assets != src_assets:
            shutil.copytree(src_assets, dst_assets, dirs_exist_ok=True)
