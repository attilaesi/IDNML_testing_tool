from core.base_test import BaseTest, TestResult, TestState
from core.data_extractor import DataExtractor


class AdUnitConfigurationTest(BaseTest):
    """
    Validates Prebid ad unit configuration.

    Answers:
      - Are there any ad units at all?
      - Does each ad unit have a code/adUnitCode?
      - Does each ad unit have at least one bidder?
      - Does each ad unit have sensible sizes?

    Assumes:
      - Framework already navigated to the URL
      - CMP has been handled
      - Prebid/GPT readiness has been waited for
    """

    name = "AdUnitConfigurationTest"

    async def setup(self, page, url: str) -> bool:
        """
        No navigation here – just ensure DOM is ready.
        """
        try:
            await page.wait_for_load_state("domcontentloaded")
            return True
        except Exception as e:
            print(f"[AdUnitConfigurationTest] setup error: {e}")
            return False

    async def execute(self, page, url: str) -> TestResult:
        """
        Extract ad unit and bidder info from window.pbjs.
        """
        result = TestResult(self.name)
        result.url = url
        result.state = TestState.PASSED
        result.data = {}

        try:
            # Optional: basic page metrics for context
            basic_data = await DataExtractor.extract_basic_data(page, url)
            result.data.update(basic_data)

            ad_unit_data = await page.evaluate(
                """
                () => {
                    const out = {
                        ad_units: [],
                        errors: []
                    };

                    try {
                        const pbjs = window.pbjs;
                        if (!pbjs || !Array.isArray(pbjs.adUnits)) {
                            out.errors.push("pbjs.adUnits is not an array");
                            return out;
                        }

                        out.ad_units = pbjs.adUnits.map((unit) => {
                            const bids = Array.isArray(unit.bids) ? unit.bids : [];
                            const bidderCodes = bids
                                .map(b => b && b.bidder)
                                .filter(Boolean);

                            const sizes =
                                unit.sizes
                                || (unit.mediaTypes && unit.mediaTypes.banner && unit.mediaTypes.banner.sizes)
                                || [];

                            return {
                                code: unit.code || unit.adUnitCode || null,
                                bidders: bidderCodes,
                                sizes: sizes,
                                mediaTypes: unit.mediaTypes || {},
                            };
                        });
                    } catch (e) {
                        out.errors.push(String(e));
                    }

                    return out;
                }
                """
            )

            result.data["prebid_ad_units"] = ad_unit_data

        except Exception as e:
            result.state = TestState.ERROR
            result.errors.append(f"JS extraction failed: {e}")

        return result

    async def validate(self, result: TestResult) -> TestResult:
        """
        Validate the ad unit configuration snapshot.
        """
        if result.state == TestState.ERROR:
            return result

        ad_unit_data = (result.data or {}).get("prebid_ad_units", {}) or {}
        ad_units = ad_unit_data.get("ad_units") or []
        js_errors = ad_unit_data.get("errors") or []

        errors = []
        warnings = []

        # Propagate JS-side issues
        for err in js_errors:
            errors.append(f"Extraction error: {err}")

        # 1) Must have at least one ad unit
        if not ad_units:
            errors.append("No Prebid ad units configured (pbjs.adUnits is empty)")

        # 2) Per-unit checks
        units_missing_code = []
        units_missing_bidders = []
        units_missing_sizes = []

        for idx, unit in enumerate(ad_units):
            code = unit.get("code")
            bidders = unit.get("bidders") or []
            sizes = unit.get("sizes") or []

            if not code:
                units_missing_code.append(idx)

            if not bidders:
                units_missing_bidders.append(code or f"index_{idx}")

            # sizes may be of various formats; just require non-empty
            if not sizes or (isinstance(sizes, list) and len(sizes) == 0):
                units_missing_sizes.append(code or f"index_{idx}")

        if units_missing_code:
            errors.append(
                f"Ad units missing code/adUnitCode at indices: {units_missing_code}"
            )

        if units_missing_bidders:
            errors.append(
                "Ad units with no bidders configured: "
                + ", ".join(units_missing_bidders)
            )

        if units_missing_sizes:
            warnings.append(
                "Ad units with no sizes configured: "
                + ", ".join(units_missing_sizes)
            )

        # Decide final state
        if errors:
            result.state = TestState.FAILED
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        if warnings:
            # We treat warnings as non-fatal but still useful to surface
            result.warnings.extend(warnings)

        # Attach metadata
        result.metadata.update(
            {
                "ad_unit_count": len(ad_units),
                "ad_units_missing_code": len(units_missing_code),
                "ad_units_missing_bidders": len(units_missing_bidders),
                "ad_units_missing_sizes": len(units_missing_sizes),
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        """
        Optional: screenshot on failure, if debug_screenshots enabled.
        """
        if result.state == TestState.FAILED and self.config.get("debug_screenshots"):
            try:
                screenshot_path = f"debug/adunit_config_fail_{hash(result.url)}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                result.metadata["debug_screenshot"] = screenshot_path
            except Exception:
                pass