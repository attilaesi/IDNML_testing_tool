# tests/layout_tests/layout_ad_sequence_test.py

"""
layout:ad_sequence

What this test is meant to test
-------------------------------
Verifies that ad slots appear at the correct paragraph positions within the
article body (#main), according to the active ad rule set:

  - light     (feat__use_light_ad_rules cookie = true)
      mpu1-m @3, recommended @5, taboola_ad @7, mpu2-m @9, …
  - heavy-mobile  (is_mobile_or_tablet = true, no light override)
      mpu1-m @2, mpu2-m @4, taboola_ad @6, mpu3-m @8, mpu4-m @10, …
  - heavy-desktop (desktop, no light override)
      mpu1 @3, taboola_ad @6, mpu2 @8, mpu3 @10

Paragraph counting: each top-level <p> direct child of #main contributes
its character count to a running bucket. The bucket resets every 100 chars
and pCount increments. A slot "seen after N" means it appeared in the DOM
between paragraph N and N+1.

An image block immediately before the expected position is granted a +1
grace (PASS with note).

The test only runs on article pages — not liveblog or index.

Test conditions
---------------
- #main container must be present.
- At least the must-have slots for the active rule set must resolve.

What counts as PASS / FAIL / SKIPPED
------------------------------------
* SKIPPED:
    - #main not found.
    - None of the must-have slots could be resolved (ads not on page).

* FAILED:
    - A slot exists in the DOM but is more than 1 paragraph away from its
      expected position.

* WARNED:
    - A slot exists but is exactly 1 paragraph off (close enough, noted only).

* SKIPPED (per slot):
    - Anchor not placed on the page — article too short or site chose not to
      insert it. Not a failure.
    - Slot's expected position exceeds total paragraph count.

* PASSED:
    - All resolved slots appear at their expected position (or +1 image grace).
"""

import re
from pathlib import Path
from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "layout_ad_sequence.js").read_text()


class LayoutAdSequenceTest(BaseTest):

    async def setup(self, page, url: str) -> bool:
        has_main = await page.evaluate("() => !!document.getElementById('main')")
        if not has_main:
            return False

        # Skip pages with no GPT slots — nothing to test.
        has_gpt_slots = await page.evaluate("""
            () => {
                try {
                    return !!(window.googletag && googletag.pubads &&
                              googletag.pubads().getSlots().length > 0);
                } catch(e) { return false; }
            }
        """)
        if not has_gpt_slots:
            return False

        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        diag = await page.evaluate(_JS)
        result.data = diag or {}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        diag: Dict[str, Any] = result.data or {}

        if diag.get("error"):
            result.state = TestState.ERROR
            result.errors.append(f"JS error: {diag['error']}")
            return result

        if diag.get("skipped"):
            result.state = TestState.SKIPPED
            result.warnings.append(diag.get("reason", "Must-have slots not found."))
            return result

        rows: List[Dict] = diag.get("rows", [])
        rule_set: str = diag.get("ruleSetName", "unknown")
        paragraphs: int = diag.get("totalParagraphs", 0)
        dom_slots: List[str] = diag.get("domSlots", [])
        gpt_slots: List[str] = diag.get("gptSlots", [])
        light = diag.get("featUseLightAdRules", False)
        mobile = diag.get("isMobileOrTablet", False)

        rule_label = f"{'light' if light else 'heavy'}-{'mobile' if mobile else 'desktop'}"
        if self.config.get("trace"):
            print(f"         layout rule: {rule_label}  paragraphs: {paragraphs}")
            print(f"         DOM slots : {', '.join(dom_slots) if dom_slots else '(none)'}")
            print(f"         GPT slots : {', '.join(gpt_slots) if gpt_slots else '(none)'}")

        continuity_fail: str = diag.get("continuityFail") or ""
        mpu_sequence: List[int] = diag.get("mpuSequence", [])

        # --- is_mobile_or_tablet cookie check ---
        from core.device_helpers import is_mobile_viewport
        expected_mobile = is_mobile_viewport(self.config)
        mobile_cookie_raw = diag.get("mobileCookieRaw")  # None if absent
        mobile_cookie_errors: List[str] = []
        if mobile_cookie_raw is None:
            mobile_cookie_errors.append(
                "is_mobile_or_tablet cookie not set by site "
                f"(expected {'true' if expected_mobile else 'false'})"
            )
        elif (mobile_cookie_raw.lower() == "true") != expected_mobile:
            mobile_cookie_errors.append(
                f"is_mobile_or_tablet cookie mismatch: "
                f"site set '{mobile_cookie_raw}', "
                f"expected '{'true' if expected_mobile else 'false'}' "
                f"based on test config (mobile={expected_mobile})"
            )

        skipped    = [r for r in rows if r["status"].startswith("SKIPPED")]
        failures   = [r for r in rows if r["status"].startswith("FAIL")]
        near_misses = [r for r in rows if r["status"].startswith("WARN")]
        passes     = [r for r in rows if r["status"].startswith("PASS")]

        # GPT cross-check: expected MPU slots must be registered with GPT.
        # "Expected" = article long enough (not SKIPPED) and slot is an MPU.
        # Exclude mobile_footer — it lives outside #main.
        gpt_slot_ids = set(gpt_slots) - {"mobile_footer"}
        mpu_re = r"^mpu\d+(?:-m)?$"
        gpt_errors: List[str] = []
        for r in rows:
            if r["status"].startswith("SKIPPED"):
                continue
            unit = r["unit"]
            if re.match(mpu_re, unit) and unit not in gpt_slot_ids:
                gpt_errors.append(f"{unit}: expected on page but not registered in GPT")

        layout_label = "light" if light else "standard"
        expected_slots = [r["unit"] for r in rows if not r["status"].startswith("SKIPPED")]
        layout_tag = f"layout={layout_label}, paragraphs={paragraphs}, expected=[{', '.join(expected_slots)}]"

        if failures or continuity_fail or gpt_errors or mobile_cookie_errors:
            result.state = TestState.FAILED
            for e in mobile_cookie_errors:
                result.errors.append(e)
            for r in failures:
                result.errors.append(f"{r['unit']}: {r['status']}")
            if continuity_fail:
                result.errors.append(f"slot sequence gap: {continuity_fail}")
            for e in gpt_errors:
                result.errors.append(e)
        else:
            result.state = TestState.PASSED

        for r in near_misses:
            result.warnings.append(f"{r['unit']}: {r['status']}")

        result.warnings.append(
            f"layout={layout_label}  rule_set={rule_set}  paragraphs={paragraphs}  "
            f"slots checked={len(rows)}  passed={len(passes)}  "
            f"warned={len(near_misses)}  failed={len(failures)}  skipped={len(skipped)}"
        )
        result.metadata["layout_tag"] = layout_tag
        result.metadata["rows"] = rows
        result.metadata["ruleSetName"] = rule_set
        result.metadata["mpuSequence"] = mpu_sequence
        result.metadata["gpt_slot_ids"] = sorted(gpt_slot_ids)

        # Scalar attributes surfaced in the crawler sheet report
        result.metadata["rule_label"] = rule_label
        result.metadata["paragraphs"] = paragraphs
        result.metadata["slots_passed"] = len(passes)
        result.metadata["slots_failed"] = len(failures)
        result.metadata["slots_warned"] = len(near_misses)
        result.metadata["slots_skipped"] = len(skipped)

        return result
