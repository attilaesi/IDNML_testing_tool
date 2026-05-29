"""
prebid: PbjsPriceFloorsVideoTest

What this test checks
---------------------
Validates that Prebid price floors are configured and active for VIDEO auctions.
Uses window.__pbjsBidEventsVideo (populated by BrowserManager) to confirm video
activity occurred, then checks the priceFloors module and rule configuration.

Test conditions
---------------
- Page must be a video page (pageType == video); otherwise skipped.
- window.__pbjsBidEventsVideo must contain bidRequested events.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: priceFloors module installed (or config present), enabled, floor rules exist,
  and at least one video-applicable rule is configured.
- FAILED: priceFloors module not installed and no floors config present.
- FAILED: floors config present but disabled.
- FAILED: floors config enabled but no rules configured.
- FAILED: no video-applicable floor rules found.
- SKIPPED: no video Prebid activity observed (non-video page or no events captured).
"""
# tests/prebid_tests/pbjs_prebid_price_floors_video_test.py

from typing import Any, Dict, List

from core.base_test import VideoOnlyTest, TestResult, TestState

class PbjsPriceFloorsVideoTest(VideoOnlyTest):

    """
    Validates Prebid price floors configuration for VIDEO auctions.

    Uses the existing video event store populated by BrowserManager:
      - window.__pbjsBidEventsVideo

    Answers:
      - Did we observe any VIDEO Prebid activity?
      - Is the priceFloors module/config present & enabled?
      - Are there any floor rules configured?
      - Are there any floor rules that look VIDEO-applicable?

    Notes:
      - "video-applicable" is determined heuristically:
          * rule.mediaType == 'video' OR rule.mediaTypes includes 'video'
          * OR mediaType is missing (treated as applies-to-all)
      - Banner-only rules are ignored for video.
    """

    name = "PbjsPriceFloorsVideoTest"

    WAIT_AFTER_DOM_MS = 1500

    async def _video_setup(self, page, url: str) -> bool:
        try:
            await page.wait_for_load_state("domcontentloaded")
            try:
                await page.wait_for_timeout(self.WAIT_AFTER_DOM_MS)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"[PbjsPriceFloorsVideoTest] setup error: {e}")
            return False

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        result.state = TestState.PASSED
        result.data = {}

        try:
            diag = await page.evaluate(
                """
                () => {
                  const out = {
                    pageType: null,

                    // observed activity
                    has_video_store: false,
                    video_events_total: 0,
                    video_bidrequested_events: 0,
                    video_auctioninit_events: 0,
                    video_auctionend_events: 0,

                    // floors snapshot
                    has_pbjs: false,
                    has_getConfig: false,
                    module_present: false,
                    installed_modules: null,

                    has_floors_config: false,
                    enabled: false,
                    provider: null,
                    rules_count: 0,
                    video_applicable_rules_count: 0,

                    raw_config: null,
                    errors: []
                  };

                  const safeKeys = (o) => {
                    try { return o && typeof o === 'object' ? Object.keys(o) : []; }
                    catch (e) { return []; }
                  };

                  const getFloorsCfg = (pbjs) => {
                    let cfg = null;
                    try { cfg = pbjs.getConfig ? pbjs.getConfig('floors') : null; } catch (e) {}
                    try {
                      if (!cfg || safeKeys(cfg).length === 0) {
                        const full = pbjs.getConfig ? (pbjs.getConfig() || {}) : {};
                        if (full && full.floors) cfg = full.floors;
                      }
                    } catch (e) {}
                    return cfg || null;
                  };

                  const getValuesObj = (cfg) => {
                    try {
                      return (cfg && cfg.data && cfg.data.values) ||
                             (cfg && cfg.values) ||
                             null;
                    } catch (e) { return null; }
                  };

                  const looksVideoApplicable = (rule) => {
                    try {
                      if (!rule || typeof rule !== 'object') return true;

                      const mt = rule.mediaType;
                      if (typeof mt === 'string') {
                        return mt.toLowerCase() === 'video';
                      }

                      const mts = rule.mediaTypes;
                      if (Array.isArray(mts)) {
                        return mts.map(x => String(x || '').toLowerCase()).includes('video');
                      }

                      const t = rule.type;
                      if (typeof t === 'string') {
                        return t.toLowerCase() === 'video';
                      }

                      // No media type specified => global => applies to video
                      return true;
                    } catch (e) {
                      return true;
                    }
                  };

                  // ------------------------------------------------------------
                  // 1) VIDEO STORE OBSERVATION
                  // ------------------------------------------------------------
                  try {
                    const store = Array.isArray(window.__pbjsBidEventsVideo)
                      ? window.__pbjsBidEventsVideo
                      : null;

                    if (store) {
                      out.has_video_store = true;
                      out.video_events_total = store.length;

                      for (let i = 0; i < store.length; i++) {
                        const ev = store[i] || {};
                        const type = String(ev.type || '');
                        if (type === 'bidRequested') out.video_bidrequested_events += 1;
                        if (type === 'auctionInit') out.video_auctioninit_events += 1;
                        if (type === 'auctionEnd') out.video_auctionend_events += 1;
                      }
                    }
                  } catch (e) {}

                  // ------------------------------------------------------------
                  // 2) FLOORS CONFIG EXTRACTION
                  // ------------------------------------------------------------
                  try {
                    const pbjs = window.pbjs;
                    if (!pbjs) {
                      out.errors.push('window.pbjs is not defined');
                      return out;
                    }
                    out.has_pbjs = true;

                    if (Array.isArray(pbjs.installedModules)) {
                      out.installed_modules = pbjs.installedModules.slice();
                      out.module_present = pbjs.installedModules.includes('priceFloors');
                    }

                    if (typeof pbjs.getConfig !== 'function') {
                      out.errors.push('pbjs.getConfig is not available');
                      return out;
                    }
                    out.has_getConfig = true;

                    const floorsCfg = getFloorsCfg(pbjs);
                    if (!floorsCfg) {
                      out.has_floors_config = false;
                      return out;
                    }

                    out.raw_config = floorsCfg;
                    out.has_floors_config = true;

                    if (Object.prototype.hasOwnProperty.call(floorsCfg, 'enabled')) {
                      out.enabled = !!floorsCfg.enabled;
                    } else {
                      out.enabled = true;
                    }

                    if (floorsCfg.data && floorsCfg.data.provider) out.provider = floorsCfg.data.provider;
                    else if (floorsCfg.provider) out.provider = floorsCfg.provider;

                    const valuesObj = getValuesObj(floorsCfg);
                    if (valuesObj && typeof valuesObj === 'object') {
                      const keys = Object.keys(valuesObj);
                      out.rules_count = keys.length;

                      let vcount = 0;
                      for (let i = 0; i < keys.length; i++) {
                        if (looksVideoApplicable(valuesObj[keys[i]])) vcount += 1;
                      }
                      out.video_applicable_rules_count = vcount;
                    }

                    if (!out.module_present && out.has_floors_config) out.module_present = true;

                  } catch (e) {
                    out.errors.push(String(e));
                  }

                  try {
                    const pubads = window.googletag && googletag.pubads ? googletag.pubads() : null;
                    if (pubads) {
                      const pt = pubads.getTargeting("pageType");
                      if (pt && pt[0]) out.pageType = String(pt[0]).toLowerCase();
                    }
                  } catch (e) {}

                  return out;
                }
                """
            )

            result.data["prebid_floors_video"] = diag

        except Exception as e:
            result.state = TestState.ERROR
            result.errors.append(f"JS extraction failed: {e}")

        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.state == TestState.ERROR:
            return result

        floors = (result.data or {}).get("prebid_floors_video", {}) or {}

        errors: List[str] = []
        warnings: List[str] = []

        for err in floors.get("errors", []) or []:
            warnings.append(f"Extraction warning: {err}")

        has_store = bool(floors.get("has_video_store"))
        bidreq = int(floors.get("video_bidrequested_events") or 0)

        if not has_store or bidreq == 0:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "No video Prebid activity observed (window.__pbjsBidEventsVideo missing or no bidRequested)."
            )
            result.metadata.update(
                {
                    "video_events_total": int(floors.get("video_events_total") or 0),
                    "video_bidrequested_events": bidreq,
                }
            )
            return result

        module_present = bool(floors.get("module_present"))
        has_cfg = bool(floors.get("has_floors_config"))
        enabled = bool(floors.get("enabled"))
        rules_count = int(floors.get("rules_count") or 0)
        video_rules = int(floors.get("video_applicable_rules_count") or 0)
        provider = floors.get("provider")

        if not module_present and not has_cfg:
            errors.append("Video floors: priceFloors module not installed and no floors config present")

        if not module_present and has_cfg:
            warnings.append("Video floors: floors config present but priceFloors not listed in pbjs.installedModules")

        if has_cfg and not enabled:
            errors.append("Video floors: floors config present but disabled (floors.enabled === false)")

        if has_cfg and enabled and rules_count == 0:
            errors.append("Video floors: no floor rules configured")
        elif has_cfg and enabled and video_rules == 0:
            errors.append("Video floors: no video-applicable floor rules found")

        if has_cfg and enabled and not provider:
            warnings.append("Video floors: provider not specified")

        if errors:
            result.state = TestState.FAILED
            result.errors.append("Video floors invalid")
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        if warnings:
            result.warnings.extend(warnings)

        result.metadata.update(
            {
                "video_events_total": int(floors.get("video_events_total") or 0),
                "video_bidrequested_events": int(floors.get("video_bidrequested_events") or 0),
                "floors_module_present": module_present,
                "floors_has_config": has_cfg,
                "floors_enabled": enabled,
                "floors_rules_count": rules_count,
                "floors_video_applicable_rules_count": video_rules,
                "floors_provider": provider,
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return