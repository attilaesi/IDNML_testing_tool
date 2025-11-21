# tests/prebid_tests/prebid_permutive_signals_test.py

from typing import Any, Dict
from core.base_test import BaseTest, TestResult, TestState


class PermutiveSignalsConfigTest(BaseTest):
    """
    Prebid – Permutive *segment* signals test (config-level).

    What this test is meant to test:
      - Verify that the Permutive Prebid RTD module is enriching the
        Prebid ORTB2 user object with segment arrays.

    Test conditions:
      - pbjs must exist on the page and expose pbjs.getConfig().
      - We inspect pbjs.getConfig().ortb2.user.* for the following signals:
          * user.ext.data.permutive
          * user.ext.data.p_standard
          * user.ext.data.p_standard_v2
          * user.data[].name == "permutive.com" and its segment IDs

    What is considered a PASS:
      - At least one of the above segment-style signals is present and contains
        at least one segment ID.

    What is considered a FAIL:
      - pbjs.getConfig() is available, but none of the segment-style Permutive
        signals are present in the ORTB2 user object.
      - That is, Permutive appears not to be contributing segment data to
        Prebid's ORTB2 config for this page.

    NOTE:
      - This is a CONFIG-LEVEL sanity check. It does not inspect actual RTB
        bid requests per bidder; it only verifies that the shared ORTB2 user
        object is being enriched by Permutive.
    """

    async def setup(self, page, url: str) -> bool:
        """
        Setup phase:
          - Check that pbjs and pbjs.getConfig() exist.
          - If they do not, we skip the test (state=SKIPPED).
        """
        js_check = """
        () => {
          try {
            return !!(window.pbjs && typeof window.pbjs.getConfig === 'function');
          } catch (e) {
            return false;
          }
        }
        """
        try:
            has_pbjs = await page.evaluate(js_check)
        except Exception:
            has_pbjs = False

        if not has_pbjs:
            # BaseTest.run() will mark this as SKIPPED if setup returns False.
            return False

        return True

    async def execute(self, page, url: str) -> TestResult:
        """
        Execute phase:
          - Read pbjs.getConfig().ortb2.user.*.
          - Look for the four Permutive segment signal locations.
          - Return a TestResult with data["permutive_segment_signals"] listing
            which signals were found and small sample values.
        """
        result = TestResult(self.name)
        result.url = url

        js_collect = """
        () => {
          const out = {
            found: [],
          };

          try {
            const cfg = (window.pbjs && typeof window.pbjs.getConfig === 'function')
              ? window.pbjs.getConfig() || {}
              : {};

            const ortb2 = cfg.ortb2 || {};
            const user  = ortb2.user || {};
            const ext   = user.ext || {};
            const data  = (ext && ext.data) ? ext.data : {};
            const userDataArr = Array.isArray(user.data) ? user.data : [];

            function add(signal, path, value) {
              out.found.push({
                signal,
                path,
                sample: value
              });
            }

            // 1) user.ext.data.permutive
            if (data && Array.isArray(data.permutive) && data.permutive.length > 0) {
              add(
                "user.ext.data.permutive",
                "ortb2.user.ext.data.permutive",
                data.permutive.slice(0, 5)
              );
            }

            // 2) user.ext.data.p_standard
            if (data && Array.isArray(data.p_standard) && data.p_standard.length > 0) {
              add(
                "user.ext.data.p_standard",
                "ortb2.user.ext.data.p_standard",
                data.p_standard.slice(0, 5)
              );
            }

            // 3) user.ext.data.p_standard_v2
            if (data && Array.isArray(data.p_standard_v2) && data.p_standard_v2.length > 0) {
              add(
                "user.ext.data.p_standard_v2",
                "ortb2.user.ext.data.p_standard_v2",
                data.p_standard_v2.slice(0, 5)
              );
            }

            // 4) user.data[].name == "permutive.com" (ORTB2 user.data)
            if (Array.isArray(userDataArr)) {
              userDataArr.forEach((block, idx) => {
                if (!block || block.name !== "permutive.com") return;
                const segs = Array.isArray(block.segment) ? block.segment : [];
                if (!segs.length) return;
                const sampleIds = segs
                  .map(s => (s && (s.id || s.value || s.code || null)))
                  .filter(Boolean)
                  .slice(0, 5);
                if (sampleIds.length > 0) {
                  add(
                    "user.data[].segment (permutive.com)",
                    `ortb2.user.data[${idx}].segment`,
                    sampleIds
                  );
                }
              });
            }

          } catch (e) {
            out.error = String(e && e.message ? e.message : e);
          }

          return out;
        }
        """

        try:
            data: Dict[str, Any] = await page.evaluate(js_collect)
        except Exception as e:
            result.state = TestState.ERROR
            result.errors.append(f"Error while collecting Permutive signals: {str(e)}")
            return result

        result.data["permutive_segment_signals"] = data
        # Leave state as PENDING here; validate() will decide PASS/FAIL.
        return result

    async def validate(self, result: TestResult) -> TestResult:
        """
        Validation phase:
          - If at least one of the target segment signals is present, mark PASSED.
          - If none are present (but pbjs existed), mark FAILED.
        """
        data = result.data.get("permutive_segment_signals") or {}
        found = data.get("found") or []

        if result.state == TestState.ERROR:
            # Already in error; do not override
            return result

        if found:
            result.state = TestState.PASSED
        else:
            result.state = TestState.FAILED
            result.errors.append(
                "No Permutive segment signals found in Prebid ORTB2 user object "
                "(expected one or more of: user.ext.data.permutive, "
                "p_standard, p_standard_v2, or user.data[permutive.com].segment)."
            )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        """
        Cleanup phase:
          - Currently does nothing.
          - Extend later for screenshots / debug dumps if needed.
        """
        return