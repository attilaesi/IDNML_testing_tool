# tests/gpt_tests/gpt_anonymised_key_test.py
"""
gpt: anonymised

What this test is meant to test
-------------------------------
Checks whether GPT page-level targeting exposes an "anonymised" signal
for lift / experiment analysis, typically under the key:

    "AnonymisedSignalLift"

This is often used for anonymous experiment bucketing or signal-lift
measurement.

Test conditions
---------------
1. GPT (window.googletag.pubads) must be present.
2. We attempt to read targeting for any of the following keys:
      - "AnonymisedSignalLift"
      - "anonymised"
   (First non-empty one wins.)

What counts as PASS / FAIL / SKIPPED
------------------------------------
* SKIPPED:
    - GPT / googletag.pubads() is not available.
    - pubads.getTargeting is not a function.

* FAILED:
    - GPT is present but none of the anonymised keys above have any values.

* PASSED:
    - At least one anonymised key has one or more values returned by
      googletag.pubads().getTargeting().
"""

from typing import Dict, Any, List

from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState


class GptAnonymisedKeyTest(GptBaseTest):
    NORMALIZED_NAME = "gpt_anonymised_key_test"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = self.NORMALIZED_NAME

    """See module docstring for full explanation."""

    async def execute(self, page, url: str) -> TestResult:
        """
        Execute phase.

        We pull the anonymised-related targeting values from GPT and store
        them into result.data for validation.
        """
        result = TestResult(self.name)
        result.url = url

        js = """
        () => {
          const out = {
            hasGpt: false,
            keyUsed: null,
            values: [],
            error: null
          };

          try {
            if (!window.googletag || !googletag.pubads) {
              return out;
            }
            const pubads = googletag.pubads();
            if (!pubads || typeof pubads.getTargeting !== "function") {
              out.hasGpt = !!pubads;
              return out;
            }

            out.hasGpt = true;

            const candidateKeys = ["AnonymisedSignalLift", "anonymised"];
            for (const k of candidateKeys) {
              try {
                const v = pubads.getTargeting(k) || [];
                if (Array.isArray(v) && v.length > 0) {
                  out.keyUsed = k;
                  out.values = v;
                  break;
                }
              } catch (e) {
                // ignore errors per key; we'll just try the next one
              }
            }
          } catch (e) {
            out.error = String(e);
          }

          return out;
        }
        """

        diag = await page.evaluate(js)
        result.data = diag or {}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        """
        Validation phase.

        Uses result.data gathered in execute() to decide PASS / FAIL / SKIPPED.
        """
        diag: Dict[str, Any] = result.data or {}
        has_gpt = bool(diag.get("hasGpt", False))
        key_used = diag.get("keyUsed")
        values: List[Any] = diag.get("values") or []
        error = diag.get("error")

        # GPT not available -> SKIPPED
        if not has_gpt:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "GPT (googletag.pubads) not available; cannot inspect anonymised targeting."
            )
            return result

        # JS error while reading targeting -> ERROR
        if error:
            result.state = TestState.ERROR
            result.errors.append(f"Error while reading anonymised targeting: {error}")
            return result

        # No key / no values -> FAILED
        if not key_used or not values:
            result.state = TestState.FAILED
            result.errors.append(
                "No anonymised targeting found in GPT "
                "(keys tried: AnonymisedSignalLift, anonymised)."
            )
            return result

        # Otherwise -> PASSED
        result.state = TestState.PASSED
        # Add a bit of context into warnings so you can see it in output
        result.warnings.append(
            f"Anonymised targeting present under key '{key_used}' "
            f"with {len(values)} value(s)."
        )
        return result