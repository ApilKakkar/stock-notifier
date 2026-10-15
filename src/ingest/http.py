"""HTTP session with retries. No personal details are sent by default."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_UA = "ml-ops-finance-research/0.1 (personal research project)"


def session(user_agent: str | None = None) -> requests.Session:
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers["User-Agent"] = user_agent or DEFAULT_UA
    return s
