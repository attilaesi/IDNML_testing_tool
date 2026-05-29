"""
environment: EnvIsMobileOrTabletTest

What this test checks
---------------------
Verifies that the site sets the `is_mobile_or_tablet` cookie to the correct value
for the viewport in use. Runs on every URL regardless of site plan.

Test conditions
---------------
- No conditions; test always runs.
- Expected value depends on viewport orientation:
    - Portrait (width < height)  → expected "true"
    - Landscape (width >= height) → expected "false"

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: cookie is present and its value matches the expected value for the viewport.
- FAILED: cookie `is_mobile_or_tablet` is absent.
- FAILED: cookie value does not match expected ("true" or "false" for the viewport).
"""

from core.base_test import BaseTest, TestResult, TestState
from core.device_helpers import is_mobile_viewport


class EnvIsMobileOrTabletTest(BaseTest):

    name = "EnvIsMobileOrTabletTest"

    async def setup(self, page, url: str) -> bool:
        try:
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        js = """
        () => {
          try {
            const cookies = document.cookie ? document.cookie.split(/;\\s*/) : [];
            for (const c of cookies) {
              const idx = c.indexOf("=");
              if (idx === -1) continue;
              const name = c.slice(0, idx).trim();
              if (name === "is_mobile_or_tablet") {
                return c.slice(idx + 1).trim() || null;
              }
            }
            return null;
          } catch (e) {
            return null;
          }
        }
        """

        cookie_value = await page.evaluate(js)
        result.data = {"cookie_value": cookie_value}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        cookie_value = (result.data or {}).get("cookie_value")
        expected = "true" if is_mobile_viewport(self.config) else "false"

        result.metadata = {
            "cookie_value": cookie_value,
            "expected_value": expected,
        }

        if cookie_value is None:
            result.state = TestState.FAILED
            result.errors.append(
                f"Cookie 'is_mobile_or_tablet' is not set. "
                f"Expected '{expected}' for current viewport "
                f"({self.config.get('viewport', {})})."
            )
            return result

        if str(cookie_value).lower() != expected:
            result.state = TestState.FAILED
            result.errors.append(
                f"Cookie 'is_mobile_or_tablet' = '{cookie_value}', expected '{expected}' "
                f"for viewport {self.config.get('viewport', {})}."
            )
            return result

        result.state = TestState.PASSED
        return result
