"""
ima:category1

What this test is meant to test
--------------------------------
Checks that the IMA video ad request cust_params contains a non-empty
"category1" value (top-level section / vertical).  This key is required
on all video pages so GAM can apply category-based targeting rules.

Test conditions
---------------
- Page must be identified as a video page (GPT pageType == "video").
- The IMA VAST ad request must have fired and been captured from
  securepubads.g.doubleclick.net before the test timeout (8 s).

What counts as PASS / FAIL / ERROR / N/A
------------------------------------------
- PASSED:
    - category1 present in cust_params with at least one non-empty value.
- FAILED:
    - category1 key missing from cust_params, or present but empty.
- SKIPPED:
    - Page is not a video page, or no IMA ad request was captured
      within the timeout.
"""

from core.ima_base_test import ImaBaseTest
from core.base_test import TestResult, TestState


class ImaCategory1Test(ImaBaseTest):

    """Validate category1 targeting key in IMA video ad request cust_params."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        cust_params = await self._fetch_cust_params(page)
        result.data = {"cust_params": cust_params, "category1": self._targeting(cust_params, "category1")}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.data.get("cust_params") is None:
            result.state = TestState.ERROR
            result.errors.append(self._ima_chain_error)
            return result

        vals = result.data.get("category1", [])
        if not vals:
            result.state = TestState.FAILED
            result.errors.append("category1 missing from IMA cust_params.")
        elif not any(v for v in vals):
            result.state = TestState.FAILED
            result.errors.append("category1 present but empty in IMA cust_params.")
        else:
            result.state = TestState.PASSED
        return result
