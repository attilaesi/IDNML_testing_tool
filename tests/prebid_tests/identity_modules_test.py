from core.base_test import BaseTest, TestResult, TestState
from tests.prebid_tests.test_settings import get_geo_config
from utils.geo_utils import detect_geo_from_cookies


class IdentityModulesTest(BaseTest):
    """
    Validate that the expected identity modules are configured for the current geo.

    Looks at pbjs.getConfig().userSync.userIds[].name

    Flow:
      - setup: no-op
      - execute: detect geo, read identity modules, compare to geo config
      - validate: identity
      - cleanup: no-op
    """

    name = "IdentityModulesTest"

    async def setup(self, page, url: str) -> bool:
        # Nothing special to do before inspection.
        return True

    async def execute(self, page, url: str) -> TestResult:
        # Same fix: don't pass url= into TestResult ctor.
        result = TestResult(self.name)
        result.url = url

        # 1) Detect geo (from cookies) and load expected modules
        fallback_geo = self.config.get("geo_mode", "UK")
        geo = await detect_geo_from_cookies(page, fallback=fallback_geo)
        result.metadata["geo"] = geo

        geo_cfg = get_geo_config(geo)
        expected_ids = set(geo_cfg.get("identity_modules", []))

        # 2) Extract identity modules from pbjs config
        data = await page.evaluate(
            """
            () => {
              const out = {
                userIds: [],
                userSync: null
              };

              if (!window.pbjs || !window.pbjs.getConfig) {
                return out;
              }

              const cfg = window.pbjs.getConfig() || {};
              const us = cfg.userSync || {};
              const ids = Array.isArray(us.userIds) ? us.userIds : [];

              out.userIds = ids.map(u => u && u.name).filter(Boolean);
              out.userSync = us;
              return out;
            }
            """
        )

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

    async def cleanup(self, page, url: str) -> None:
        # No extra cleanup required.
        return