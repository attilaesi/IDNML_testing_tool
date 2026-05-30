"""
prebid: PbjsIdentityModulesTest

What this test checks
---------------------
Validates that the expected Prebid identity modules are configured for the current geo,
by reading pbjs.getConfig().userSync.userIds[].name and comparing to the expected set
defined in the geo config for the detected locale.

Test conditions
---------------
- window.pbjs must be present.
- Geo is determined from the Locale cookie injected by the framework.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: all expected identity modules for the geo are present in pbjs userSync config.
- FAILED: one or more expected identity modules are missing for the current geo.
"""
from pathlib import Path
from core.base_test import BaseTest, TestResult, TestState
from config.test_settings import get_geo_config
from utils.geo_utils import detect_geo_from_cookies

_JS = (Path(__file__).parent.parent / "js" / "pbjs_identity_modules.js").read_text()

class PbjsIdentityModulesTest(BaseTest):

    """
    Validate that the expected identity modules are configured for the current geo.

    Looks at pbjs.getConfig().userSync.userIds[].name

    Flow:
      - setup: no-op
      - execute: detect geo, read identity modules, compare to geo config
      - validate: identity
      - cleanup: no-op
    """

    name = "PbjsIdentityModulesTest"

    async def setup(self, page, url: str) -> bool:
        # Nothing special to do before inspection.
        return True

    async def execute(self, page, url: str) -> TestResult:
        # Same fix: don't pass url= into TestResult ctor.
        result = TestResult(self.name)
        result.url = url

        # 1) Detect geo from Locale cookie (injected by framework_manager)
        # self.locale is set per URL, based on the 'Locale' cookie.
        locale = getattr(self, "locale", "UK")
        geo = locale  # keep using the same variable name if the rest of the test expects 'geo'
        result.metadata["locale"] = locale
        result.metadata["geo"] = geo  # backwards-compatible metadata key

        geo_cfg = get_geo_config(geo)
        expected_ids = set(geo_cfg.get("identity_modules", []))

        # 2) Extract identity modules from pbjs config
        data = await page.evaluate(_JS)

        actual_ids = set(data.get("userIds") or [])
        missing = sorted(expected_ids - actual_ids)

        result.data = {
            "actual_identity_modules": sorted(actual_ids),
            "expected_identity_modules": sorted(expected_ids),
            "missing_identity_modules": missing,
            "raw_userSync": data.get("userSync"),
        }

        if missing:
            result.state = TestState.FAILED
            result.errors.append(
                f"Missing identity modules for {geo}: {', '.join(missing)}"
            )
        else:
            result.state = TestState.PASSED

        return result

    async def validate(self, result: TestResult) -> TestResult:
        # All logic is already baked into execute.
        return result

