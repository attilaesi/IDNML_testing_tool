"""
ima:VideoID

What this test is meant to test
--------------------------------
Checks that the IMA video ad request cust_params contains a non-empty
"VideoID" value that identifies the specific video asset being played.
This key is required so GAM can apply video-content-specific targeting
and frequency capping rules.

Test conditions
---------------
- Page must be identified as a video page (GPT pageType == "video").
- The IMA VAST ad request must have fired and been captured from
  securepubads.g.doubleclick.net before the test timeout (8 s).

What counts as PASS / FAIL / ERROR / N/A
------------------------------------------
- PASSED:
    - "VideoID" present in cust_params with a non-empty value.
- FAILED:
    - "VideoID" key missing from cust_params, or present but empty.
- SKIPPED:
    - Page is not a video page, or no IMA ad request was captured
      within the timeout.
"""

from core.ima_base_test import ImaBaseTest
from core.base_test import TestResult, TestState


class ImaVideoIdTest(ImaBaseTest):

    """Validate VideoID key in IMA video ad request cust_params."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        cust_params = await self._fetch_cust_params(page)
        result.data = {"cust_params": cust_params, "videoID": self._targeting(cust_params, "videoID")}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.data.get("cust_params") is None:
            result.state = TestState.ERROR
            result.errors.append(self._ima_chain_error)
            return result

        vals = result.data.get("videoID", [])
        if not vals:
            result.state = TestState.FAILED
            result.errors.append("videoID missing from IMA cust_params.")
            return result
        if not any(v for v in vals):
            result.state = TestState.FAILED
            result.errors.append("videoID present but empty in IMA cust_params.")
            return result

        import re
        invalid = [v for v in vals if not re.match(r'^[a-zA-Z0-9]{4,}$', str(v).strip())]
        if invalid:
            result.state = TestState.FAILED
            result.errors.append(f"videoID format invalid (expected alphanumeric, e.g. yYEQtO0C): {', '.join(invalid)}")
        else:
            result.state = TestState.PASSED
        return result
