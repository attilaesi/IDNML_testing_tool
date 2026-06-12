"""
core/ima_base_test.py

Base class for IMA (video) GAM key-value tests.

Key-values sent to GAM from the video player travel inside the cust_params
query parameter of the VAST ad tag URL.  framework_manager registers the
network listener and clicks the play button ONCE per URL before any tests run,
so window.__imaAdRequest is populated by the time tests start polling.

Subclasses only need to implement execute() and validate(); setup() and
the _targeting() helper are provided here.
"""

import asyncio
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs, unquote as _unquote

from core.base_test import VideoOnlyTest, TestResult, TestState

_IMA_ENDPOINTS = (
    'https://pubads.g.doubleclick.net/gampad/ads',
    'https://pagead2.googlesyndication.com/gampad/ads',
    'https://pubads.g.doubleclick.net/gampad/live/ads',
    'https://pagead2.googlesyndication.com/gampad/live/ads',
)


class ImaBaseTest(VideoOnlyTest):
    """Base for IMA cust_params key-value tests. Runs on video pages only."""

    _IMA_TIMEOUT = 25.0
    _IMA_POLL_INTERVAL = 0.2

    async def _video_setup(self, page, url: str) -> bool:
        # The runner (framework_manager) registered the primary IMA listener and
        # clicked the play button before any tests started. IMA tests block here
        # until window.__imaAdRequest is set — display tests never call this and
        # are completely unaffected.
        attempts = int(self._IMA_TIMEOUT / self._IMA_POLL_INTERVAL)
        for _ in range(attempts):
            if await page.evaluate("!!(window.__imaAdRequest)"):
                return True
            await asyncio.sleep(self._IMA_POLL_INTERVAL)

        # Timeout — IMA request never fired. Return True so execute() can still
        # read None from window.__imaAdRequest and produce a SKIPPED result.
        return True

    async def _fetch_cust_params(self, page) -> Optional[Dict[str, str]]:
        """
        Read window.__imaAdRequest. By the time this is called, _video_setup has
        already waited for it — so this is a single read, no polling needed.
        """
        data = await page.evaluate("window.__imaAdRequest || null")
        if data:
            cust_params = data.get("cust_params") or {}
            if self.config.get("trace"):
                print(f"[{self.name}] IMA cust_params captured: {cust_params}")
            return cust_params
        if self.config.get("trace"):
            print(f"[{self.name}] IMA cust_params not captured after {self._IMA_TIMEOUT}s")
        return None

    def _targeting(self, cust_params: Dict[str, str], key: str) -> List[str]:
        """
        Return a list of values for the key.
        [] = key missing; [''] = key present but empty; ['value'] = key present with value.
        """
        if not cust_params:
            return []
        if key not in cust_params:
            return []
        val = cust_params[key]
        s = str(val).strip() if val is not None else ""
        return [s] if s else [""]
