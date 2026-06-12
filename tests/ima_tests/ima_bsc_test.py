"""
ima:BSC

Checks that the IMA video ad request cust_params contains a non-empty
BSC (Brand Safety Category) value with at least one numeric segment ID
(e.g. 87012038,74062139).
"""

from core.ima_base_test import ImaBaseTest
from core.base_test import TestResult, TestState


class ImaBscTest(ImaBaseTest):

    """Validate BSC targeting key in IMA video ad request cust_params."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        cust_params = await self._fetch_cust_params(page)
        result.data = {"cust_params": cust_params, "BSC": self._targeting(cust_params, "BSC")}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.data.get("cust_params") is None:
            result.state = TestState.SKIPPED
            result.warnings.append("No IMA ad request captured — video player may not have fired.")
            return result

        vals = result.data.get("BSC", [])
        if not vals:
            result.state = TestState.FAILED
            result.errors.append("BSC missing from IMA cust_params.")
        elif not any(v for v in vals):
            result.state = TestState.FAILED
            result.errors.append("BSC present but empty in IMA cust_params.")
        else:
            result.state = TestState.PASSED
        return result
