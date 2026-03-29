import time
from urllib.parse import urljoin

import requests
from django.conf import settings
from PIL import Image
from rest_framework.exceptions import ValidationError

from apps.social_accounts.models import MetaPage

from .base import BasePublisher


class InstagramPublisher(BasePublisher):

    BASE_URL = "https://graph.facebook.com/v18.0"

    def publish(self, post_platform):

        publishing_target = post_platform.publishing_target

        media_items = post_platform.media.all().order_by("order")

        if not media_items.exists():
            raise Exception("Instagram requires media")

        ig_user_id = publishing_target.resource_id

        meta_page = MetaPage.objects.filter(
            social_account=publishing_target.social_account,
            instagram_business_id=ig_user_id,
        ).first()

        if not meta_page:
            raise Exception("MetaPage not linked to Instagram account")

        access_token = meta_page.page_access_token

        create_url = f"{self.BASE_URL}/{ig_user_id}/media"

        if media_items.count() == 1:

            media = media_items.first()

            file_url = urljoin(settings.BASE_URL, media.file.url)

            payload = {
                "caption": post_platform.caption or "",
                "access_token": access_token,
            }

            if media.media_type == "IMAGE":
                payload["image_url"] = file_url

            elif media.media_type == "VIDEO":
                payload["video_url"] = file_url
                payload["media_type"] = "REELS"

            create_res = requests.post(create_url, data=payload, timeout=10)

            if create_res.status_code != 200:
                raise Exception(create_res.text)

            container_id = create_res.json()["id"]

        else:

            children = []

            for media in media_items:

                file_url = urljoin(settings.BASE_URL, media.file.url)

                payload = {
                    "is_carousel_item": True,
                    "access_token": access_token,
                }

                if media.media_type == "IMAGE":
                    payload["image_url"] = file_url

                else:
                    payload["video_url"] = file_url
                    payload["media_type"] = "REELS"

                child_res = requests.post(create_url, data=payload)

                if child_res.status_code != 200:
                    raise Exception(child_res.text)

                children.append(child_res.json()["id"])

            carousel_payload = {
                "media_type": "CAROUSEL",
                "children": ",".join(children),
                "caption": post_platform.caption or "",
                "access_token": access_token,
            }

            carousel_res = requests.post(create_url, data=carousel_payload)

            if carousel_res.status_code != 200:
                raise Exception(carousel_res.text)

            container_id = carousel_res.json()["id"]

        status_url = f"{self.BASE_URL}/{container_id}"

        for _ in range(10):

            status_res = requests.get(
                status_url,
                params={
                    "fields": "status_code",
                    "access_token": access_token,
                },
            )

            status = status_res.json().get("status_code")

            if status == "FINISHED":
                break

            if status == "ERROR":
                raise Exception("Instagram media processing failed")

            time.sleep(5)

        publish_url = f"{self.BASE_URL}/{ig_user_id}/media_publish"

        publish_payload = {
            "creation_id": container_id,
            "access_token": access_token,
        }

        publish_res = requests.post(publish_url, data=publish_payload)

        if publish_res.status_code != 200:
            raise Exception(publish_res.text)

        return {"external_id": publish_res.json()["id"]}
