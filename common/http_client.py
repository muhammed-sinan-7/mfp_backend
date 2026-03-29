# apps/common/http_client.py

import requests

DEFAULT_TIMEOUT = 10


def get(url, **kwargs):
    return requests.get(url, timeout=DEFAULT_TIMEOUT, **kwargs)


def post(url, **kwargs):
    return requests.post(url, timeout=DEFAULT_TIMEOUT, **kwargs)


def put(url, **kwargs):
    return requests.put(url, timeout=DEFAULT_TIMEOUT, **kwargs)
