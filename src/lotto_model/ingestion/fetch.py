import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

import httpx

from lotto_model.ingestion.evidence import EvidenceStore

RESTRICTED = {
    "irish.national-lottery.com": "Published terms prohibit data harvesting",
    "www.irishlottery.com": "Published terms prohibit data harvesting",
    "www.lottery.ie": "Extraction requires permission; personal reference only",
    "www.lottery.co.uk": "Published terms prohibit data harvesting",
    "pickmysix.com": "Direct access returned HTTP 403 during discovery",
}


class AccessPolicy:
    def __init__(self, allowed=None, crawl_delays=None):
        self.allowed = allowed or {}
        self.crawl_delays = crawl_delays or {}

    def check(self, url):
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise ValueError("Only unauthenticated HTTPS evidence URLs allowed")
        if parsed.hostname in RESTRICTED:
            raise ValueError(RESTRICTED[parsed.hostname])
        if any(
            part in ("play", "account", "checkout") for part in parsed.path.split("/")
        ):
            raise ValueError("Interactive routes are outside ingestion scope")
        prefixes = self.allowed.get(parsed.hostname, ())
        if not any(
            parsed.path == p or parsed.path.startswith(p.rstrip("/") + "/")
            for p in prefixes
        ):
            raise ValueError("Source has no reviewed acquisition policy")


class Fetcher:
    def __init__(
        self,
        store: EvidenceStore,
        *,
        client=None,
        policy=None,
        sleep=time.sleep,
        clock=time.monotonic,
        max_requests=100,
    ):
        self.store = store
        self.client = client or httpx.Client(
            timeout=20, headers={"User-Agent": "lotto-model-research/0.1"}
        )
        self.policy = policy or AccessPolicy()
        self.sleep, self.clock = sleep, clock
        self.last_request = {}
        self.blocked = set()
        self.max_requests, self.requests = max_requests, 0

    def fetch(self, url: str, refresh=False, validator=None):
        self.policy.check(url)
        if not refresh and (cached := self.store.cached(url)):
            if validator and not validator(self.store.read(cached)):
                raise ValueError("Cached evidence fails content validation")
            return cached
        host = urlparse(url).hostname
        if host in self.blocked:
            raise ValueError("Host stopped after access denial")
        current = url
        last_artifact = None
        redirects = 0
        attempts = 0
        while attempts < 3:
            self.policy.check(current)
            current_host = urlparse(current).hostname
            if current_host in self.blocked:
                raise ValueError("Host stopped after access denial")
            if self.requests >= self.max_requests:
                raise ValueError("Request budget exhausted; resume with saved evidence")
            delay = max(
                0,
                max(2, self.policy.crawl_delays.get(current_host, 0))
                - (self.clock() - self.last_request.get(current_host, float("-inf"))),
            )
            if delay:
                if delay > 60:
                    raise ValueError(
                        f"Collection deferred for host crawl delay: {delay:.0f}s"
                    )
                self.sleep(delay)
            self.requests += 1
            self.last_request[current_host] = self.clock()
            try:
                response = self.client.get(current, follow_redirects=False)
            except httpx.TransportError:
                attempts += 1
                last_artifact = self.store.write(
                    b"",
                    url=url,
                    final_url=current,
                    http_status=None,
                    content_type=None,
                    status="error",
                )
                self.sleep(2**attempts)
                continue
            body = response.content
            captcha = any(
                x in body[:10000].lower()
                for x in (
                    b"<title>just a moment",
                    b"<title>captcha",
                    b"cf-chl-",
                    b"access denied",
                )
            )
            status = (
                "blocked"
                if response.status_code in (401, 403) or captcha
                else ("valid" if response.status_code == 200 else "error")
            )
            if status == "valid" and validator and not validator(body):
                status = "invalid"
            last_artifact = self.store.write(
                body,
                url=url,
                final_url=current,
                http_status=response.status_code,
                content_type=response.headers.get("content-type"),
                status=status,
            )
            if status == "blocked":
                self.blocked.add(current_host)
                return last_artifact
            if response.is_redirect:
                redirects += 1
                if redirects > 5:
                    raise ValueError("Too many redirects")
                current = urljoin(current, response.headers.get("location", ""))
                continue
            if response.status_code == 429 or response.status_code >= 500:
                attempts += 1
                retry = response.headers.get("retry-after", "")
                retry_delay = 0
                if retry.isdigit():
                    retry_delay = float(retry)
                elif retry:
                    try:
                        retry_delay = max(
                            0,
                            (
                                parsedate_to_datetime(retry)
                                - datetime.now(timezone.utc)
                            ).total_seconds(),
                        )
                    except (ValueError, TypeError, OverflowError):
                        pass
                delay = max(2**attempts, retry_delay)
                if delay > 60:
                    raise ValueError(
                        f"Collection deferred by Retry-After: {delay:.0f}s"
                    )
                self.sleep(delay)
                continue
            return last_artifact
        return last_artifact
