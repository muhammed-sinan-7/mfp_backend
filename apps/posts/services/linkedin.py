import requests
import time

from .base import BasePublisher


class LinkedInPublisher(BasePublisher):

    BASE_URL = "https://api.linkedin.com/v2"

    def publish(self, post_platform):

        social_account = post_platform.publishing_target.social_account
        caption = post_platform.caption or ""

        if not social_account.access_token:
            raise Exception("Missing LinkedIn access token")

        if social_account.is_token_expired():
            raise Exception("LinkedIn token expired")

        access_token = social_account.access_token

        person_id = social_account.external_id
        author_urn = f"urn:li:person:{person_id}"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        image = post_platform.media.filter(media_type="IMAGE").first()
        video = post_platform.media.filter(media_type="VIDEO").first()

        if video:
            media_urn = self._upload_video(video.file, access_token, person_id)
            share_media_category = "VIDEO"

        elif image:
            media_urn = self._upload_image(image.file, access_token, person_id)
            share_media_category = "IMAGE"

        else:
            media_urn = None
            share_media_category = "NONE"

        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": caption},
                    "shareMediaCategory": share_media_category,
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        if media_urn:
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                {
                    "status": "READY",
                    "media": media_urn,
                    "title": {"text": "Shared Image"},
                }
            ]

        print("FINAL PAYLOAD:", payload)

        response = requests.post(
            f"{self.BASE_URL}/ugcPosts", json=payload, headers=headers
        )

        print("POST RESPONSE:", response.status_code, response.text)

        if response.status_code not in [200, 201]:
            raise Exception(f"LinkedIn publish failed: {response.text}")

        return {"external_id": response.json().get("id")}

    def _wait_for_asset_ready(self, asset, access_token):
        """
        LinkedIn's /v2/assets/{urn} status endpoint is unreliable.
        After a successful PUT upload the asset is ready within a few seconds.
        A short sleep is the standard approach for this legacy API.
        """
        print(f"[ASSET READY] Waiting 4s for asset to process: {asset}")
        time.sleep(4)

    def _upload_image(self, file_field, access_token, person_id):

        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": f"urn:li:person:{person_id}",
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }

        register_res = requests.post(
            f"{self.BASE_URL}/assets?action=registerUpload",
            json=register_payload,
            headers=headers,
        )

        print("REGISTER IMAGE:", register_res.status_code, register_res.text)

        if register_res.status_code != 200:
            raise Exception(f"LinkedIn image register failed: {register_res.text}")

        data = register_res.json()

        upload_url = data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset = data["value"]["asset"]

        # ✅ S3-safe read
        file_field.open()
        file_bytes = file_field.read()
        file_field.close()

        upload_res = requests.put(
            upload_url,
            data=file_bytes,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/octet-stream",
            },
        )

        print("UPLOAD IMAGE:", upload_res.status_code, upload_res.text[:200])

        if upload_res.status_code not in [200, 201, 202]:
            raise Exception(f"LinkedIn image upload failed: {upload_res.status_code} {upload_res.text[:300]}")

        self._wait_for_asset_ready(asset, access_token)

        return asset

    def _upload_video(self, file_field, access_token, person_id):

        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
                "owner": f"urn:li:person:{person_id}",
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }

        register_res = requests.post(
            f"{self.BASE_URL}/assets?action=registerUpload",
            json=register_payload,
            headers=headers,
        )

        print("REGISTER VIDEO:", register_res.status_code, register_res.text)

        if register_res.status_code != 200:
            raise Exception(f"LinkedIn video register failed: {register_res.text}")

        data = register_res.json()

        upload_url = data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset = data["value"]["asset"]

        file_field.open()
        file_bytes = file_field.read()
        file_field.close()

        upload_res = requests.put(
            upload_url,
            data=file_bytes,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/octet-stream",
            },
        )

        print("UPLOAD VIDEO:", upload_res.status_code, upload_res.text[:200])

        if upload_res.status_code not in [200, 201, 202]:
            raise Exception(f"LinkedIn video upload failed: {upload_res.status_code} {upload_res.text[:300]}")

        self._wait_for_asset_ready(asset, access_token)

        return asset