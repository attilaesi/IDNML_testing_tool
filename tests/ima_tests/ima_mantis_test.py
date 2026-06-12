"""
ima:mantis

What this test is meant to test
--------------------------------
Checks the IMA video ad request cust_params for the "mantis" brand-safety
key, which carries vertical / safety labels used by GAM for brand-safe
targeting.  The test is lenient: if the key is absent that is acceptable;
if it is present the value must be non-empty.

Test conditions
---------------
- Page must be identified as a video page (GPT pageType == "video").
- The IMA VAST ad request must have fired and been captured from
  securepubads.g.doubleclick.net before the test timeout (8 s).

What counts as PASS / FAIL / SKIPPED
--------------------------------------
- PASSED:
    - "mantis" key absent from cust_params, OR
    - "mantis" present with at least one non-empty value.
- FAILED:
    - "mantis" present but all values are empty / whitespace.
- SKIPPED:
    - Page is not a video page, or no IMA ad request was captured
      within the timeout.
"""

from core.ima_base_test import ImaBaseTest
from core.base_test import TestResult, TestState


class ImaMantisTest(ImaBaseTest):

    """Validate mantis brand-safety key in IMA video ad request cust_params."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        cust_params = await self._fetch_cust_params(page)
        result.data = {"cust_params": cust_params, "mantis": self._targeting(cust_params, "mantis")}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.data.get("cust_params") is None:
            result.state = TestState.SKIPPED
            result.warnings.append("No IMA ad request captured — video player may not have fired.")
            return result

        vals = result.data.get("mantis", [])
        if not vals:
            result.state = TestState.FAILED
            result.errors.append("mantis missing from IMA cust_params.")
        elif not any(v for v in vals):
            result.state = TestState.FAILED
            result.errors.append("mantis present but empty in IMA cust_params.")
        else:
            result.state = TestState.PASSED
        return result
