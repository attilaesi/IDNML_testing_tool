# tests/prebid_tests/price_floors_display_test.py

from typing import Any, Dict, List, Optional

from core.base_test import BaseTest, TestResult, TestState
from core.data_extractor import DataExtractor


class PriceFloorsDisplayTest(BaseTest):
    """
    Validates Prebid price floors configuration for DISPLAY auctions.

    Uses the existing display event store populated by BrowserManager:
      - window.__pbjsBidEventsDisplay

    Answers:
      - Did we observe any DISPLAY Prebid activity?
      - Is the priceFloors module/config present & enabled?
      - Are there any floor rules configured?
      - Are there any floor rules that look DISPLAY/BANNER-applicable?

    Notes:
      - "display-applicable" is determined heuristically:
          * rule.mediaType == 'banner' OR rule.mediaTypes includes 'banner'
          * OR mediaType is missing (treated as applies-to-all)
      - This is intentionally conservative: we want to avoid false FAILs when
        rules are generic (no mediaType field).
    """

    name = "PriceFloorsDisplayTest"

    # Wait a little to allow auctions to happen if your harness navigates fast
    WAIT_AFTER_DOM_MS = 1500

    async def setup(self, page, url: str) -> bool:
        try:
            await page.wait_for_load_state("domcontentloaded")
            try:
                await page.wait_for_timeout(self.WAIT_AFTER_DOM_MS)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"[PriceFloorsDisplayTest] setup error: {e}")
            return False

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        result.state = TestState.PASSED
        result.data = {}

        try:
            # Optional: basic page metrics for context
            basic_data = await DataExtractor.extract_basic_data(page, url)
            result.data.update(basic_data)

            diag = await page.evaluate(
                """
                () => {
                  const out = {
                    // observed activity
                    has_display_store: false,
                    display_events_total: 0,
                    display_bidrequested_events: 0,
                    display_auctioninit_events: 0,
                    display_auctionend_events: 0,

                    // floors snapshot
                    has_pbjs: false,
                    has_getConfig: false,
                    module_present: false,
                    installed_modules: null,

                    has_floors_config: false,
                    enabled: false,
                    provider: null,
                    rules_count: 0,
                    display_applicable_rules_count: 0,

                    raw_config: null,
                    errors: []
                  };

                  const safeObjKeys = (o) => {
                    try { return o && typeof o === 'object' ? Object.keys(o) : []; }
                    catch (e) { return []; }
                  };

                  const getFloorsCfg = (pbjs) => {
                    let floorsCfg = null;
                    try {
                      floorsCfg = pbjs.getConfig ? pbjs.getConfig('floors') : null;
                    } catch (e) {}

                    // Some stacks nest under full config
                    try {
                      if (!floorsCfg || (typeof floorsCfg === 'object' && safeObjKeys(floorsCfg).length === 0)) {
                        const fullCfg = pbjs.getConfig ? (pbjs.getConfig() || {}) : {};
                        if (fullCfg && fullCfg.floors) floorsCfg = fullCfg.floors;
                      }
                    } catch (e) {}

                    return floorsCfg || null;
                  };

                  const getValuesObj = (floorsCfg) => {
                    try {
                      return (floorsCfg && floorsCfg.data && floorsCfg.data.values) ||
                             (floorsCfg && floorsCfg.values) ||
                             null;
                    } catch (e) {
                      return null;
                    }
                  };

                  const looksBannerApplicable = (ruleObj) => {
                    // Heuristic:
                    // - if rule has explicit mediaType/mediaTypes and includes banner -> banner-applicable
                    // - if no mediaType/mediaTypes -> assume generic (applies-to-all) -> banner-applicable
                    try {
                      if (!ruleObj || typeof ruleObj !== 'object') return true;

                      const mt = ruleObj.mediaType;
                      if (typeof mt === 'string') {
                        return mt.toLowerCase() === 'banner';
                      }

                      const mts = ruleObj.mediaTypes;
                      if (Array.isArray(mts)) {
                        return mts.map(x => String(x || '').toLowerCase()).includes('banner');
                      }

                      // Some configs use "type"
                      const t = ruleObj.type;
                      if (typeof t === 'string') {
                        const tl = t.toLowerCase();
                        if (tl === 'banner' || tl === 'display') return true;
                      }

                      // No explicit media type => treat as generic
                      return true;
                    } catch (e) {
                      return true;
                    }
                  };

                  // ------------------------------------------------------------
                  // 1) DISPLAY STORE OBSERVATION
                  // ------------------------------------------------------------
                  try {
                    const store = Array.isArray(window.__pbjsBidEventsDisplay) ? window.__pbjsBidEventsDisplay : null;
                    if (store) {
                      out.has_display_store = true;
                      out.display_events_total = store.length;

                      // count key event types
                      for (let i = 0; i < store.length; i++) {
                        const ev = store[i] || {};
                        const type = (ev.type || '').toString();
                        if (type === 'bidRequested') out.display_bidrequested_events += 1;
                        if (type === 'auctionInit') out.display_auctioninit_events += 1;
                        if (type === 'auctionEnd') out.display_auctionend_events += 1;
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

                    // installedModules – presence of priceFloors module
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
                      out.raw_config = null;
                      out.has_floors_config = false;
                      return out;
                    }

                    out.raw_config = floorsCfg;
                    out.has_floors_config = true;

                    // Enabled flag
                    if (Object.prototype.hasOwnProperty.call(floorsCfg, 'enabled')) {
                      out.enabled = !!floorsCfg.enabled;
                    } else {
                      // default TRUE when config present
                      out.enabled = true;
                    }

                    // Provider (optional)
                    if (floorsCfg.data && floorsCfg.data.provider) out.provider = floorsCfg.data.provider;
                    else if (floorsCfg.provider) out.provider = floorsCfg.provider;

                    const valuesObj = getValuesObj(floorsCfg);
                    if (valuesObj && typeof valuesObj === 'object') {
                      const keys = Object.keys(valuesObj);
                      out.rules_count = keys.length;

                      // display-applicable count
                      let dcount = 0;
                      for (let i = 0; i < keys.length; i++) {
                        const k = keys[i];
                        const rule = valuesObj[k];
                        if (looksBannerApplicable(rule)) dcount += 1;
                      }
                      out.display_applicable_rules_count = dcount;
                    } else {
                      out.rules_count = 0;
                      out.display_applicable_rules_count = 0;
                    }

                    // Fallback: if config exists, treat module_present as true
                    if (!out.module_present && out.has_floors_config) out.module_present = true;

                  } catch (e) {
                    out.errors.push(String(e));
                  }

                  return out;
                }
                """
            )

            result.data["prebid_floors_display"] = diag

        except Exception as e:
            result.state = TestState.ERROR
            result.errors.append(f"JS extraction failed: {e}")

        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.state == TestState.ERROR:
            return result

        floors = (result.data or {}).get("prebid_floors_display", {}) or {}

        errors: List[str] = []
        warnings: List[str] = []

        # JS-side errors
        for err in floors.get("errors", []) or []:
            warnings.append(f"Extraction warning: {err}")

        # Require display store & some display activity, otherwise SKIP (can’t validate display floors)
        has_store = bool(floors.get("has_display_store"))
        display_bidreq = int(floors.get("display_bidrequested_events") or 0)

        if not has_store or display_bidreq == 0:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "No display Prebid activity observed (window.__pbjsBidEventsDisplay missing or no bidRequested)."
            )
            result.metadata.update(
                {
                    "display_events_total": int(floors.get("display_events_total") or 0),
                    "display_bidrequested_events": display_bidreq,
                }
            )
            return result

        module_present = bool(floors.get("module_present"))
        has_cfg = bool(floors.get("has_floors_config"))
        enabled = bool(floors.get("enabled"))
        rules_count = int(floors.get("rules_count") or 0)
        display_rules = int(floors.get("display_applicable_rules_count") or 0)
        provider = floors.get("provider")

        # 1) Module/config presence
        if not module_present and not has_cfg:
            errors.append("Display floors: priceFloors module not installed and no floors config present")

        if not module_present and has_cfg:
            warnings.append("Display floors: floors config present but priceFloors not listed in pbjs.installedModules")

        # 2) Enabled
        if has_cfg and not enabled:
            errors.append("Display floors: floors config present but disabled (floors.enabled === false)")

        # 3) Rules
        if has_cfg and enabled and rules_count == 0:
            errors.append("Display floors: no floor rules configured (floors.data.values / floors.values empty or missing)")
        elif has_cfg and enabled and display_rules == 0:
            errors.append("Display floors: no banner/display-applicable floor rules found")

        # 4) Provider optional
        if has_cfg and enabled and not provider:
            warnings.append("Display floors: provider not specified")

        if errors:
            result.state = TestState.FAILED
            # Keep roundup clean (short message), details go to metadata
            result.errors.append("Display floors invalid")
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        if warnings:
            result.warnings.extend(warnings)

        result.metadata.update(
            {
                "display_events_total": int(floors.get("display_events_total") or 0),
                "display_bidrequested_events": int(floors.get("display_bidrequested_events") or 0),
                "floors_module_present": module_present,
                "floors_has_config": has_cfg,
                "floors_enabled": enabled,
                "floors_rules_count": rules_count,
                "floors_display_applicable_rules_count": display_rules,
                "floors_provider": provider,
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return