from core.base_test import BaseTest, TestResult, TestState
from core.data_extractor import DataExtractor


class PrebidEnvironmentTest(BaseTest):
    """
    Smoke test for the Prebid environment.

    Answers:
      - Is window.pbjs present?
      - Is pbjs.que initialised as an array?
      - Is a Prebid version exposed?
      - Are any Prebid modules installed?

    This test assumes:
      - The framework already navigated to the URL
      - CMP has been handled
      - pbjs / GPT readiness has been waited for
    """

    name = "PrebidEnvironmentTest"

    async def setup(self, page, url: str) -> bool:
        """
        Framework has already done navigation & CMP.
        We only ensure DOM is ready. No extra navigation here.
        """
        try:
            await page.wait_for_load_state("domcontentloaded")
            return True
        except Exception as e:
            print(f"[PrebidEnvironmentTest] setup error: {e}")
            return False

    async def execute(self, page, url: str) -> TestResult:
        """
        Gather a minimal snapshot of the Prebid environment.
        """
        result = TestResult(self.name)
        result.url = url
        result.state = TestState.PASSED
        result.data = {}

        try:
            # Basic page metrics (slots, paragraphs, etc.) – useful context
            basic_data = await DataExtractor.extract_basic_data(page, url)
            result.data.update(basic_data)

            # Snapshot of Prebid presence and modules
            prebid_env = await page.evaluate(
                """
                () => {
                    const out = {
                        pbjs_loaded: false,
                        queue_ready: false,
                        version: null,
                        installed_modules: [],
                        errors: []
                    };

                    try {
                        const pbjs = window.pbjs;

                        if (!pbjs) {
                            return out;
                        }

                        out.pbjs_loaded = true;
                        out.queue_ready = Array.isArray(pbjs.que);
                        out.version = pbjs.version || null;

                        if (Array.isArray(pbjs.installedModules)) {
                            out.installed_modules = pbjs.installedModules.slice();
                        }
                    } catch (e) {
                        out.errors.push(String(e));
                    }

                    return out;
                }
                """
            )

            result.data["prebid_env"] = prebid_env

        except Exception as e:
            result.state = TestState.ERROR
            result.errors.append(f"JS extraction failed: {e}")

        return result

    async def validate(self, result: TestResult) -> TestResult:
        """
        Validate the Prebid environment snapshot.
        """
        if result.state == TestState.ERROR:
            return result

        prebid_env = (result.data or {}).get("prebid_env", {}) or {}
        errors = []

        # 1) pbjs global present
        if not prebid_env.get("pbjs_loaded"):
            errors.append("Prebid.js not loaded (window.pbjs missing)")

        # 2) queue initialised
        if prebid_env.get("pbjs_loaded") and not prebid_env.get("queue_ready"):
            errors.append("Prebid queue (pbjs.que) not initialised as array")

        # 3) modules installed
        installed_modules = prebid_env.get("installed_modules") or []
        if prebid_env.get("pbjs_loaded") and not installed_modules:
            errors.append("No Prebid modules installed (pbjs.installedModules empty)")

        # 4) propagate JS-side extraction errors
        for err in prebid_env.get("errors", []):
            errors.append(f"Extraction error: {err}")

        if errors:
            result.state = TestState.FAILED
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        # Metadata for CSV / debugging
        result.metadata.update(
            {
                "pbjs_loaded": prebid_env.get("pbjs_loaded", False),
                "queue_ready": prebid_env.get("queue_ready", False),
                "prebid_version": prebid_env.get("version"),
                "installed_module_count": len(installed_modules),
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        """
        Optional: screenshot on failure if debug_screenshots enabled.
        """
        if result.state == TestState.FAILED and self.config.get("debug_screenshots"):
            try:
                screenshot_path = f"debug/prebid_env_fail_{hash(result.url)}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                result.metadata["debug_screenshot"] = screenshot_path
            except Exception:
                # Don't let cleanup issues break the run
                pass