import asyncio
from typing import Any, List, Tuple


class CMPHandler:
    """
    Handles CMP consent banners.

    Strategy:
      - Try a sequence of known CSS/XPath selectors on the top page, then inside iframes.
      - Click the first matching "accept"/"continue"/"consent-or-pay" style button.
      - Only do this once per browser session via `self.cmp_handled`.
    """

    def __init__(self, config: dict):
        self.config = config
        self.cmp_handled: bool = False

    # ─────────────────────────────────────────────────────────────────
    # Backwards-compatible entry point expected by the framework
    # ─────────────────────────────────────────────────────────────────
    async def handle_consent(self, page: Any, timeout: int = 10) -> None:
        """
        Attempt to dismiss CMP once. Safe no-op if already handled.
        """
        if self.cmp_handled:
            return
        clicked = await self._dismiss_any_cmp(page, timeout=timeout)
        if clicked:
            self.cmp_handled = True

    # Optional new name if you want to call it directly elsewhere.
    async def dismiss_cmp(self, page: Any, timeout: int = 10) -> bool:
        return await self._dismiss_any_cmp(page, timeout=timeout)

    # ─────────────────────────────────────────────────────────────────
    # Internal implementation
    # ─────────────────────────────────────────────────────────────────
    async def _dismiss_any_cmp(self, page: Any, timeout: int = 10) -> bool:
        deadline = asyncio.get_event_loop().time() + timeout

        # Primary site-specific selectors (from your provided CSS)
        eu_selectors: List[str] = [
            # EU accept button (desktop & mobile path is the same as provided)
            "#notice > div.message-component.message-row.main-container > div:nth-child(2) > div.message-component.message-row.cta-container > button.message-component.message-button.no-children.focusable.sp_choice_type_11.last-focusable-el",
        ]
        uk_cop_selectors: List[str] = [
            # UK consent-or-pay
            "#notice > div.message-component.message-row.cmp-row > div.message-component.message-row.row-contentpass > div > button",
        ]

        # Generic fallbacks that often work across variants
        generic_css: List[str] = [
            "#notice button[title*='Accept']",
            "button[aria-label='I Accept']",
            "button:has-text('Accept')",
            "button:has-text('I agree')",
            "button:has-text('Continue')",
        ]

        xpath_selectors: List[str] = [
            "//button[contains(text(),'Accept')]",
            "//button[contains(text(),'I Agree')]",
            "//button[contains(text(),'Continue')]",
        ]

        css_sequence: List[str] = eu_selectors + uk_cop_selectors + generic_css

        while asyncio.get_event_loop().time() < deadline:
            try:
                # 1) Try CSS on the main page
                for sel in css_sequence:
                    if await self._try_click_css(page, sel):
                        print(f"✅ CMP: clicked via CSS selector: {sel}")
                        return True

                # 2) Try XPath on the main page
                for xp in xpath_selectors:
                    if await self._try_click_xpath(page, xp):
                        print(f"✅ CMP: clicked via XPath selector: {xp}")
                        return True

                # 3) Try inside iframes
                for frame in page.frames:
                    for sel in css_sequence:
                        if await self._try_click_css(frame, sel):
                            print(f"✅ CMP: clicked (iframe) via CSS selector: {sel}")
                            return True
                    for xp in xpath_selectors:
                        if await self._try_click_xpath(frame, xp):
                            print(f"✅ CMP: clicked (iframe) via XPath selector: {xp}")
                            return True

            except Exception as e:
                # Don't let CMP handling break the run
                print(f"ℹ️ CMP: exception while searching/clicking: {e}")

            await asyncio.sleep(0.25)

        print("ℹ️ CMP: no consent dialog found within timeout")
        return False

    # ─────────────────────────────────────────────────────────────────
    # Small helpers
    # ─────────────────────────────────────────────────────────────────
    async def _try_click_css(self, target: Any, selector: str) -> bool:
        try:
            el = await target.query_selector(selector)
            if el:
                await el.click(timeout=1000)
                return True
        except Exception:
            pass
        return False

    async def _try_click_xpath(self, target: Any, xpath: str) -> bool:
        try:
            el = await target.query_selector(f"xpath={xpath}")
            if el:
                await el.click(timeout=1000)
                return True
        except Exception:
            pass
        return False