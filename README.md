# US Trend Brief

每日自动聚合美国时尚趋势资讯，生成静态速报页面并部署到 GitHub Pages。

## 数据源

- **WWD** — 行业新闻、财报、时装周
- **Business of Fashion** — 商业与趋势深度分析
- **Highsnobiety** — 街头潮流、球鞋、联名
- **Hypebeast** — 街头/男装/球鞋 drop 资讯
- **Refinery29** — 女性时尚与生活方式
- **Who What Wear** — 女性穿搭与购物趋势

## 功能

- 每天自动抓取多个 RSS 源
- 按时间窗口和关键词过滤、去重
- 支持 LLM 自动提炼关键趋势词并生成摘要
- 生成响应式静态网页（PC / 手机友好）
- 自动归档历史速报
- 通过 GitHub Actions 定时部署到 GitHub Pages

## 本地运行

```bash
# 1. 进入项目目录
cd us-trend-brief

# 2. 创建虚拟环境并安装依赖
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. （可选）配置 OpenAI API Key 以启用 LLM 摘要
export OPENAI_API_KEY="sk-..."
# 可选：使用兼容 OpenAI 的其他服务（如 Kimi / DeepSeek）
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4o-mini"

# 4. 生成今日速报
python scripts/run_daily.py

# 5. 本地预览
python -m http.server 8000 --directory public
# 打开 http://localhost:8000
```

> 如果不配置 `OPENAI_API_KEY`，会自动回退到规则摘要（按分类统计关键词 + 一句话摘要）。

## 部署到 GitHub Pages

1. 在 GitHub 新建仓库，把本项目 push 上去：

```bash
git remote add origin https://github.com/<your-username>/us-trend-brief.git
git branch -M main
git push -u origin main
```

2. 进入 GitHub 仓库 → **Settings → Pages**：
   - **Source** 选择 **GitHub Actions**

3. （可选）配置 LLM API Key：
   - **Settings → Secrets and variables → Actions → New repository secret**
   - 添加 `OPENAI_API_KEY`
   - 如需非 OpenAI 端点，再添加 `OPENAI_BASE_URL` 和 `OPENAI_MODEL`

4. GitHub Actions 会在每天 UTC 08:00 自动运行，也可以手动触发：
   - **Actions → Daily US Trend Brief → Run workflow**

5. 部署完成后访问：
   ```
   https://<your-username>.github.io/us-trend-brief/
   ```

## 自定义配置

编辑 `config/sources.yaml`：

- 增删 RSS 源
- 调整关键词过滤
- 修改 `lookback_hours`（默认 48 小时，保证每天不漏文章）
- 修改站点名称和描述

## 项目结构

```
us-trend-brief/
├── .github/workflows/daily.yml   # GitHub Actions 自动部署
├── config/sources.yaml           # RSS 源与过滤规则
├── src/
│   ├── fetcher.py                # RSS 抓取
│   ├── processor.py              # 过滤、分类、标签
│   ├── summarizer.py             # LLM / 规则摘要
│   ├── generator.py              # HTML 生成
│   └── templates/index.html      # 速报页面模板
├── scripts/run_daily.py          # 每日运行入口
├── public/                       # GitHub Pages 输出目录
│   ├── index.html                # 最新速报
│   ├── archive/                  # 历史归档
│   └── assets/style.css          # 样式
├── data/                         # 原始 JSON 数据归档
└── requirements.txt
```

## 后续扩展

- [ ] 接入 Google Trends（`pytrends`）拉取热门时尚搜索词
- [ ] 接入 TikTok Creative Center / Pinterest Trends 社媒热度
- [ ] 增加邮件/飞书群推送
- [ ] 趋势词时间序列追踪与可视化

## License

MIT
