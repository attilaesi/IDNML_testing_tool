"""
ima:pageType

What this test is meant to test
--------------------------------
Checks that the IMA video ad request cust_params contains a non-empty
"pageType" value.  The video player must pass this key so GAM can apply
page-type-specific targeting rules.  On video pages the value is expected
to be "video".

Test conditions
---------------
- Page must be identified as a video page (GPT pageType == "video").
- The IMA VAST ad request must have fired and been captured from
  securepubads.g.doubleclick.net before the test timeout (8 s).

What counts as PASS / FAIL / SKIPPED
--------------------------------------
- PASSED:
    - pageType present in cust_params with a non-empty value.
- FAILED:
    - pageType key missing from cust_params, or present but empty.
- SKIPPED:
    - Page is not a video page, or no IMA ad request was captured
      within the timeout (video player may not have fired).
"""

from core.ima_base_test import ImaBaseTest
from core.base_test import TestResult, TestState


class ImaPageTypeTest(ImaBaseTest):

    """Validate pageType key in IMA video ad request cust_params."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        cust_params = await self._fetch_cust_params(page)
        result.data = {"cust_params": cust_params, "pageType": self._targeting(cust_params, "pageType")}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.data.get("cust_params") is None:
            result.state = TestState.SKIPPED
            result.warnings.append("No IMA ad request captured — video player may not have fired.")
            return result

        vals = result.data.get("pageType", [])
        if not vals:
            result.state = TestState.FAILED
            result.errors.append("pageType missing from IMA cust_params.")
        elif not any(v for v in vals):
            result.state = TestState.FAILED
            result.errors.append("pageType present but empty in IMA cust_params.")
        else:
            result.state = TestState.PASSED
        return result
