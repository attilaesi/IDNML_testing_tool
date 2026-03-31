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
    - A slot is MISSING or appears at the wrong paragraph position.
    - Slots whose expectedAfter position exceeds the article's total paragraph
      count are silently skipped (article too short to test them).

* PASSED:
    - All resolved slots appear at their expected position (or +1 image grace).
"""

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class LayoutAdSequenceTest(BaseTest):

    async def setup(self, page, url: str) -> bool:
        has_main = await page.evaluate("() => !!document.getElementById('main')")
        if not has_main:
            return False

        # Poll up to 5s for Taboola to inject rendered content.
        # The framework already scrolled the full page before tests run.
        # We require an actual rbox with items, not just an empty container.
        try:
            await page.wait_for_function(
                """() => {
                    const rbox = document.querySelector(".trc_rbox");
                    if (rbox && rbox.querySelector(".trc_rbox_div")) return true;
                    const items = document.querySelectorAll(
                        ".trc_related_container .trc-item, "
                        + ".tbl-trecs-container .trc-item, "
                        + "[id^='taboola-'] .trc-item"
                    );
                    return items.length > 0;
                }""",
                polling=250,
                timeout=5000,
            )
        except Exception:
            pass

        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        js = r"""
        () => {
          const MIN_CHARS = 100;
          const MAX_WAIT_MS = 2500;
          const SETTLE_MS = 400;

          const container = document.getElementById("main");
          if (!container) return { error: "no #main" };

          function getCookie(name) {
            const m = document.cookie.match(
              new RegExp("(?:^|;\\s*)" + name + "=([^;]*)")
            );
            return m ? decodeURIComponent(m[1]) : null;
          }

          const featUseLightAdRules =
            (getCookie("feat__use_light_ad_rules") || "").toLowerCase() === "true";
          const isMobileOrTablet =
            (getCookie("is_mobile_or_tablet") || "").toLowerCase() === "true";

          function isVisible(el) {
            if (!el) return false;
            const cs = getComputedStyle(el);
            if (cs.display === "none" || cs.visibility === "hidden") return false;
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
          }

          function isImageBlock(el) {
            if (!el) return false;
            if (el.matches && el.matches("figure, picture")) return true;
            return !!(el.querySelector && el.querySelector("figure img, picture img, img"));
          }

          function findSlotByName(name) {
            if (!name) return null;
            let el = document.getElementById(name);
            if (el) return el;

            const base = name.replace(/-m$/, "");
            el = container.querySelector(
              '[data-tile-name="' + name + '"], [data-tile-name="' + base + '"]'
            );
            if (el) return el;

            el = container.querySelector('iframe[id*="' + name + '"]');
            if (el) {
              return el.closest("div[id], .third-party-ad, .sc-r9kkgp-2, .sc-r9kkgp-0") || el;
            }

            try {
              el = container.querySelector('[id$="' + CSS.escape(name) + '"]');
              if (el) return el;
            } catch(e) {}

            return null;
          }

          function findRecommendedBlock() {
            for (const child of container.children) {
              if (!isVisible(child)) continue;

              // Inline recommended block
              const label = child.querySelector("span, h2, h3, h4, [role='heading']");
              if (/^recommended$/i.test((label && label.textContent || "").trim())) {
                if (child.querySelector("ul li a")) return child;
              }

              // Taboola recommended block
              const outer = child.matches &&
                child.matches(".trc_related_container, .tbl-trecs-container, [id^='taboola-']")
                ? child
                : child.querySelector &&
                  child.querySelector(".trc_related_container, .tbl-trecs-container, [id^='taboola-']");
              if (!outer) continue;
              const rbox = outer.querySelector(".trc_rbox");
              if (!rbox) continue;
              const layouts = [
                "alternating-thumbnails-stream-1x4",
                "alternating-thumbnails-stream-1x4-a",
                "alternating-thumbnails-d1"
              ];
              if (!layouts.some(cls => rbox.classList.contains(cls))) continue;
              const h = outer.querySelector(
                ".trc_rbox_header_span, [role='heading'], h2, h3, h4, span"
              );
              if (/^recommended$/i.test((h && h.textContent || "").trim())) return child;
            }
            return null;
          }

          function findTaboolaAd() {
            const containers = Array.from(container.querySelectorAll(
              ".trc_related_container, .tbl-trecs-container, [id^='taboola-'], .taboola"
            )).filter(isVisible);

            for (const outer of containers) {
              const rbox = outer.querySelector(
                ".trc_rbox.alternating-thumbnails-d1.trc-content-sponsored"
              );
              if (!rbox || !isVisible(rbox)) continue;
              const t = (outer.textContent || "").trim();
              if (/(promoted|sponsored|Sponsored Links|by Taboola|Promoted Links)/i.test(t)) {
                return outer;
              }
            }

            const allRboxes = Array.from(container.querySelectorAll(
              ".trc_rbox.alternating-thumbnails-d1.trc-content-sponsored"
            )).filter(isVisible);

            for (const r of allRboxes) {
              const block = r.closest(
                ".trc_related_container, .tbl-trecs-container, [id^='taboola-'], .taboola"
              ) || r;
              const t = (block.textContent || "").trim();
              if (/(promoted|sponsored|Sponsored Links|by Taboola|Promoted Links)/i.test(t)) {
                return block;
              }
            }
            return null;
          }

          function collectAllSlotNames() {
            const names = new Set();
            container.querySelectorAll("[data-tile-name]").forEach(function(el) {
              const n = el.getAttribute("data-tile-name");
              if (n) names.add(n);
            });
            container.querySelectorAll("[id]").forEach(function(el) {
              if (/^mpu\d+(?:-m)?$/.test(el.id)) names.add(el.id);
            });
            return Array.from(names);
          }

          // --- Build rule set ---
          const allSlotNames = collectAllSlotNames();
          let ruleSetName, mustHaveKeys, targets;

          if (featUseLightAdRules) {
            ruleSetName = "light";
            mustHaveKeys = ["mpu1-m", "recommended", "taboola_ad"];
            targets = [
              { key:"mpu1-m",      expectedAfter:3,  finder:function(){ return findSlotByName("mpu1-m"); } },
              { key:"recommended", expectedAfter:5,  finder:findRecommendedBlock },
              { key:"taboola_ad",  expectedAfter:7,  finder:findTaboolaAd },
              { key:"mpu2-m",      expectedAfter:9,  finder:function(){ return findSlotByName("mpu2-m"); } },
              { key:"mpu3-m",      expectedAfter:13, finder:function(){ return findSlotByName("mpu3-m"); } },
              { key:"mpu4-m",      expectedAfter:18, finder:function(){ return findSlotByName("mpu4-m"); } },
              { key:"mpu5-m",      expectedAfter:25, finder:function(){ return findSlotByName("mpu5-m"); } },
              { key:"mpu6-m",      expectedAfter:30, finder:function(){ return findSlotByName("mpu6-m"); } },
            ];
          } else if (isMobileOrTablet) {
            ruleSetName = "heavy-mobile";
            mustHaveKeys = ["mpu1-m", "taboola_ad"];
            targets = [
              { key:"mpu1-m",     expectedAfter:2,  finder:function(){ return findSlotByName("mpu1-m"); } },
              { key:"mpu2-m",     expectedAfter:4,  finder:function(){ return findSlotByName("mpu2-m"); } },
              { key:"taboola_ad", expectedAfter:6,  finder:findTaboolaAd },
              { key:"mpu3-m",     expectedAfter:8,  finder:function(){ return findSlotByName("mpu3-m"); } },
              { key:"mpu4-m",     expectedAfter:10, finder:function(){ return findSlotByName("mpu4-m"); } },
            ];
            const mobileMpus = allSlotNames
              .map(function(n) {
                const m = n.match(/^mpu(\d+)-m$/);
                return m ? Number(m[1]) : null;
              })
              .filter(function(n) { return n != null && n >= 5; });
            const maxN = mobileMpus.length ? Math.max.apply(null, mobileMpus) : 4;
            for (let n = 5; n <= maxN; n++) {
              (function(num) {
                targets.push({
                  key: "mpu" + num + "-m",
                  expectedAfter: 12 + (num - 5) * 4,
                  finder: function() { return findSlotByName("mpu" + num + "-m"); }
                });
              })(n);
            }
          } else {
            ruleSetName = "heavy-desktop";
            mustHaveKeys = ["mpu1", "taboola_ad"];
            targets = [
              { key:"mpu1",       expectedAfter:3, finder:function(){ return findSlotByName("mpu1"); } },
              { key:"taboola_ad", expectedAfter:6, finder:findTaboolaAd },
              { key:"mpu2",       expectedAfter:8, finder:function(){ return findSlotByName("mpu2"); } },
              { key:"mpu3",       expectedAfter:10, finder:function(){ return findSlotByName("mpu3"); } },
            ];
          }

          // --- Resolve slots ---
          const found = {};
          targets.forEach(function(t) {
            try { const el = t.finder(); if (el) found[t.key] = true; }
            catch(e) {}
          });

          const mustHavePresent = mustHaveKeys.some(function(k) { return found[k]; });
          if (!mustHavePresent) {
            return {
              ruleSetName: ruleSetName,
              skipped: true,
              reason: "None of the must-have slots found: " + mustHaveKeys.join(", "),
            };
          }

          // --- Walk DOM and count paragraphs ---
          let pCount = 0;
          let charBucket = 0;
          const firstSeen = {};
          const pCountBefore = [];
          const children = Array.from(container.children);

          // First pass: resolve slot → DOM element
          const resolvedEls = {};
          targets.forEach(function(t) {
            try { const el = t.finder(); if (el) resolvedEls[t.key] = el; }
            catch(e) {}
          });

          for (let i = 0; i < children.length; i++) {
            const child = children[i];
            if (!isVisible(child)) { pCountBefore[i] = pCount; continue; }

            targets.forEach(function(t) {
              if (firstSeen[t.key] != null) return;
              const el = resolvedEls[t.key];
              if (!el) return;
              if (child === el || child.contains(el)) firstSeen[t.key] = pCount;
            });

            pCountBefore[i] = pCount;

            if (child.tagName === "P" && child.parentElement === container) {
              const txt = (child.textContent || "").replace(/\s+/g, " ").trim();
              if (txt) {
                charBucket += txt.length;
                if (charBucket >= MIN_CHARS) { pCount++; charBucket = 0; }
              }
            }
          }

          // --- Build row results ---
          function passesImageGrace(t, seenAfter) {
            if (seenAfter !== t.expectedAfter + 1) return false;
            for (let i = 0; i < pCountBefore.length; i++) {
              if (pCountBefore[i] === t.expectedAfter) {
                const el = children[i];
                return el ? isImageBlock(el) : false;
              }
            }
            return false;
          }

          const rows = targets.map(function(t) {
            const el = resolvedEls[t.key];
            const seenAfter = firstSeen[t.key];
            let status;

            // Article too short to reach this slot's expected position — skip.
            if (pCount <= t.expectedAfter) {
              status = "SKIPPED (article too short: " + pCount + " paragraphs, needs >" + t.expectedAfter + ")";
            } else if (!el) {
              status = "MISSING";
            } else if (seenAfter == null) {
              status = "MISSING (not reached)";
            } else if (seenAfter === t.expectedAfter) {
              status = "PASS";
            } else if (passesImageGrace(t, seenAfter)) {
              status = "PASS (image shift to " + seenAfter + ")";
            } else {
              status = "FAIL (seen after " + seenAfter + ", expected " + t.expectedAfter + ")";
            }

            return {
              unit: t.key,
              expectedAfter: t.expectedAfter,
              seenAfter: (el && seenAfter != null) ? seenAfter : null,
              status: status,
            };
          });

          // --- DOM slots found on the page ---
          const domSlots = collectAllSlotNames().sort();

          // --- GPT slot ad unit paths ---
          const gptSlots = [];
          try {
            if (window.googletag && googletag.pubads) {
              (googletag.pubads().getSlots() || []).forEach(function(s) {
                const path = s.getAdUnitPath ? s.getAdUnitPath() : null;
                const id = s.getSlotElementId ? s.getSlotElementId() : null;
                if (path || id) gptSlots.push(id || path);
              });
            }
          } catch(e) {}

          // --- Slot number continuity check ---
          // Extract mpu numbers from resolved slots and verify no gaps in sequence.
          const mpuSuffix = isMobileOrTablet ? "-m" : "";
          const mpuRe = isMobileOrTablet ? /^mpu(\d+)-m$/ : /^mpu(\d+)$/;
          const mpuNums = Object.keys(resolvedEls)
            .map(function(k) { const m = k.match(mpuRe); return m ? Number(m[1]) : null; })
            .filter(function(n) { return n != null; })
            .sort(function(a, b) { return a - b; });

          let continuityFail = null;
          if (mpuNums.length >= 2) {
            for (let i = 1; i < mpuNums.length; i++) {
              if (mpuNums[i] !== mpuNums[i - 1] + 1) {
                continuityFail = "mpu" + mpuNums[i - 1] + mpuSuffix
                  + " → mpu" + mpuNums[i] + mpuSuffix
                  + " (gap: missing mpu" + (mpuNums[i - 1] + 1) + mpuSuffix + ")";
                break;
              }
            }
          }

          return {
            ruleSetName: ruleSetName,
            isMobileOrTablet: isMobileOrTablet,
            featUseLightAdRules: featUseLightAdRules,
            totalParagraphs: pCount,
            domSlots: domSlots,
            gptSlots: gptSlots,
            mpuSequence: mpuNums,
            continuityFail: continuityFail,
            rows: rows,
          };
        }
        """

        diag = await page.evaluate(js)
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
        print(f"         layout rule: {rule_label}  paragraphs: {paragraphs}")
        print(f"         DOM slots : {', '.join(dom_slots) if dom_slots else '(none)'}")
        print(f"         GPT slots : {', '.join(gpt_slots) if gpt_slots else '(none)'}")

        continuity_fail: str = diag.get("continuityFail") or ""
        mpu_sequence: List[int] = diag.get("mpuSequence", [])

        skipped = [r for r in rows if r["status"].startswith("SKIPPED")]
        failures = [r for r in rows if r["status"].startswith("FAIL") or r["status"].startswith("MISSING")]
        passes = [r for r in rows if r["status"].startswith("PASS")]

        layout_label = "lighter-ad-layout" if light else "standard-ad-layout"
        layout_context = f"{layout_label}  rule_set={rule_set}  paragraphs={paragraphs}"

        if failures or continuity_fail:
            result.state = TestState.FAILED
            for r in failures:
                result.errors.append(f"{r['unit']}: {r['status']}")
            if continuity_fail:
                result.errors.append(f"slot sequence gap: {continuity_fail}")
        else:
            result.state = TestState.PASSED

        result.warnings.append(
            f"{layout_context}  "
            f"slots checked={len(rows)}  passed={len(passes)}  "
            f"failed={len(failures)}  skipped={len(skipped)}"
        )
        result.metadata["layout_context"] = layout_context
        result.metadata["rows"] = rows
        result.metadata["ruleSetName"] = rule_set
        result.metadata["mpuSequence"] = mpu_sequence

        return result
