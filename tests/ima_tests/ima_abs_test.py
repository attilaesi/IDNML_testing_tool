"""
ima:ABS

What this test is meant to test
--------------------------------
Checks that the IMA video ad request cust_params contains a non-empty
ABS (Audience Behavioural Segment) value.  GAM uses ABS to apply
audience-based pricing and targeting rules on video inventory.

Test conditions
---------------
- Page must be a video page with an active JW Player hero player.
- The IMA VAST ad request must have fired and been captured from
  securepubads.g.doubleclick.net before the test timeout.

What counts as PASS / FAIL / SKIPPED
--------------------------------------
- PASSED:
    - "ABS" key present in IMA cust_params with a non-empty value.
- FAILED:
    - "ABS" key missing from cust_params.
    - "ABS" key present but empty.
- SKIPPED:
    - No IMA ad request captured — video player did not fire on this page.
"""

from core.ima_base_test import ImaBaseTest
from core.base_test import TestResult, TestState


class ImaAbsTest(ImaBaseTest):

    """Validate ABS targeting key in IMA video ad request cust_params."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        cust_params = await self._fetch_cust_params(page)
        result.data = {"cust_params": cust_params, "ABS": self._targeting(cust_params, "ABS")}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.data.get("cust_params") is None:
            result.state = TestState.SKIPPED
            result.warnings.append("No IMA ad request captured — video player may not have fired.")
            return result

        vals = result.data.get("ABS", [])
        if not vals:
            result.state = TestState.FAILED
            result.errors.append("ABS missing from IMA cust_params.")
        elif not any(v for v in vals):
            result.state = TestState.FAILED
            result.errors.append("ABS present but empty in IMA cust_params.")
        else:
            result.state = TestState.PASSED
        return result
