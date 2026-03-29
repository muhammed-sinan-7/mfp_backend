import logging

from apps.social_accounts.models import (
    MetaPage,
    PublishingTarget,
    SocialProvider,
)

from .meta import MetaOAuthService

logger = logging.getLogger(__name__)


class MetaSyncService:

    @staticmethod
    def sync_pages(social_account):
        oauth_service = MetaOAuthService()

        pages_data = oauth_service.fetch_pages(user_token=social_account.access_token)

        synced_targets = []

        for page in pages_data.get("data", []):

            page_id = page["id"]
            page_name = page["name"]
            page_token = page["access_token"]

            # 1️⃣ Create/Update MetaPage (THIS WAS MISSING)
            meta_page, _ = MetaPage.objects.update_or_create(
                social_account=social_account,
                page_id=page_id,
                defaults={
                    "name": page_name,
                    "page_access_token": page_token,
                },
            )

            # 2️⃣ Create PublishingTarget for Facebook Page
            publishing_target, _ = PublishingTarget.objects.update_or_create(
                social_account=social_account,
                provider=SocialProvider.META,
                resource_id=page_id,
                defaults={
                    "display_name": page_name,
                    "metadata": page,
                },
            )

            synced_targets.append(publishing_target)

            # 3️⃣ Fetch Instagram Business Account
            try:
                ig_data = page.get("instagram_business_account") or oauth_service.fetch_instagram_account(
                    page_id=page_id, page_token=page_token
                )

                if ig_data and ig_data.get("id"):

                    ig_id = ig_data["id"]

                    ig_profile = {}
                    try:
                        ig_profile = oauth_service.fetch_instagram_profile(
                            ig_id=ig_id, page_token=page_token
                        ) or {}
                    except Exception as profile_exc:
                        logger.warning(
                            "Instagram profile fetch failed for ig_id %s (page %s): %s",
                            ig_id,
                            page_id,
                            str(profile_exc),
                        )

                    # 4️⃣ Update MetaPage with IG Business ID
                    meta_page.instagram_business_id = ig_id
                    meta_page.save(update_fields=["instagram_business_id"])

                    # 5️⃣ Create PublishingTarget for Instagram
                    ig_display_name = (
                        ig_profile.get("username")
                        or page.get("name")
                        or page_name
                        or f"instagram-{ig_id}"
                    )
                    ig_target, _ = PublishingTarget.objects.update_or_create(
                        social_account=social_account,
                        provider=SocialProvider.INSTAGRAM,
                        resource_id=ig_id,
                        defaults={
                            "display_name": ig_display_name,
                            "metadata": ig_profile,
                        },
                    )

                    synced_targets.append(ig_target)

            except Exception as e:
                logger.warning("Instagram sync failed for page %s: %s", page_id, str(e))

        return synced_targets
