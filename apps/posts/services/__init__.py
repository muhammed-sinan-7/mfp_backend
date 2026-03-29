from apps.social_accounts.models import SocialProvider

from .instagram import InstagramPublisher
from .linkedin import LinkedInPublisher
from .youtube import YouTubePublisher


def get_publisher(provider: str):

    if provider == SocialProvider.LINKEDIN:
        return LinkedInPublisher()

    if provider == SocialProvider.INSTAGRAM:
        return InstagramPublisher()

    if provider == SocialProvider.YOUTUBE:
        return YouTubePublisher()

    raise ValueError(f"No publisher found for provider: {provider}")
