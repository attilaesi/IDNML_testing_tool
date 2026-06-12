"""
ima:liveblog

What this test is meant to test
--------------------------------
Checks the IMA video ad request cust_params for the "liveblog" flag, which
indicates whether the embedding page is a live blog.  If the key is sent,
its value must be the expected boolean indicator.

Test conditions
---------------
- Page must be identified as a video page (GPT pageType == "video").
- The IMA VAST ad request must have fired and been captured from
  securepubads.g.doubleclick.net before the test timeout (8 s).

What counts as PASS / FAIL / SKIPPED
--------------------------------------
- PASSED:
    - "liveblog" key absent from cust_params, OR
    - "liveblog" present with value "y" or "n".
- FAILED:
    - "liveblog" present with any value other than "y" or "n".
- SKIPPED:
    - Page is not a video page, or no IMA ad request was captured
      within the timeout.
"""

from core.ima_base_test import ImaBaseTest
from core.base_test import TestResult, TestState


class ImaLiveblogTest(ImaBaseTest):

    """Validate liveblog flag in IMA video ad request cust_params."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        cust_params = await self._fetch_cust_params(page)
        result.data = {"cust_params": cust_params, "liveblog": self._targeting(cust_params, "liveblog")}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.data.get("cust_params") is None:
            result.state = TestState.SKIPPED
            result.warnings.append("No IMA ad request captured — video player may not have fired.")
            return result

        vals = result.data.get("liveblog", [])
        if not vals:
            result.state = TestState.FAILED
            result.errors.append("liveblog missing from IMA cust_params.")
        elif not any(v for v in vals):
            result.state = TestState.FAILED
            result.errors.append("liveblog present but empty in IMA cust_params.")
        else:
            bad = [v for v in vals if v.lower() not in {"y", "n"}]
            if bad:
                result.state = TestState.FAILED
                result.errors.append("liveblog invalid in IMA cust_params (expected 'y'/'n'): " + ", ".join(bad))
            else:
                result.state = TestState.PASSED
        return result
