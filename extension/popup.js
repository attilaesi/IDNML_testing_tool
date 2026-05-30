// popup.js — Ad Inspector orchestrator
// Injects test JS into the active tab and renders pass/fail results.

"use strict";

// ---------------------------------------------------------------------------
// Category map — controls grouping and display order
// ---------------------------------------------------------------------------
const CATEGORIES = {
  "PREBID": [
    "pbjs_environment",
    "pbjs_display_bidder_presence",
    "pbjs_video_bidder_presence",
    "pbjs_auction_activity",
    "pbjs_adunit_configuration",
    "pbjs_consent_integration",
    "pbjs_identity_modules",
    "pbjs_price_floors_display",
    "pbjs_price_floors_video",
    "pbjs_pubcid_presence_display",
    "pbjs_pubcid_presence_video",
    "pbjs_timeout_config",
    "pbjs_warnings",
    "pbjs_hero_player_placement",
    "pbjs_mantis_signals_bid",
    "pbjs_permutive_signals_bid",
  ],
  "GPT": [
    "gpt_page_type",
    "gpt_mantis_context",
  ],
  "ENVIRONMENT": [
    "env_is_mobile_or_tablet",
  ],
};

// All test stems that popup.js knows about (those that need injection)
const ALL_TEST_STEMS = [
  "pbjs_environment",
  "pbjs_display_bidder_presence",
  "pbjs_video_bidder_presence",
  "pbjs_auction_activity",
  "pbjs_adunit_configuration",
  "pbjs_consent_integration",
  "pbjs_identity_modules",
  "pbjs_price_floors_display",
  "pbjs_price_floors_video",
  "pbjs_pubcid_presence_display",
  "pbjs_pubcid_presence_video",
  "pbjs_timeout_config",
  "pbjs_warnings_init",   // warnings uses a special IIFE init script
  "pbjs_hero_player_placement",
  "pbjs_mantis_signals_bid",
  "pbjs_permutive_signals_bid",
  "gpt_page_type",
  "gpt_mantis_context",
  "env_is_mobile_or_tablet",
];

// ---------------------------------------------------------------------------
// VALIDATORS — translate each Python validate() faithfully.
// Each function receives the raw data returned by the test function.
// Returns string[] — empty = PASS, non-empty = FAIL with those error messages.
// ---------------------------------------------------------------------------
const VALIDATORS = {

  "pbjs_environment": (data) => {
    const errors = [];
    const env = (data && data.prebid_env) ? data.prebid_env : (data || {});
    if (!env.pbjs_loaded) errors.push("Prebid.js not loaded (window.pbjs missing)");
    if (env.pbjs_loaded && !env.queue_ready) errors.push("Prebid queue (pbjs.que) not initialised as array");
    const modules = env.installed_modules || [];
    if (env.pbjs_loaded && !modules.length) errors.push("No Prebid modules installed (pbjs.installedModules empty)");
    for (const e of (env.errors || [])) errors.push("Extraction error: " + e);
    return errors;
  },

  "pbjs_display_bidder_presence": (data) => {
    // In extension context there's no Supabase — show seen bidders as INFO.
    // We PASS if pbjs is present and we saw bidders, FAIL if pbjs is present
    // but zero bidRequested events were captured.
    const errors = [];
    if (!data || !data.hasPbjs) {
      errors.push("window.pbjs not present; cannot run display bidder presence test.");
      return errors;
    }
    const bidRequested = parseInt(data.bidRequestedEvents || 0, 10);
    if (bidRequested === 0) {
      errors.push("No DISPLAY bidRequested events captured. Prebid may not have fired yet.");
    }
    // No Supabase in extension — we can't assert expected set. Return INFO.
    return errors;
  },

  "pbjs_video_bidder_presence": (data) => {
    const errors = [];
    if (!data || !data.hasPbjs) {
      errors.push("window.pbjs not present; cannot run video bidder presence test.");
      return errors;
    }
    const heroBidReq = parseInt(data.heroBidRequestedEvents || 0, 10);
    if (heroBidReq === 0 && parseInt(data.eventsLen || 0, 10) > 0) {
      errors.push("No hero_player VIDEO bidRequested events found in event store.");
    }
    return errors;
  },

  "pbjs_auction_activity": (data) => {
    const errors = [];
    const activity = (data && data.prebid_auction_activity) ? data.prebid_auction_activity : (data || {});
    for (const e of (activity.errors || [])) errors.push("Extraction error: " + e);
    const debug = activity.debug || {};
    const bidRequestedCount = parseInt(debug.bidRequestedCount || 0, 10);
    const totalBidResponses = parseInt(activity.total_bid_responses || 0, 10);
    if (totalBidResponses === 0) {
      if (bidRequestedCount > 0) {
        // Warning only — treated as PASS with warning in Python. We return no errors.
        // Surface as INFO; nothing to errors array.
      } else {
        errors.push("No bid responses recorded for any Prebid ad unit and no bidRequested events seen.");
      }
    }
    return errors;
  },

  "pbjs_adunit_configuration": (data) => {
    const errors = [];
    const adUnitData = (data && data.prebid_ad_units) ? data.prebid_ad_units : (data || {});
    for (const e of (adUnitData.errors || [])) errors.push("Extraction error: " + e);
    const adUnits = adUnitData.ad_units || [];
    if (!adUnits.length) {
      errors.push("No Prebid ad units configured (pbjs.adUnits is empty)");
      return errors;
    }
    const missingCode = [];
    const missingBidders = [];
    adUnits.forEach((unit, idx) => {
      if (!unit.code) missingCode.push(idx);
      if (!unit.bidders || !unit.bidders.length) missingBidders.push(unit.code || "index_" + idx);
    });
    if (missingCode.length) errors.push("Ad units missing code/adUnitCode at indices: " + missingCode.join(", "));
    if (missingBidders.length) errors.push("Ad units with no bidders configured: " + missingBidders.join(", "));
    return errors;
  },

  "pbjs_consent_integration": (data) => {
    const errors = [];
    if (!data) { errors.push("No data returned"); return errors; }
    if (!data.hasPbjs) {
      errors.push("window.pbjs not present; cannot inspect consentManagement config.");
      return errors;
    }
    if (!data.hasGetConfig) {
      errors.push("pbjs.getConfig is not available; cannot read consentManagement configuration.");
      return errors;
    }
    if (data.error) {
      errors.push("Error while reading pbjs.getConfig(): " + data.error);
      return errors;
    }
    const cm = data.consentManagement;
    if (!cm || typeof cm !== "object" || Object.keys(cm).length === 0) {
      errors.push("Prebid consentManagement config not present in pbjs.getConfig().");
      return errors;
    }
    const namespaces = { gdpr: data.gdpr, usp: data.usp, gpp: data.gpp };
    const configured = [];
    const missingCmpApi = [];
    for (const [ns, cfg] of Object.entries(namespaces)) {
      if (!cfg) continue;
      configured.push(ns);
      const cmpApi = (typeof cfg === "object") ? cfg.cmpApi : null;
      if (!cmpApi) missingCmpApi.push(ns);
    }
    if (!configured.length) {
      errors.push("consentManagement is present but none of the expected namespaces (gdpr / usp / gpp) are configured.");
      return errors;
    }
    if (missingCmpApi.length) {
      errors.push("cmpApi is not configured for: " + missingCmpApi.map(ns => "consentManagement." + ns + ".cmpApi").join(", "));
    }
    return errors;
  },

  "pbjs_identity_modules": (data) => {
    // In extension context there's no geo config to compare against.
    // We PASS if userIds are found, INFO if empty.
    const errors = [];
    if (!data) { errors.push("No data returned"); return errors; }
    const userIds = data.userIds || data.actual_identity_modules || [];
    if (!userIds.length) {
      errors.push("No identity modules found in pbjs.getConfig().userSync.userIds");
    }
    return errors;
  },

  "pbjs_price_floors_display": (data) => {
    const errors = [];
    const floors = (data && data.prebid_floors_display) ? data.prebid_floors_display : (data || {});
    for (const e of (floors.errors || [])) errors.push("Extraction warning: " + e);

    const hasStore = Boolean(floors.has_display_store);
    const displayBidReq = parseInt(floors.display_bidrequested_events || 0, 10);

    if (!hasStore || displayBidReq === 0) {
      // SKIPPED in Python — we surface as INFO in extension
      errors.push("No display Prebid activity observed (window.__pbjsBidEventsDisplay missing or no bidRequested).");
      return errors;
    }

    const modulePresent = Boolean(floors.module_present);
    const hasCfg = Boolean(floors.has_floors_config);
    const enabled = Boolean(floors.enabled);
    const rulesCount = parseInt(floors.rules_count || 0, 10);
    const displayRules = parseInt(floors.display_applicable_rules_count || 0, 10);

    if (!modulePresent && !hasCfg) errors.push("Display floors: priceFloors module not installed and no floors config present");
    if (hasCfg && !enabled) errors.push("Display floors: floors config present but disabled (floors.enabled === false)");
    if (hasCfg && enabled && rulesCount === 0) errors.push("Display floors: no floor rules configured (floors.data.values / floors.values empty or missing)");
    else if (hasCfg && enabled && displayRules === 0) errors.push("Display floors: no banner/display-applicable floor rules found");

    return errors;
  },

  "pbjs_price_floors_video": (data) => {
    const errors = [];
    const floors = (data && data.prebid_floors_video) ? data.prebid_floors_video : (data || {});
    for (const e of (floors.errors || [])) errors.push("Extraction warning: " + e);

    const hasStore = Boolean(floors.has_video_store);
    const bidReq = parseInt(floors.video_bidrequested_events || 0, 10);

    if (!hasStore || bidReq === 0) {
      errors.push("No video Prebid activity observed (window.__pbjsBidEventsVideo missing or no bidRequested).");
      return errors;
    }

    const modulePresent = Boolean(floors.module_present);
    const hasCfg = Boolean(floors.has_floors_config);
    const enabled = Boolean(floors.enabled);
    const rulesCount = parseInt(floors.rules_count || 0, 10);
    const videoRules = parseInt(floors.video_applicable_rules_count || 0, 10);

    if (!modulePresent && !hasCfg) errors.push("Video floors: priceFloors module not installed and no floors config present");
    if (hasCfg && !enabled) errors.push("Video floors: floors config present but disabled (floors.enabled === false)");
    if (hasCfg && enabled && rulesCount === 0) errors.push("Video floors: no floor rules configured");
    else if (hasCfg && enabled && videoRules === 0) errors.push("Video floors: no video-applicable floor rules found");

    return errors;
  },

  "pbjs_pubcid_presence_display": (data) => {
    const errors = [];
    if (!data || !data.hasPbjs) {
      errors.push("window.pbjs not found; cannot validate pubcid in display bids.");
      return errors;
    }
    if (parseInt(data.bidRequestedEvents || 0, 10) === 0) {
      errors.push("No DISPLAY bidRequested events captured; cannot confirm pubcid for display bidders.");
      return errors;
    }
    const missing = data.biddersMissingPubcid || [];
    if (missing.length) {
      errors.push("pubcid missing for DISPLAY bidders: " + missing.join(", "));
    }
    return errors;
  },

  "pbjs_pubcid_presence_video": (data) => {
    const errors = [];
    if (!data || !data.hasPbjs) {
      errors.push("window.pbjs not found; cannot validate pubcid in video bids.");
      return errors;
    }
    if (parseInt(data.heroBidsConsidered || 0, 10) === 0) {
      errors.push("No VIDEO hero_player bids captured; cannot confirm pubcid for video bidders.");
      return errors;
    }
    const missing = data.biddersMissingPubcid || [];
    if (missing.length) {
      errors.push("pubcid missing for VIDEO bidders: " + missing.join(", "));
    }
    return errors;
  },

  "pbjs_timeout_config": (data) => {
    const errors = [];
    const timeout_data = (data && data.prebid_timeout_config) ? data.prebid_timeout_config : (data || {});
    for (const e of (timeout_data.errors || [])) errors.push("Extraction error: " + e);
    const timeoutRaw = timeout_data.timeout;
    if (timeoutRaw == null) {
      errors.push("No Prebid timeout configured (timeout / bidderTimeout / auctionTimeout missing)");
    } else {
      const val = parseInt(timeoutRaw, 10);
      if (isNaN(val)) {
        errors.push("Invalid timeout format: " + timeoutRaw);
      } else if (val < 100) {
        errors.push("Timeout too low: " + val + "ms (minimum 100ms recommended)");
      } else if (val > 5000) {
        errors.push("Timeout too high: " + val + "ms (maximum 5000ms recommended)");
      }
    }
    return errors;
  },

  "pbjs_warnings": (data) => {
    // The warnings test uses a special init IIFE. The runner collects
    // window.__prebidWarningLogs after a short delay. Since we can't wait
    // 5 seconds from popup.js in a simple way, we check what was hooked.
    const errors = [];
    if (!data) return errors;
    const init = data.init || data;
    if (init && init.hasPbjs === false) {
      errors.push("pbjs not present on page; cannot run warnings test.");
      return errors;
    }
    // If matchedByBidder is present (raw data from window), check it
    const matched = data.matchedByBidder || {};
    const adslots = data.invalidBidAdslotsByBidder || {};
    if (Object.keys(matched).length > 0) {
      const parts = Object.keys(matched).sort().map(bidder => {
        const slots = adslots[bidder] || [];
        return slots.length ? (bidder + " -> " + slots.join(", ")) : bidder;
      });
      errors.push("Invalid bids: " + parts.join(" | "));
    }
    return errors;
  },

  "pbjs_hero_player_placement": (data) => {
    const errors = [];
    if (!data || !data.hasPbjs) {
      errors.push("window.pbjs not present; cannot inspect hero_player bids.");
      return errors;
    }
    if (parseInt(data.eventsLen || 0, 10) === 0) {
      errors.push((data.source || "Event store") + " is empty; no Prebid events captured.");
      return errors;
    }
    if (parseInt(data.heroBidsTotal || 0, 10) === 0) {
      errors.push("No bids found for adUnitCode 'hero_player' in bidRequested events.");
      return errors;
    }
    const perBidder = data.perBidder || {};
    const lines = [];
    let anyFail = false;
    for (const bidder of Object.keys(perBidder).sort()) {
      const info = perBidder[bidder] || {};
      const missP = parseInt(info.missingPlacement || 0, 10);
      const invP = parseInt(info.invalidPlacement || 0, 10);
      const missC = parseInt(info.missingPlcmt || 0, 10);
      const invC = parseInt(info.invalidPlcmt || 0, 10);
      const mismatch = parseInt(info.mismatch || 0, 10);
      if (missP === 0 && invP === 0 && missC === 0 && invC === 0 && mismatch === 0) continue;
      anyFail = true;
      const reasons = [];
      if (missP) reasons.push("missing placement=" + missP);
      if (invP) reasons.push("invalid placement=" + invP);
      if (missC) reasons.push("missing plcmt=" + missC);
      if (invC) reasons.push("invalid plcmt=" + invC);
      if (mismatch) reasons.push("placement/plcmt mismatch=" + mismatch);
      lines.push(bidder + ": FAIL (" + reasons.join("; ") + ")");
    }
    if (anyFail) {
      errors.push("Hero player placement failures:\n" + lines.join("\n"));
    }
    return errors;
  },

  "pbjs_mantis_signals_bid": (data) => {
    const errors = [];
    if (!data || !data.hasPbjs) {
      errors.push("pbjs not present");
      return errors;
    }
    if (parseInt(data.totalRequests || 0, 10) === 0) {
      errors.push("No bidder requests found");
      return errors;
    }
    const perBidder = data.perBidder || {};
    const bidders = Object.keys(perBidder);
    if (!bidders.length) {
      errors.push("No bidders found in requests");
      return errors;
    }

    const MANTIS_ENTRY_RE = /^[A-Za-z0-9][A-Za-z0-9_-]*-(GREEN|AMBER|RED)$/;
    const MANTIS_CTX_ENTRY_RE = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;

    const validateArray = (pathName, obs) => {
      const errs = [];
      if (!obs || !obs.seen) { errs.push(pathName + ": missing"); return errs; }
      if (obs.type !== "array") { errs.push(pathName + ": wrong type (expected array, got " + obs.type + ")"); return errs; }
      if (parseInt(obs.count || 0, 10) <= 0) { errs.push(pathName + ": empty array"); return errs; }
      return errs;
    };

    let anyFail = false;
    for (const bidder of bidders.sort()) {
      const info = perBidder[bidder] || {};
      if (parseInt(info.requestCount || 0, 10) === 0) continue;
      const paths = info.paths || {};
      const mantisObs = paths["site.ext.data.mantis"] || {};
      const mantisCtxObs = paths["site.ext.data.mantis_context"] || {};

      const failures = [
        ...validateArray("site.ext.data.mantis", mantisObs),
        ...validateArray("site.ext.data.mantis_context", mantisCtxObs),
      ];

      if (!failures.length) {
        // Pattern validation
        const mantisVals = (mantisObs.sample || []).map(String).filter(Boolean);
        const ctxVals = (mantisCtxObs.sample || []).map(String).filter(Boolean);
        const badMantis = mantisVals.filter(v => !MANTIS_ENTRY_RE.test(v));
        const badCtx = ctxVals.filter(v => !MANTIS_CTX_ENTRY_RE.test(v));
        if (badMantis.length) failures.push("site.ext.data.mantis: invalid entries -> " + badMantis.slice(0, 10).join(", "));
        if (badCtx.length) failures.push("site.ext.data.mantis_context: invalid entries -> " + badCtx.slice(0, 10).join(", "));
      }

      if (failures.length) {
        anyFail = true;
        errors.push(bidder + ": " + failures.join("; "));
      }
    }
    if (!anyFail && errors.length === 0) return [];
    return errors;
  },

  "pbjs_permutive_signals_bid": (data) => {
    const errors = [];
    if (!data || !data.hasPbjs) { errors.push("pbjs not present"); return errors; }
    if (parseInt(data.totalRequests || 0, 10) === 0) { errors.push("No bidder requests found"); return errors; }

    const REQUIRED_BIDDERS = ["ix", "rubicon", "msft", "pubmatic"];
    const perBidder = data.perBidder || {};

    const hasAnyRequired = REQUIRED_BIDDERS.some(b => {
      const info = perBidder[b];
      return info && parseInt(info.requestCount || 0, 10) > 0;
    });
    if (!hasAnyRequired) {
      errors.push("No requests for required bidders: " + REQUIRED_BIDDERS.join(", "));
      return errors;
    }

    const sampleHasToken = (sample, token) => {
      if (!sample || !sample.length) return false;
      const t = token.toLowerCase();
      return sample.some(raw => String(raw).toLowerCase().includes(t));
    };

    for (const bidder of REQUIRED_BIDDERS) {
      const info = perBidder[bidder];
      if (!info || parseInt(info.requestCount || 0, 10) === 0) continue;
      const paths = info.paths || {};
      const failures = [];

      const pStd = paths["user.ext.data.p_standard"] || {};
      const perm = paths["user.ext.data.permutive"] || {};
      const kw = paths["user.keywords"] || {};

      if (!pStd.seen) failures.push("user.ext.data.p_standard: missing");
      if (!perm.seen) failures.push("user.ext.data.permutive: missing");
      if (!kw.seen) {
        failures.push("user.keywords: missing");
      } else {
        const sample = kw.sample || [];
        const tokens = ["p_standard=", "p_standard_aud=", "permutive="];
        const missingTokens = tokens.filter(t => !sampleHasToken(sample, t));
        if (missingTokens.length) failures.push("user.keywords: missing tokens " + missingTokens.join(", "));
      }

      if (failures.length) errors.push(bidder + ": FAIL (" + failures.join("; ") + ")");
    }

    return errors;
  },

  "gpt_page_type": (data) => {
    const errors = [];
    if (data === null || data === undefined) {
      errors.push("GPT targeting not available (googletag missing or not ready).");
      return errors;
    }
    const vals = Array.isArray(data) ? data : (data.pageType || []);
    if (!vals.length) {
      errors.push("pageType targeting key missing or empty.");
      return errors;
    }
    const nonEmpty = vals.map(v => String(v).trim()).filter(v => v);
    if (!nonEmpty.length) {
      errors.push("pageType targeting contains only empty values.");
    }
    return errors;
  },

  "gpt_mantis_context": (data) => {
    const errors = [];
    if (!data) {
      errors.push("GPT targeting not available.");
      return errors;
    }
    if (!data.present) {
      errors.push("mantis_context key not found in GPT targeting.");
      return errors;
    }
    const vals = (data.values || []).map(v => String(v).trim()).filter(v => v);
    if (!vals.length) {
      errors.push("mantis_context targeting present but contains only empty values.");
    }
    return errors;
  },

  "env_is_mobile_or_tablet": (data) => {
    const errors = [];
    const cookieValue = (data && typeof data === "object") ? data.cookie_value : data;
    if (cookieValue === null || cookieValue === undefined) {
      errors.push("Cookie 'is_mobile_or_tablet' is not set.");
    }
    // We can't know the expected value without viewport config,
    // but we can check the cookie exists and has a valid value.
    else if (cookieValue !== "true" && cookieValue !== "false") {
      errors.push("Cookie 'is_mobile_or_tablet' has unexpected value: '" + cookieValue + "' (expected 'true' or 'false').");
    }
    return errors;
  },

};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function truncateUrl(url, maxLen = 60) {
  if (!url) return "";
  if (url.length <= maxLen) return url;
  return url.slice(0, maxLen - 3) + "...";
}

// All JS file paths to inject (relative to extension root)
function getTestFilePaths() {
  return ALL_TEST_STEMS.map(stem => "js/" + stem + ".js");
}

// ---------------------------------------------------------------------------
// Runner function injected into the tab
// Calls each window.__adTests["name"]() and returns raw results.
// The warnings test (pbjs_warnings_init) needs extra handling since it's
// an IIFE, not an arrow function stored in __adTests.
// ---------------------------------------------------------------------------
function buildRunnerFunc() {
  return function () {
    const results = {};
    const tests = window.__adTests || {};

    for (const [name, fn] of Object.entries(tests)) {
      try {
        if (typeof fn === "function") {
          results[name] = fn();
        } else {
          results[name] = { _error: "not a function" };
        }
      } catch (e) {
        results[name] = { _error: String(e) };
      }
    }

    // warnings: collect whatever was captured from the init IIFE
    // The init script is an IIFE so it runs on injection; grab the log store.
    try {
      const logs = Array.isArray(window.__prebidWarningLogs)
        ? window.__prebidWarningLogs
        : [];

      const FAIL_PATTERN = "invalid bid sent to bidder";

      const failing = logs.filter(m => {
        const t = (m.text || "").toLowerCase();
        return t.includes(FAIL_PATTERN);
      }).slice(0, 50);

      const byBidder = {};
      const adslotsByBidder = {};

      const extractBidder = (line) => {
        try {
          const ll = line.toLowerCase();
          const idx = ll.indexOf(FAIL_PATTERN);
          if (idx === -1) return "unknown";
          const after = (line.slice(idx + FAIL_PATTERN.length) || "").trim();
          const tok = after.split(":")[0].split(" ")[0].trim();
          return tok.replace(/[^a-zA-Z0-9_-]/g, "") || "unknown";
        } catch (e) { return "unknown"; }
      };

      const extractAdslots = (line) => {
        const slots = [];
        const adslotRe = /"adslot"\s*:\s*"([^"]+)"/gi;
        const gpidRe = /"gpid"\s*:\s*"([^"]+)"/gi;
        let m;
        while ((m = adslotRe.exec(line)) !== null) {
          const s = m[1].trim();
          if (s && !slots.includes(s)) slots.push(s);
        }
        if (!slots.length) {
          while ((m = gpidRe.exec(line)) !== null) {
            const s = m[1].trim();
            if (s && !slots.includes(s)) slots.push(s);
          }
        }
        return slots;
      };

      for (const m of failing) {
        const line = m.text || "";
        const bidder = extractBidder(line);
        byBidder[bidder] = (byBidder[bidder] || 0) + 1;
        const slots = extractAdslots(line);
        if (slots.length) {
          adslotsByBidder[bidder] = adslotsByBidder[bidder] || [];
          for (const s of slots) {
            if (!adslotsByBidder[bidder].includes(s)) adslotsByBidder[bidder].push(s);
          }
        }
      }

      results["pbjs_warnings"] = {
        prebidMessagesTotal: logs.length,
        matchedCount: failing.length,
        matchedByBidder: byBidder,
        invalidBidAdslotsByBidder: adslotsByBidder,
        init: { hasPbjs: !!window.pbjs },
      };
    } catch (e) {
      results["pbjs_warnings"] = { _error: String(e) };
    }

    return results;
  };
}

// ---------------------------------------------------------------------------
// UI rendering
// ---------------------------------------------------------------------------

function renderResults(allData) {
  const resultsEl = document.getElementById("results");
  const summaryEl = document.getElementById("summary");
  resultsEl.innerHTML = "";
  resultsEl.style.display = "block";

  let totalPass = 0;
  let totalFail = 0;
  let totalSkip = 0;

  for (const [category, testNames] of Object.entries(CATEGORIES)) {
    const catHeader = document.createElement("div");
    catHeader.className = "category-header";
    catHeader.textContent = category;
    resultsEl.appendChild(catHeader);

    for (const name of testNames) {
      const data = allData[name];
      const row = document.createElement("div");
      row.className = "test-row";

      const label = document.createElement("span");
      label.className = "test-name";
      label.textContent = name.replace(/_/g, " ");

      const badge = document.createElement("span");
      badge.className = "badge";

      const detail = document.createElement("div");
      detail.className = "test-detail";

      if (data === undefined || data === null) {
        badge.className += " badge-skip";
        badge.textContent = "NO DATA";
        totalSkip++;
      } else if (data && data._error) {
        badge.className += " badge-fail";
        badge.textContent = "ERROR";
        detail.textContent = "JS Error: " + data._error;
        totalFail++;
      } else {
        const validator = VALIDATORS[name];
        if (!validator) {
          // INFO — no validator defined
          badge.className += " badge-info";
          badge.textContent = "INFO";
          try {
            detail.textContent = JSON.stringify(data, null, 2).slice(0, 400);
          } catch (_) {
            detail.textContent = String(data);
          }
        } else {
          const errors = validator(data);
          if (errors.length === 0) {
            badge.className += " badge-pass";
            badge.textContent = "PASS";
            totalPass++;
          } else {
            badge.className += " badge-fail";
            badge.textContent = "FAIL";
            detail.textContent = errors.join("\n");
            totalFail++;
          }
        }
      }

      const topRow = document.createElement("div");
      topRow.className = "test-top";
      topRow.appendChild(label);
      topRow.appendChild(badge);

      row.appendChild(topRow);
      if (detail.textContent) row.appendChild(detail);
      resultsEl.appendChild(row);
    }
  }

  summaryEl.textContent = `${totalPass} passed / ${totalFail} failed / ${totalSkip} no data`;
  summaryEl.className = "summary " + (totalFail > 0 ? "summary-fail" : "summary-pass");
  summaryEl.style.display = "block";
}

function showError(msg) {
  const errEl = document.getElementById("error-msg");
  errEl.textContent = msg;
  errEl.style.display = "block";
}

function setLoading(loading) {
  const btn = document.getElementById("run-btn");
  const spinner = document.getElementById("spinner");
  btn.disabled = loading;
  btn.textContent = loading ? "Running..." : "Run Tests";
  spinner.style.display = loading ? "inline-block" : "none";
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  const urlEl = document.getElementById("tab-url");
  const runBtn = document.getElementById("run-btn");

  // Get active tab
  let activeTab = null;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    activeTab = tab;
    urlEl.textContent = truncateUrl(tab.url, 70);
    urlEl.title = tab.url;
  } catch (e) {
    showError("Could not get active tab: " + e.message);
    return;
  }

  runBtn.addEventListener("click", async () => {
    document.getElementById("results").style.display = "none";
    document.getElementById("results").innerHTML = "";
    document.getElementById("summary").style.display = "none";
    document.getElementById("error-msg").style.display = "none";

    setLoading(true);

    try {
      // Step 1: inject all test JS files into the tab (MAIN world)
      const filePaths = getTestFilePaths();

      await chrome.scripting.executeScript({
        target: { tabId: activeTab.id },
        files: filePaths,
        world: "MAIN",
      });

      // Step 2: wait briefly for the warnings IIFE to settle, then run all tests
      await new Promise(resolve => setTimeout(resolve, 1200));

      // Step 3: execute runner function to collect results
      const [injectionResult] = await chrome.scripting.executeScript({
        target: { tabId: activeTab.id },
        func: buildRunnerFunc(),
        world: "MAIN",
      });

      const allData = injectionResult && injectionResult.result ? injectionResult.result : {};

      renderResults(allData);
    } catch (e) {
      showError("Injection failed: " + (e.message || String(e)));
    } finally {
      setLoading(false);
    }
  });
});
