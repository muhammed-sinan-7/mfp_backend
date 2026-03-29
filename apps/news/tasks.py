import logging

from celery import shared_task

from apps.industries.models import Industry

from .services.rss_ingestion_service import RSSIntegrationService

logger = logging.getLogger(__name__)


@shared_task
def ingest_news_for_industry(industry_id):
    service = RSSIntegrationService()
    service.run(industry_id=industry_id)


@shared_task
def ingest_all_news():
    industries = Industry.objects.values_list("id", flat=True)

    for industry_id in industries:
        ingest_news_for_industry.delay(industry_id)

    logger.info(f"Dispatched news ingestion for {len(industries)} industries")
