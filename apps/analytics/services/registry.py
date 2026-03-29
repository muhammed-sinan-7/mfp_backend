from . import instagram, linkedin, youtube

FETCHERS = {
    "instagram": instagram.fetch,
    "meta": instagram.fetch,
    "youtube": youtube.fetch,
    "linkedin": linkedin.fetch,
}
