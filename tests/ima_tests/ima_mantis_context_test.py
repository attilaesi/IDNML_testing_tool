"""
ima:mantis_context

What this test is meant to test
--------------------------------
Checks the IMA video ad request cust_params for "mantis_context", which
carries the Mantis contextual classification string.  Unlike the lenient
mantis check, this key is expected to be present and populated on all
video ad requests.

Test conditions
---------------
- Page must be identified as a video page (GPT pageType == "video").
- The IMA VAST ad request must have fired and been captured from
  securepubads.g.doubleclick.net before the test timeout (8 s).

What counts as PASS / FAIL / ERROR / N/A
------------------------------------------
- PASSED:
    - "mantis_context" present in cust_params with a non-empty value.
- FAILED:
    - "mantis_context" key missing from cust_params, or present but empty.
- SKIPPED:
    - Page is not a video page, or no IMA ad request was captured
      within the timeout.
"""

from core.ima_base_test import ImaBaseTest
from core.base_test import TestResult, TestState


class ImaMantisContextTest(ImaBaseTest):

    """Validate mantis_context key in IMA video ad request cust_params."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        cust_params = await self._fetch_cust_params(page)
        result.data = {"cust_params": cust_params, "mantis_context": self._targeting(cust_params, "mantis_context")}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.data.get("cust_params") is None:
            result.state = TestState.ERROR
            result.errors.append(self._ima_chain_error)
            return result

        vals = result.data.get("mantis_context", [])
        if not vals:
            result.state = TestState.FAILED
            result.errors.append("mantis_context missing from IMA cust_params.")
        elif not any(v for v in vals):
            result.state = TestState.FAILED
            result.errors.append("mantis_context present but empty in IMA cust_params.")
        else:
            result.state = TestState.PASSED
        return result
