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
    # Set by _fetch_cust_params() when the prerequisite chain broke; used by subclass validate().
    _ima_chain_error: str = "No IMA ad request captured."

    async def _video_setup(self, page, url: str) -> bool:
        # Bail immediately if the framework already determined no player exists.
        if await page.evaluate("!!(window.__imaPlayerAbsent)"):
            return True

        # The runner (framework_manager) registered the primary IMA listener and
        # clicked the play button before any tests started. IMA tests block here
        # until window.__imaAdRequest is set — display tests never call this and
        # are completely unaffected.
        attempts = int(self._IMA_TIMEOUT / self._IMA_POLL_INTERVAL)
        for _ in range(attempts):
            if await page.evaluate("!!(window.__imaAdRequest)"):
                return True
            await asyncio.sleep(self._IMA_POLL_INTERVAL)

        return True

    async def _fetch_cust_params(self, page) -> Optional[Dict[str, str]]:
        """
        Read window.__imaAdRequest. Sets self._ima_chain_error with a chain-specific
        diagnosis when no request was captured, so validate() can report exactly
        where in the video → player → IMA chain the failure occurred.
        """
        data = await page.evaluate("window.__imaAdRequest || null")
        if data:
            cust_params = data.get("cust_params") or {}
            if self.config.get("trace"):
                print(f"[{self.name}] IMA cust_params captured: {cust_params}")
            return cust_params

        # Walk the chain to find where it broke.
        try:
            if await page.evaluate("!!(window.__imaPlayerAbsent)"):
                self._ima_chain_error = (
                    "JW Player did not appear in DOM — "
                    "video page has no active autoplay player or player took too long to load"
                )
            elif await page.evaluate("!!(window.__imaVideoSetupDone)"):
                self._ima_chain_error = (
                    "JW Player loaded and play was triggered but no IMA VAST request was captured — "
                    "ad break did not fire or was blocked by the player"
                )
            else:
                self._ima_chain_error = (
                    "No IMA ad request captured — "
                    "player setup did not complete (check framework logs for video setup details)"
                )
        except Exception:
            self._ima_chain_error = "No IMA ad request captured."

        if self.config.get("trace"):
            print(f"[{self.name}] IMA fail reason: {self._ima_chain_error}")
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
