# tests/prebid_tests/price_floors_test.py

from core.base_test import BaseTest, TestResult, TestState
from core.data_extractor import DataExtractor


class PriceFloorsTest(BaseTest):
    """
    Validates Prebid price floors configuration.

    Answers:
      - Is the priceFloors module installed?
      - Is floors config enabled?
      - Are any floor rules configured?

    Assumes:
      - Framework already navigated to the URL
      - CMP has been handled
      - Prebid/GPT readiness has been waited for
    """

    name = "PriceFloorsTest"

    async def setup(self, page, url: str) -> bool:
        """
        No navigation here – just ensure DOM is ready.
        """
        try:
            await page.wait_for_load_state("domcontentloaded")
            return True
        except Exception as e:
            print(f"[PriceFloorsTest] setup error: {e}")
            return False

    async def execute(self, page, url: str) -> TestResult:
        """
        Extract price floors related information from window.pbjs.
        """
        result = TestResult(self.name)
        result.url = url
        result.state = TestState.PASSED
        result.data = {}

        try:
            # Optional: basic page metrics for context
            basic_data = await DataExtractor.extract_basic_data(page, url)
            result.data.update(basic_data)

            floors_data = await page.evaluate(
                """
                () => {
                    const out = {
                        module_present: false,
                        enabled: false,
                        provider: null,
                        rules_count: 0,
                        raw_config: {},
                        installed_modules: null,
                        has_pbjs: false,
                        has_getConfig: false,
                        errors: []
                    };

                    try {
                        const pbjs = window.pbjs;
                        if (!pbjs) {
                            out.errors.push("window.pbjs is not defined");
                            return out;
                        }

                        out.has_pbjs = true;

                        // 1) installedModules – presence of priceFloors module
                        if (Array.isArray(pbjs.installedModules)) {
                            out.installed_modules = pbjs.installedModules.slice();
                            out.module_present = pbjs.installedModules.includes("priceFloors");
                        }

                        // 2) Need getConfig to inspect floors config
                        if (typeof pbjs.getConfig !== "function") {
                            out.errors.push("pbjs.getConfig is not available");
                            return out;
                        }

                        out.has_getConfig = true;

                        let floorsCfg = pbjs.getConfig("floors");

                        // Some versions nest it under the full config
                        if (!floorsCfg || (typeof floorsCfg === "object" && Object.keys(floorsCfg).length === 0)) {
                            const fullCfg = pbjs.getConfig() || {};
                            if (fullCfg.floors) {
                                floorsCfg = fullCfg.floors;
                            }
                        }

                        if (!floorsCfg) {
                            // No floors config at all – but module_present might still be true
                            out.raw_config = {};
                            return out;
                        }

                        out.raw_config = floorsCfg;

                        // Enabled flag:
                        //  - if floorsCfg.enabled is explicitly set, honour it
                        //  - if it's missing but we have config, default to TRUE
                        if (Object.prototype.hasOwnProperty.call(floorsCfg, "enabled")) {
                            out.enabled = !!floorsCfg.enabled;
                        } else {
                            out.enabled = true;
                        }

                        // Provider (optional)
                        if (floorsCfg.data && floorsCfg.data.provider) {
                            out.provider = floorsCfg.data.provider;
                        } else if (floorsCfg.provider) {
                            out.provider = floorsCfg.provider;
                        }

                        // Rule count from data.values / values
                        let rulesCount = 0;
                        const valuesObj =
                            (floorsCfg.data && floorsCfg.data.values) ||
                            floorsCfg.values ||
                            null;

                        if (valuesObj && typeof valuesObj === "object") {
                            rulesCount = Object.keys(valuesObj).length;
                        }

                        out.rules_count = rulesCount;

                        // 3) Fallback: if we somehow didn't see the module in installedModules
                        // but there *is* a floors config, treat module_present as true.
                        if (!out.module_present && floorsCfg) {
                            out.module_present = true;
                        }

                    } catch (e) {
                        out.errors.push(String(e));
                    }

                    return out;
                }
                """
            )

            result.data["prebid_floors"] = floors_data

        except Exception as e:
            result.state = TestState.ERROR
            result.errors.append(f"JS extraction failed: {e}")

        return result

    async def validate(self, result: TestResult) -> TestResult:
        """
        Validate the price floors configuration snapshot.
        """
        if result.state == TestState.ERROR:
            return result

        floors = (result.data or {}).get("prebid_floors", {}) or {}
        errors = []
        warnings = []

        # Propagate JS-side errors
        for err in floors.get("errors", []):
            errors.append(f"Extraction error: {err}")

        module_present = floors.get("module_present", False)
        enabled = floors.get("enabled", False)
        rules_count = floors.get("rules_count", 0)
        provider = floors.get("provider")
        raw_cfg = floors.get("raw_config") or {}
        has_config = bool(raw_cfg)

        # 1) Module presence
        if not module_present and not has_config:
            errors.append("Price floors module (priceFloors) not installed and no floors config present")

        if not module_present and has_config:
            # Config exists but module isn't listed – warn, don’t hard-fail.
            warnings.append("Price floors config present but priceFloors module not listed in pbjs.installedModules")

        # 2) Enabled flag
        # After the execute() change, 'enabled' will be True whenever there is
        # a floors config and no explicit enabled:false.
        if has_config and not enabled:
            errors.append("Price floors config present but disabled in Prebid (floors.enabled === false)")

        # 3) Rules
        if has_config and enabled and rules_count == 0:
            errors.append("No floor rules configured (floors.data.values / floors.values is empty or missing)")

        # 4) Provider is optional – warn if missing
        if has_config and enabled and not provider:
            warnings.append("Price floors provider not specified in config")

        # Final state
        if errors:
            result.state = TestState.FAILED
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        if warnings:
            result.warnings.extend(warnings)

        # Attach metadata for reporting
        result.metadata.update(
            {
                "floors_module_present": module_present,
                "floors_enabled": enabled,
                "floors_rules_count": rules_count,
                "floors_provider": provider,
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        """
        Optional: screenshot on failure, if debug_screenshots enabled.
        """
        if result.state == TestState.FAILED and self.config.get("debug_screenshots"):
            try:
                screenshot_path = f"debug/price_floors_fail_{hash(result.url)}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                result.metadata["debug_screenshot"] = screenshot_path
            except Exception:
                pass