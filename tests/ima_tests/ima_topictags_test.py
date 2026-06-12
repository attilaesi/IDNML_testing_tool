"""
ima:topictags

What this test is meant to test
--------------------------------
Checks the IMA video ad request cust_params for "topictags", which carries
a list of editorial topic tags.  If present, GAM uses these for contextual
targeting.  The test is lenient: absence is acceptable; if set, at least
one non-empty tag must be present.

Test conditions
---------------
- Page must be identified as a video page (GPT pageType == "video").
- The IMA VAST ad request must have fired and been captured from
  securepubads.g.doubleclick.net before the test timeout (8 s).

What counts as PASS / FAIL / SKIPPED
--------------------------------------
- PASSED:
    - "topictags" key absent from cust_params, OR
    - "topictags" present with at least one non-empty tag.
- FAILED:
    - "topictags" present but all tags are empty / whitespace.
- SKIPPED:
    - Page is not a video page, or no IMA ad request was captured
      within the timeout.
"""

from core.ima_base_test import ImaBaseTest
from core.base_test import TestResult, TestState


class ImaTopictagsTest(ImaBaseTest):

    """Validate topictags key in IMA video ad request cust_params."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        cust_params = await self._fetch_cust_params(page)
        result.data = {"cust_params": cust_params, "topictags": self._targeting(cust_params, "topictags")}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.data.get("cust_params") is None:
            result.state = TestState.SKIPPED
            result.warnings.append("No IMA ad request captured — video player may not have fired.")
            return result

        vals = result.data.get("topictags", [])
        if not vals:
            result.state = TestState.FAILED
            result.errors.append("topictags missing from IMA cust_params.")
        elif not any(v for v in vals):
            result.state = TestState.FAILED
            result.errors.append("topictags present but empty in IMA cust_params.")
        else:
            result.state = TestState.PASSED
        return result
