"""
ima:category2

What this test is meant to test
--------------------------------
Checks the IMA video ad request cust_params for "category2" (second-level
taxonomy).  Some content may only carry category1; in that case the absence
of category2 is acceptable.  If category2 is present it must be non-empty.

Test conditions
---------------
- Page must be identified as a video page (GPT pageType == "video").
- The IMA VAST ad request must have fired and been captured from
  securepubads.g.doubleclick.net before the test timeout (8 s).

What counts as PASS / FAIL / ERROR / N/A
------------------------------------------
- PASSED:
    - category2 present and non-empty, OR
    - category2 absent but category1 is present (single-level taxonomy).
- FAILED:
    - category2 key present in cust_params but value is empty / whitespace.
- SKIPPED:
    - Page is not a video page, or no IMA ad request was captured
      within the timeout.
"""

from core.ima_base_test import ImaBaseTest
from core.base_test import TestResult, TestState


class ImaCategory2Test(ImaBaseTest):

    """Validate category2 targeting key in IMA video ad request cust_params."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        cust_params = await self._fetch_cust_params(page)
        result.data = {
            "cust_params": cust_params,
            "category1": self._targeting(cust_params, "category1"),
            "category2": self._targeting(cust_params, "category2"),
        }
        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.data.get("cust_params") is None:
            result.state = TestState.ERROR
            result.errors.append(self._ima_chain_error)
            return result

        cat2 = result.data.get("category2", [])

        if not cat2:
            result.state = TestState.FAILED
            result.errors.append("category2 missing from IMA cust_params.")
        elif not any(v for v in cat2):
            result.state = TestState.FAILED
            result.errors.append("category2 present but empty in IMA cust_params.")
        else:
            result.state = TestState.PASSED
        return result
