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
                        errors: []
                    };

                    try {
                        const pbjs = window.pbjs;
                        if (!pbjs) {
                            out.errors.push("window.pbjs is not defined");
                            return out;
                        }

                        // Check module presence
                        if (Array.isArray(pbjs.installedModules)) {
                            out.module_present = pbjs.installedModules.includes("priceFloors");
                        }

                        if (typeof pbjs.getConfig !== "function") {
                            out.errors.push("pbjs.getConfig is not available");
                            return out;
                        }

                        // Get floors config via getConfig
                        let floorsCfg = pbjs.getConfig("floors");
                        if (!floorsCfg || (typeof floorsCfg === "object" && Object.keys(floorsCfg).length === 0)) {
                            // Some versions return nested under main config
                            const fullCfg = pbjs.getConfig() || {};
                            if (fullCfg.floors) {
                                floorsCfg = fullCfg.floors;
                            }
                        }

                        if (!floorsCfg) {
                            out.raw_config = {};
                            return out;
                        }

                        out.raw_config = floorsCfg;
                        out.enabled = !!floorsCfg.enabled;
                        out.provider = floorsCfg.data && floorsCfg.data.provider
                            ? floorsCfg.data.provider
                            : (floorsCfg.provider || null);

                        // Try to derive rule count from various shapes
                        let rulesCount = 0;

                        // Most common shape: floors.data.values
                        const valuesObj =
                            (floorsCfg.data && floorsCfg.data.values)
                            || floorsCfg.values
                            || null;

                        if (valuesObj && typeof valuesObj === "object") {
                            rulesCount = Object.keys(valuesObj).length;
                        }

                        // Some configs may have schema-based rules or additional schemas;
                        // we keep it simple and only count values keys for now.
                        out.rules_count = rulesCount;

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

        # 1) Module presence
        if not module_present:
            errors.append("Price floors module (priceFloors) not installed")

        # 2) Enabled flag
        if module_present and not enabled:
            errors.append("Price floors not enabled in Prebid config")

        # 3) Rules
        if module_present and enabled and rules_count == 0:
            errors.append("No floor rules configured (floors.values is empty or missing)")

        # 4) Provider is optional, but nice to have – warn if missing
        if module_present and enabled and not provider:
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