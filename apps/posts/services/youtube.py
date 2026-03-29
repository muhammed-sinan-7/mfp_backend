from django.conf import settings
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .base import BasePublisher


class YouTubePublisher(BasePublisher):

    def publish(self, post_platform):

        social_account = post_platform.publishing_target.social_account
        post = post_platform.post

        media = post_platform.media.all().filter(media_type="VIDEO").first()

        if not media:
            raise Exception("YouTube requires a video file")

        credentials = Credentials(
            token=social_account.access_token,
            refresh_token=social_account.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )

        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

            social_account.access_token = credentials.token
            social_account.token_expires_at = timezone.now() + timezone.timedelta(
                seconds=3600
            )
            social_account.save(update_fields=["access_token", "token_expires_at"])

        youtube = build("youtube", "v3", credentials=credentials)

        caption = post_platform.caption or "Untitled Video"

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": caption[:90],
                    "description": caption,
                },
                "status": {"privacyStatus": "public"},
            },
            media_body=MediaFileUpload(media.file.path, chunksize=-1, resumable=True),
        )

        response = request.execute()

        return {"external_id": response.get("id")}
