import logging
from datetime import datetime, timezone

import feedparser
import requests
from bs4 import BeautifulSoup
from django.utils import timezone as dj_timezone
from newspaper import Article

from apps.ai.services.llm_service import AIService

from ..models import NewsArticle, NewsSource

logger = logging.getLogger(__name__)


class RSSIntegrationService:

    # -----------------------------
    # CLEAN HTML (CORE FIX)
    # -----------------------------
    def clean_html(self, html):
        if not html:
            return ""

        soup = BeautifulSoup(html, "html.parser")

        # Remove scripts/styles
        for tag in soup(["script", "style"]):
            tag.decompose()

        return soup.get_text(separator=" ", strip=True)

    # -----------------------------
    # FULL ARTICLE EXTRACTION
    # -----------------------------
    def extract_full_content(self, url):
        try:
            article = Article(url)
            article.download()
            article.parse()
            return article.text[:8000]
        except Exception:
            return ""

    # -----------------------------
    # FETCH SOURCES
    # -----------------------------
    def fetch_sources(self, industry_id=None):
        qs = NewsSource.objects.filter(is_active=True)

        if industry_id:
            qs = qs.filter(industry_id=industry_id)

        return qs

    # -----------------------------
    # PARSE FEED
    # -----------------------------
    def parse_feed(self, source):
        feed = feedparser.parse(source.rss_url)

        if feed.bozo:
            logger.warning(f"Invalid feed: {source.rss_url}")
            return None

        return feed

    # -----------------------------
    # OG IMAGE EXTRACTION
    # -----------------------------
    def extract_og_image(self, url):
        try:
            response = requests.get(url, timeout=5)
            soup = BeautifulSoup(response.text, "html.parser")

            tag = soup.find("meta", property="og:image")
            if tag:
                return tag.get("content")

        except Exception:
            return None

        return None

    # -----------------------------
    # IMAGE EXTRACTION (ROBUST)
    # -----------------------------
    def extract_image(self, entry):
        image_url = None

        if hasattr(entry, "media_content"):
            media = entry.media_content
            if media:
                image_url = media[0].get("url")

        if not image_url and hasattr(entry, "media_thumbnail"):
            thumb = entry.media_thumbnail
            if thumb:
                image_url = thumb[0].get("url")

        if not image_url and hasattr(entry, "enclosures"):
            enclosure = entry.enclosures
            if enclosure:
                image_url = enclosure[0].get("href")

        if not image_url and hasattr(entry, "content"):
            soup = BeautifulSoup(entry.content[0].value, "html.parser")
            img = soup.find("img")
            if img:
                image_url = img.get("src")

        if not image_url and hasattr(entry, "summary"):
            soup = BeautifulSoup(entry.summary, "html.parser")
            img = soup.find("img")
            if img:
                image_url = img.get("src")

        if not image_url:
            image_url = self.extract_og_image(getattr(entry, "link", ""))

        return image_url

    # -----------------------------
    # EXTRACT ARTICLE DATA
    # -----------------------------
    def extract_articles(self, entry, source):

        published_time = getattr(entry, "published_parsed", None)

        if published_time:
            published_time = datetime(*published_time[:6], tzinfo=timezone.utc)
        else:
            published_time = dj_timezone.now()

        raw_summary = getattr(entry, "summary", "")
        clean_summary = self.clean_html(raw_summary)

        data = {
            "title": getattr(entry, "title", ""),
            "summary": clean_summary,  # ✅ cleaned
            "raw_summary": raw_summary,  # optional (store if needed)
            "url": getattr(entry, "link", ""),
            "image": self.extract_image(entry),
            "source": source,
            "industry": source.industry,
            "published_at": published_time,
        }

        return data

    # -----------------------------
    # AI SUMMARY
    # -----------------------------
    def generate_ai_summary(self, title, content):
        try:
            if not content:
                return ""

            ai = AIService()

            prompt = f"""
You are a senior industry analyst.

Summarize this article clearly and insightfully.

Title: {title}

Content:
{content}

RULES:
- 6–10 lines
- Explain what happened
- Why it matters
- Key insights
- No fluff
"""

            result = ai.chat([{"role": "user", "content": prompt}])

            return result.get("response", "")

        except Exception:
            return ""

    # -----------------------------
    # SAVE ARTICLE
    # -----------------------------
    def save_articles(self, data):

        if NewsArticle.objects.filter(url=data["url"]).exists():
            return None

        full_content = self.extract_full_content(data["url"])

        content_to_use = full_content if full_content else data["summary"]

        ai_summary = ""
        if len(content_to_use) > 500:
            ai_summary = self.generate_ai_summary(data["title"], content_to_use)

        return NewsArticle.objects.create(
            title=data["title"],
            summary=data["summary"],
            content=full_content,
            ai_summary=ai_summary,
            url=data["url"],
            image=data["image"],
            source=data["source"],
            industry=data["industry"],
            published_at=data["published_at"],
        )

    # -----------------------------
    # MAIN RUNNER
    # -----------------------------
    def run(self, industry_id=None):
        sources = self.fetch_sources(industry_id=industry_id)

        existing_urls = set(NewsArticle.objects.values_list("url", flat=True))

        total_processed = 0
        total_created = 0

        for source in sources:
            try:
                feed = self.parse_feed(source)

                if not feed or not hasattr(feed, "entries"):
                    continue

                for entry in feed.entries[:10]:
                    try:
                        article_data = self.extract_articles(entry, source)

                        if not article_data["url"]:
                            continue

                        if article_data["url"] in existing_urls:
                            continue

                        total_processed += 1

                        created = self.save_articles(article_data)

                        if created:
                            total_created += 1
                            existing_urls.add(article_data["url"])

                    except Exception as e:
                        logger.warning(f"Entry failed: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Source failed: {source.rss_url}", exc_info=True)

        logger.info(
            f"News fetch completed | processed={total_processed}, created={total_created}"
        )
