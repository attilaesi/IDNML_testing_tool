"""
ima:permutive

What this test is meant to test
--------------------------------
Checks the IMA video ad request cust_params for "permutive" audience
segment data.  Some stacks pass Permutive segment IDs here for audience
targeting.  The test is lenient: absence is acceptable; presence requires
at least one non-empty value.

Test conditions
---------------
- Page must be identified as a video page (GPT pageType == "video").
- The IMA VAST ad request must have fired and been captured from
  securepubads.g.doubleclick.net before the test timeout (8 s).

What counts as PASS / FAIL / ERROR / N/A
------------------------------------------
- PASSED:
    - "permutive" key absent from cust_params, OR
    - "permutive" present with at least one non-empty value.
- FAILED:
    - "permutive" present but all values are empty / whitespace.
- SKIPPED:
    - Page is not a video page, or no IMA ad request was captured
      within the timeout.
"""

from core.ima_base_test import ImaBaseTest
from core.base_test import TestResult, TestState


class ImaPermutiveTest(ImaBaseTest):

    """Validate permutive targeting key in IMA video ad request cust_params."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        cust_params = await self._fetch_cust_params(page)
        result.data = {"cust_params": cust_params, "permutive": self._targeting(cust_params, "permutive")}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.data.get("cust_params") is None:
            result.state = TestState.ERROR
            result.errors.append(self._ima_chain_error)
            return result

        vals = result.data.get("permutive", [])
        if not vals:
            result.state = TestState.FAILED
            result.errors.append("permutive missing from IMA cust_params.")
        elif not any(v for v in vals):
            result.state = TestState.FAILED
            result.errors.append("permutive present but empty in IMA cust_params.")
        else:
            result.state = TestState.PASSED
        return result
