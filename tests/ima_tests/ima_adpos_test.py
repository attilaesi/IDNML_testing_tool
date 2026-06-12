"""
ima:adpos

What this test is meant to test
--------------------------------
Checks that the IMA video ad request cust_params contains a non-empty
"adpos" value indicating the ad position within the video stream
(e.g. preroll, midroll, postroll).  GAM requires this key to apply
position-based pricing and frequency rules.

Test conditions
---------------
- Page must be identified as a video page (GPT pageType == "video").
- The IMA VAST ad request must have fired and been captured from
  securepubads.g.doubleclick.net before the test timeout (8 s).

What counts as PASS / FAIL / SKIPPED
--------------------------------------
- PASSED:
    - "adpos" present in cust_params with a non-empty value.
- FAILED:
    - "adpos" key missing from cust_params, or present but empty.
- SKIPPED:
    - Page is not a video page, or no IMA ad request was captured
      within the timeout.
"""

from core.ima_base_test import ImaBaseTest
from core.base_test import TestResult, TestState


class ImaAdposTest(ImaBaseTest):

    """Validate adpos key in IMA video ad request cust_params."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        cust_params = await self._fetch_cust_params(page)
        result.data = {"cust_params": cust_params, "adpos": self._targeting(cust_params, "adpos")}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.data.get("cust_params") is None:
            result.state = TestState.SKIPPED
            result.warnings.append("No IMA ad request captured — video player may not have fired.")
            return result

        vals = result.data.get("adpos", [])
        if not vals:
            result.state = TestState.FAILED
            result.errors.append("adpos missing from IMA cust_params.")
        elif not any(v for v in vals):
            result.state = TestState.FAILED
            result.errors.append("adpos present but empty in IMA cust_params.")
        else:
            result.state = TestState.PASSED
        return result
