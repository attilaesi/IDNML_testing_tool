"""
prebid: PbjsPrebidTimeoutConfigTest

What this test checks
---------------------
Validates that a Prebid bid timeout is configured and falls within the acceptable
range (100–5000 ms). Reads pbjs.getConfig() and checks bidderTimeout, timeout,
or auctionTimeout in that priority order.

Test conditions
---------------
- window.pbjs and pbjs.getConfig must be present.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: a timeout is configured and its value is between 100–5000 ms.
- FAILED: no timeout configured (no bidderTimeout / timeout / auctionTimeout in config).
- FAILED: timeout is below 100 ms (unrealistically low).
- FAILED: timeout exceeds 5000 ms (unrealistically high).
"""
from pathlib import Path
from core.base_test import BaseTest, TestResult, TestState
from core.data_extractor import DataExtractor

_JS = (Path(__file__).parent.parent / "js" / "pbjs_timeout_config.js").read_text()

class PbjsPrebidTimeoutConfigTest(BaseTest):

    """
    Validates Prebid timeout configuration.

    Answers:
      - Is a timeout configured (timeout / bidderTimeout / auctionTimeout)?
      - Is the value in a reasonable range (defaults: 100–5000 ms)?

    Assumes:
      - Framework already navigated to the URL
      - CMP has been handled
      - Prebid/GPT readiness has been waited for
    """

    name = "PbjsPrebidTimeoutConfigTest"

    # You can tweak these if needed
    MIN_TIMEOUT_MS = 100
    MAX_TIMEOUT_MS = 5000

    async def setup(self, page, url: str) -> bool:
        """
        No navigation here – just ensure DOM is ready.
        """
        try:
            await page.wait_for_load_state("domcontentloaded")
            return True
        except Exception as e:
            print(f"[PbjsPrebidTimeoutConfigTest] setup error: {e}")
            return False

    async def execute(self, page, url: str) -> TestResult:
        """
        Extract timeout-related configuration from window.pbjs.
        """
        result = TestResult(self.name)
        result.url = url
        result.state = TestState.PASSED
        result.data = {}

        try:
            # Optional: basic page metrics for context
            basic_data = await DataExtractor.extract_basic_data(page, url)
            result.data.update(basic_data)

            timeout_data = await page.evaluate(_JS)

            result.data["prebid_timeout_config"] = timeout_data

        except Exception as e:
            result.state = TestState.ERROR
            result.errors.append(f"JS extraction failed: {e}")

        return result

    async def validate(self, result: TestResult) -> TestResult:
        """
        Validate the timeout configuration snapshot.
        """
        if result.state == TestState.ERROR:
            return result

        timeout_data = (result.data or {}).get("prebid_timeout_config", {}) or {}
        errors = []
        warnings = []

        # Propagate any JS-side errors first
        for err in timeout_data.get("errors", []):
            errors.append(f"Extraction error: {err}")

        timeout_raw = timeout_data.get("timeout")
        timeout_source = timeout_data.get("timeout_source", "none")
        config_complete = timeout_data.get("config_complete", False)

        # 1) Must have some timeout configured
        if timeout_raw is None:
            errors.append("No Prebid timeout configured (timeout / bidderTimeout / auctionTimeout missing)")
        else:
            # 2) Validate numeric range
            try:
                timeout_val = int(timeout_raw)
                if timeout_val < self.MIN_TIMEOUT_MS:
                    errors.append(
                        f"Timeout too low: {timeout_val}ms "
                        f"(minimum {self.MIN_TIMEOUT_MS}ms recommended)"
                    )
                elif timeout_val > self.MAX_TIMEOUT_MS:
                    errors.append(
                        f"Timeout too high: {timeout_val}ms "
                        f"(maximum {self.MAX_TIMEOUT_MS}ms recommended)"
                    )
            except (ValueError, TypeError):
                errors.append(f"Invalid timeout format: {timeout_raw}")

        # 3) Mark incomplete configuration if no relevant keys present
        if not config_complete:
            warnings.append("Timeout configuration appears incomplete (no timeout-like keys in pbjs config)")

        # Final state
        if errors:
            result.state = TestState.FAILED
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        if warnings:
            result.warnings.extend(warnings)

        # Attach metadata for reporting
        result.metadata.update(
            {
                "timeout_value": timeout_raw,
                "timeout_source": timeout_source,
                "config_complete": bool(config_complete),
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        """
        Optional: screenshot on failure, if debug_screenshots enabled.
        """
        if result.state == TestState.FAILED and self.config.get("debug_screenshots"):
            try:
                screenshot_path = f"debug/prebid_timeout_fail_{hash(result.url)}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                result.metadata["debug_screenshot"] = screenshot_path
            except Exception:
                pass