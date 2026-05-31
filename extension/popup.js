"use strict";

// ---------------------------------------------------------------------------
// Category map
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
    "gpt_mantis",
    "gpt_mantis_context",
    "gpt_permutive_composite",
    "gpt_article_id",
    "gpt_category1",
    "gpt_category2",
    "gpt_autorefresh",
    "gpt_cmp_active",
    "gpt_commercial",
    "gpt_consent_tcf",
    "gpt_content_sources",
    "gpt_gam_bid_keys",
    "gpt_gdpr_key",
    "gpt_liveblog",
    "gpt_longread",
    "gpt_referrer",
    "gpt_reg_gate",
    "gpt_testgroup",
    "gpt_topictags",
    "gpt_anonymised_key",
    "gpt_untested_keys",
  ],
  "LAYOUT": [
    "layout_ad_sequence",
  ],
  "ENVIRONMENT": [
    "env_is_mobile_or_tablet",
  ],
};

// ---------------------------------------------------------------------------
// VALIDATORS
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
    const errors = [];
    if (!data || !data.hasPbjs) {
      errors.push("window.pbjs not present; cannot run display bidder presence test.");
      return errors;
    }
    const bidRequested = parseInt(data.bidRequestedEvents || 0, 10);
    if (bidRequested === 0) {
      errors.push("No DISPLAY bidRequested events captured. Prebid may not have fired yet.");
    }
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
    if (totalBidResponses === 0 && bidRequestedCount === 0) {
      errors.push("No bid responses recorded and no bidRequested events seen.");
    }
    return errors;
  },

  "pbjs_adunit_configuration": (data) => {
    const errors = [];
    const adUnitData = (data && data.prebid_ad_units) ? data.prebid_ad_units : (data || {});
    for (const e of (adUnitData.errors || [])) errors.push("Extraction error: " + e);
    const adUnits = adUnitData.ad_units || [];
    if (!adUnits.length) { errors.push("No Prebid ad units configured (pbjs.adUnits is empty)"); return errors; }
    const missingCode = [];
    const missingBidders = [];
    adUnits.forEach((unit, idx) => {
      if (!unit.code) missingCode.push(idx);
      if (!unit.bidders || !unit.bidders.length) missingBidders.push(unit.code || "index_" + idx);
    });
    if (missingCode.length) errors.push("Ad units missing code at indices: " + missingCode.join(", "));
    if (missingBidders.length) errors.push("Ad units with no bidders: " + missingBidders.join(", "));
    return errors;
  },

  "pbjs_consent_integration": (data) => {
    const errors = [];
    if (!data) { errors.push("No data returned"); return errors; }
    if (!data.hasPbjs) { errors.push("window.pbjs not present"); return errors; }
    if (!data.hasGetConfig) { errors.push("pbjs.getConfig not available"); return errors; }
    if (data.error) { errors.push("Error reading pbjs.getConfig(): " + data.error); return errors; }
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
      if (typeof cfg === "object" && !cfg.cmpApi) missingCmpApi.push(ns);
    }
    if (!configured.length) {
      errors.push("consentManagement present but no gdpr/usp/gpp namespaces configured.");
      return errors;
    }
    if (missingCmpApi.length) errors.push("cmpApi not configured for: " + missingCmpApi.join(", "));
    return errors;
  },

  "pbjs_identity_modules": (data) => {
    const errors = [];
    if (!data) { errors.push("No data returned"); return errors; }
    const userIds = data.userIds || data.actual_identity_modules || [];
    if (!userIds.length) errors.push("No identity modules found in pbjs.getConfig().userSync.userIds");
    return errors;
  },

  "pbjs_price_floors_display": (data) => {
    const errors = [];
    const floors = (data && data.prebid_floors_display) ? data.prebid_floors_display : (data || {});
    for (const e of (floors.errors || [])) errors.push("Extraction warning: " + e);
    const hasStore = Boolean(floors.has_display_store);
    const displayBidReq = parseInt(floors.display_bidrequested_events || 0, 10);
    if (!hasStore || displayBidReq === 0) {
      errors.push("No display Prebid activity observed.");
      return errors;
    }
    const modulePresent = Boolean(floors.module_present);
    const hasCfg = Boolean(floors.has_floors_config);
    const enabled = Boolean(floors.enabled);
    const rulesCount = parseInt(floors.rules_count || 0, 10);
    const displayRules = parseInt(floors.display_applicable_rules_count || 0, 10);
    if (!modulePresent && !hasCfg) errors.push("Display floors: priceFloors module not installed and no floors config present");
    if (hasCfg && !enabled) errors.push("Display floors: floors config present but disabled");
    if (hasCfg && enabled && rulesCount === 0) errors.push("Display floors: no floor rules configured");
    else if (hasCfg && enabled && displayRules === 0) errors.push("Display floors: no display-applicable floor rules found");
    return errors;
  },

  "pbjs_price_floors_video": (data) => {
    const errors = [];
    const floors = (data && data.prebid_floors_video) ? data.prebid_floors_video : (data || {});
    for (const e of (floors.errors || [])) errors.push("Extraction warning: " + e);
    const hasStore = Boolean(floors.has_video_store);
    const bidReq = parseInt(floors.video_bidrequested_events || 0, 10);
    if (!hasStore || bidReq === 0) {
      errors.push("No video Prebid activity observed.");
      return errors;
    }
    const modulePresent = Boolean(floors.module_present);
    const hasCfg = Boolean(floors.has_floors_config);
    const enabled = Boolean(floors.enabled);
    const rulesCount = parseInt(floors.rules_count || 0, 10);
    const videoRules = parseInt(floors.video_applicable_rules_count || 0, 10);
    if (!modulePresent && !hasCfg) errors.push("Video floors: priceFloors module not installed and no floors config present");
    if (hasCfg && !enabled) errors.push("Video floors: floors config present but disabled");
    if (hasCfg && enabled && rulesCount === 0) errors.push("Video floors: no floor rules configured");
    else if (hasCfg && enabled && videoRules === 0) errors.push("Video floors: no video-applicable floor rules found");
    return errors;
  },

  "pbjs_pubcid_presence_display": (data) => {
    const errors = [];
    if (!data || !data.hasPbjs) { errors.push("window.pbjs not found"); return errors; }
    if (parseInt(data.bidRequestedEvents || 0, 10) === 0) {
      errors.push("No DISPLAY bidRequested events captured; cannot confirm pubcid.");
      return errors;
    }
    const missing = data.biddersMissingPubcid || [];
    if (missing.length) errors.push("pubcid missing for DISPLAY bidders: " + missing.join(", "));
    return errors;
  },

  "pbjs_pubcid_presence_video": (data) => {
    const errors = [];
    if (!data || !data.hasPbjs) { errors.push("window.pbjs not found"); return errors; }
    if (parseInt(data.heroBidsConsidered || 0, 10) === 0) {
      errors.push("No VIDEO hero_player bids captured; cannot confirm pubcid.");
      return errors;
    }
    const missing = data.biddersMissingPubcid || [];
    if (missing.length) errors.push("pubcid missing for VIDEO bidders: " + missing.join(", "));
    return errors;
  },

  "pbjs_timeout_config": (data) => {
    const errors = [];
    const d = (data && data.prebid_timeout_config) ? data.prebid_timeout_config : (data || {});
    for (const e of (d.errors || [])) errors.push("Extraction error: " + e);
    const val = d.timeout == null ? null : parseInt(d.timeout, 10);
    if (val == null) errors.push("No Prebid timeout configured");
    else if (isNaN(val)) errors.push("Invalid timeout format: " + d.timeout);
    else if (val < 100) errors.push("Timeout too low: " + val + "ms (min 100ms)");
    else if (val > 5000) errors.push("Timeout too high: " + val + "ms (max 5000ms)");
    return errors;
  },

  "pbjs_warnings": (data) => {
    const errors = [];
    if (!data) return errors;
    if (data.init && data.init.hasPbjs === false) {
      errors.push("pbjs not present; cannot run warnings test.");
      return errors;
    }
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
    if (!data || !data.hasPbjs) { errors.push("window.pbjs not present"); return errors; }
    if (parseInt(data.eventsLen || 0, 10) === 0) {
      errors.push("Event store empty; no Prebid events captured.");
      return errors;
    }
    if (parseInt(data.heroBidsTotal || 0, 10) === 0) {
      errors.push("No bids found for adUnitCode 'hero_player'.");
      return errors;
    }
    const perBidder = data.perBidder || {};
    const lines = [];
    for (const bidder of Object.keys(perBidder).sort()) {
      const info = perBidder[bidder] || {};
      const missP = parseInt(info.missingPlacement || 0, 10);
      const invP  = parseInt(info.invalidPlacement  || 0, 10);
      const missC = parseInt(info.missingPlcmt      || 0, 10);
      const invC  = parseInt(info.invalidPlcmt      || 0, 10);
      const mismatch = parseInt(info.mismatch       || 0, 10);
      if (missP === 0 && invP === 0 && missC === 0 && invC === 0 && mismatch === 0) continue;
      const reasons = [];
      if (missP)    reasons.push("missing placement=" + missP);
      if (invP)     reasons.push("invalid placement=" + invP);
      if (missC)    reasons.push("missing plcmt=" + missC);
      if (invC)     reasons.push("invalid plcmt=" + invC);
      if (mismatch) reasons.push("placement/plcmt mismatch=" + mismatch);
      lines.push(bidder + ": " + reasons.join("; "));
    }
    if (lines.length) errors.push("Hero player placement failures:\n" + lines.join("\n"));
    return errors;
  },

  "pbjs_mantis_signals_bid": (data) => {
    const errors = [];
    if (!data || !data.hasPbjs) { errors.push("pbjs not present"); return errors; }
    if (parseInt(data.totalRequests || 0, 10) === 0) { errors.push("No bidder requests found"); return errors; }
    const perBidder = data.perBidder || {};
    const bidders = Object.keys(perBidder);
    if (!bidders.length) { errors.push("No bidders found in requests"); return errors; }
    const MANTIS_RE     = /^[A-Za-z0-9][A-Za-z0-9_-]*-(GREEN|AMBER|RED)$/;
    const MANTIS_CTX_RE = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
    const check = (pathName, obs, re) => {
      if (!obs || !obs.seen) return [pathName + ": missing"];
      if (obs.type !== "array") return [pathName + ": wrong type (got " + obs.type + ")"];
      if (parseInt(obs.count || 0, 10) <= 0) return [pathName + ": empty array"];
      const bad = (obs.sample || []).map(String).filter(v => !re.test(v));
      return bad.length ? [pathName + ": invalid entries -> " + bad.slice(0, 5).join(", ")] : [];
    };
    for (const bidder of bidders.sort()) {
      const info = perBidder[bidder] || {};
      if (parseInt(info.requestCount || 0, 10) === 0) continue;
      const paths = info.paths || {};
      const failures = [
        ...check("site.ext.data.mantis",         paths["site.ext.data.mantis"]         || {}, MANTIS_RE),
        ...check("site.ext.data.mantis_context",  paths["site.ext.data.mantis_context"] || {}, MANTIS_CTX_RE),
      ];
      if (failures.length) errors.push(bidder + ": " + failures.join("; "));
    }
    return errors;
  },

  "pbjs_permutive_signals_bid": (data) => {
    const errors = [];
    if (!data || !data.hasPbjs) { errors.push("pbjs not present"); return errors; }
    if (parseInt(data.totalRequests || 0, 10) === 0) { errors.push("No bidder requests found"); return errors; }
    const REQUIRED_BIDDERS = ["ix", "rubicon", "msft", "pubmatic"];
    const perBidder = data.perBidder || {};
    const hasAnyRequired = REQUIRED_BIDDERS.some(b => parseInt((perBidder[b] || {}).requestCount || 0, 10) > 0);
    if (!hasAnyRequired) { errors.push("No requests for required bidders: " + REQUIRED_BIDDERS.join(", ")); return errors; }
    const sampleHasToken = (sample, token) => (sample || []).some(raw => String(raw).toLowerCase().includes(token.toLowerCase()));
    for (const bidder of REQUIRED_BIDDERS) {
      const info = perBidder[bidder];
      if (!info || parseInt(info.requestCount || 0, 10) === 0) continue;
      const paths = info.paths || {};
      const failures = [];
      if (!paths["user.ext.data.p_standard"]?.seen) failures.push("user.ext.data.p_standard: missing");
      if (!paths["user.ext.data.permutive"]?.seen)  failures.push("user.ext.data.permutive: missing");
      const kw = paths["user.keywords"] || {};
      if (!kw.seen) {
        failures.push("user.keywords: missing");
      } else {
        const tokens = ["p_standard=", "p_standard_aud=", "permutive="];
        const missing = tokens.filter(t => !sampleHasToken(kw.sample, t));
        if (missing.length) failures.push("user.keywords: missing tokens " + missing.join(", "));
      }
      if (failures.length) errors.push(bidder + ": FAIL (" + failures.join("; ") + ")");
    }
    return errors;
  },

  "gpt_page_type": (data) => {
    const errors = [];
    if (data === null || data === undefined) { errors.push("GPT targeting not available."); return errors; }
    const vals = Array.isArray(data) ? data : (data.pageType || []);
    if (!vals.length) { errors.push("pageType targeting key missing or empty."); return errors; }
    if (!vals.map(v => String(v).trim()).filter(v => v).length) errors.push("pageType contains only empty values.");
    return errors;
  },

  "gpt_mantis_context": (data) => {
    const errors = [];
    if (!data) { errors.push("GPT targeting not available."); return errors; }
    if (!data.present) { errors.push("mantis_context key not found in GPT targeting."); return errors; }
    if (!(data.values || []).map(v => String(v).trim()).filter(v => v).length) {
      errors.push("mantis_context present but contains only empty values.");
    }
    return errors;
  },

  "env_is_mobile_or_tablet": (data) => {
    const errors = [];
    const val = (data && typeof data === "object") ? data.cookie_value : data;
    if (val === null || val === undefined) errors.push("Cookie 'is_mobile_or_tablet' is not set.");
    else if (val !== "true" && val !== "false") errors.push("Cookie 'is_mobile_or_tablet' has unexpected value: '" + val + "'");
    return errors;
  },

  "gpt_anonymised_key": (data) => {
    if (!data || !data.hasGpt) return [];
    if (data.error) return ["Error reading anonymised targeting: " + data.error];
    if (!data.keyUsed || !(data.values || []).length)
      return ["No anonymised targeting found (keys tried: AnonymisedSignalLift, anonymised)."];
    return [];
  },

  "gpt_article_id": (data) => {
    if (!data) return [];
    const pageType = ((data.pageType || [])[0] || "").toLowerCase().trim();
    if (pageType === "index" || pageType === "homepage") return [];
    const CANDIDATE_KEYS = ["article", "articleid", "article_id", "content_id"];
    const normalized = {};
    for (const [k, v] of Object.entries(data)) normalized[k.toLowerCase()] = (v || []).map(String);
    let foundValid = false;
    const emptyKeys = [];
    for (const cand of CANDIDATE_KEYS) {
      if (!(cand in normalized)) continue;
      const good = normalized[cand].filter(v => v && !["null","none","undefined"].includes(v.toLowerCase()));
      if (good.length) { foundValid = true; break; }
      emptyKeys.push(cand);
    }
    if (!foundValid) return ["No valid article ID targeting found. Empty/invalid: " + (emptyKeys.join(", ") || "none of the candidate keys present")];
    return [];
  },

  "gpt_autorefresh": (data) => {
    const vals = ((data || {}).autorefresh || []).map(v => String(v).trim());
    if (!vals.length) return [];
    const bad = vals.filter(v => !["yes","no"].includes(v.toLowerCase()));
    return bad.length ? ["Invalid autorefresh values (expected yes/no): " + bad.join(", ")] : [];
  },

  "gpt_category1": (data) => {
    if (!data) return [];
    const pageType = ((data.pageType || [])[0] || "").toLowerCase().trim();
    if (pageType === "index" || pageType === "homepage") return [];
    const vals = (data.category1 || []).map(v => String(v).trim()).filter(v => v);
    return vals.length ? [] : ["category1 targeting missing or empty on article-like page."];
  },

  "gpt_category2": (data) => {
    if (!data) return [];
    const pageType = ((data.pageType || [])[0] || "").toLowerCase().trim();
    if (pageType === "index" || pageType === "homepage") return [];
    const cat1 = (data.category1 || []).map(v => String(v).trim()).filter(v => v);
    const cat2 = (data.category2 || []).map(v => String(v).trim()).filter(v => v);
    if (!cat2.length && cat1.length) return [];
    return cat2.length ? [] : ["category2 targeting empty/invalid for article-like page."];
  },

  "gpt_cmp_active": (data) => {
    const vals = ((data || {}).cmpActive || []).map(v => String(v).trim());
    if (!vals.length) return [];
    const bad = vals.filter(v => !["true","false"].includes(v.toLowerCase()));
    return bad.length ? ["Invalid cmpActive values (expected true/false): " + bad.join(", ")] : [];
  },

  "gpt_commercial": (data) => {
    const vals = ((data || {}).commercial || []).map(v => String(v).trim());
    if (!vals.length) return [];
    const bad = vals.filter(v => !["y","n"].includes(v.toLowerCase()));
    return bad.length ? ["Invalid commercial values (expected y/n): " + bad.join(", ")] : [];
  },

  "gpt_consent_tcf": (data) => {
    if (!data || !data.hasGpt) return [];
    if (!data.gdprKey && !data.tcString)
      return ["For UK locale, neither a gdpr GPT targeting key nor euconsent-v2 TCString was found."];
    return [];
  },

  "gpt_content_sources": (data) => {
    const vals = ((data || {}).contentSources || []).map(v => String(v).trim());
    if (!vals.length) return [];
    return vals.filter(v => v).length ? [] : ["contentSources present but all values are empty."];
  },

  "gpt_gam_bid_keys": (data) => {
    if (!data) return [];
    if (data.error) return ["JS error: " + data.error];
    if (!data.hasGpt) return [];
    if (!data.auctionEndCount) return [];
    const errors = [];
    if (!data.hasPrebid) errors.push("No hb_* keys in GAM targeting; Prebid did not enrich GAM.");
    if (!data.hasTam)    errors.push("No amzn* keys in GAM targeting; TAM did not enrich GAM.");
    return errors;
  },

  "gpt_gdpr_key": (data) => {
    if (!data || !data.hasGpt) return [];
    const vals = (data.gdprValues || []).map(v => String(v).trim());
    if (!vals.length) return ["gdpr targeting key missing."];
    const valid = vals.filter(v => v === "0" || v === "1");
    return valid.length ? [] : ["Invalid gdpr value(s) (expected 0 or 1): " + vals.join(", ")];
  },

  "gpt_liveblog": (data) => {
    const vals = ((data || {}).liveblog || []).map(v => String(v).trim());
    if (!vals.length) return [];
    const bad = vals.filter(v => !["y","n"].includes(v.toLowerCase()));
    return bad.length ? ["Invalid liveblog values (expected y/n): " + bad.join(", ")] : [];
  },

  "gpt_longread": (data) => {
    const vals = ((data || {}).longread || []).map(v => String(v).trim());
    if (!vals.length) return [];
    const bad = vals.filter(v => !["y","n"].includes(v.toLowerCase()));
    return bad.length ? ["Invalid longread values (expected y/n): " + bad.join(", ")] : [];
  },

  "gpt_mantis": (data) => {
    const vals = ((data || {}).mantis || []).map(v => String(v).trim());
    if (!vals.length) return [];
    return vals.filter(v => v).length ? [] : ["mantis targeting present but all values empty."];
  },

  "gpt_permutive_composite": (data) => {
    const vals = ((data || {}).permutive || []).map(v => String(v).trim());
    if (!vals.length) return [];
    return vals.filter(v => v).length ? [] : ["permutive targeting present but all values empty."];
  },

  "gpt_referrer": (data) => {
    if (!data || !data.hasGpt) return [];
    const gptRef = (data.gptReferrer || "").trim();
    const docRef = (data.docReferrer || "").trim();
    if (!gptRef || !docRef) return [];
    if (gptRef.includes(docRef) || docRef.includes(gptRef)) return [];
    return ["GPT referrer '" + gptRef + "' does not match document.referrer '" + docRef + "'."];
  },

  "gpt_reg_gate": (data) => {
    const vals = ((data || {}).reg_gate || []).map(v => String(v).trim());
    if (!vals.length) return [];
    return vals.filter(v => v).length ? [] : ["reg_gate targeting present but empty."];
  },

  "gpt_testgroup": (data) => {
    const vals = ((data || {}).testgroup || []).map(v => String(v).trim());
    if (!vals.length) return [];
    return vals.filter(v => v).length ? [] : ["testgroup targeting present but empty."];
  },

  "gpt_topictags": (data) => {
    const vals = ((data || {}).topictags || []).map(v => String(v).trim());
    if (!vals.length) return [];
    return vals.filter(v => v).length ? [] : ["topictags targeting present but all empty."];
  },

  "gpt_untested_keys": (data) => {
    const KNOWN_KEYS = new Set(["pageType","article","articleId","article_id","content_id",
      "category1","category2","commercial","liveblog","longread","reg_gate","testgroup",
      "topictags","mantis","mantis_context","gdpr","autorefresh","cmpActive","contentSources",
      "referrer","permutive","AnonymisedSignalLift"]);
    const keys = (data || {}).keys || [];
    if (!keys.length) return [];
    const untested = keys.filter(k => !KNOWN_KEYS.has(k));
    return untested.length ? ["Unknown GPT keys (not covered by any test): " + untested.sort().join(", ")] : [];
  },

  "layout_ad_sequence": (data) => {
    if (!data) return [];
    if (data.error) return ["JS error: " + data.error];
    if (data.skipped) return [];
    const failures = (data.rows || []).filter(r => (r.status || "").startsWith("FAIL"));
    if (!failures.length) return [];
    return failures.map(r => r.slot + ": " + r.status + (r.reason ? " — " + r.reason : ""));
  },

};

// ---------------------------------------------------------------------------
// Test files to inject (must match background.js)
// ---------------------------------------------------------------------------
const TEST_FILES = [
  "js/pbjs_environment.js",
  "js/pbjs_display_bidder_presence.js",
  "js/pbjs_video_bidder_presence.js",
  "js/pbjs_auction_activity.js",
  "js/pbjs_adunit_configuration.js",
  "js/pbjs_consent_integration.js",
  "js/pbjs_identity_modules.js",
  "js/pbjs_price_floors_display.js",
  "js/pbjs_price_floors_video.js",
  "js/pbjs_pubcid_presence_display.js",
  "js/pbjs_pubcid_presence_video.js",
  "js/pbjs_timeout_config.js",
  "js/pbjs_hero_player_placement.js",
  "js/pbjs_mantis_signals_bid.js",
  "js/pbjs_permutive_signals_bid.js",
  "js/gpt_page_type.js",
  "js/gpt_mantis.js",
  "js/gpt_mantis_context.js",
  "js/gpt_permutive_composite.js",
  "js/gpt_article_id.js",
  "js/gpt_category1.js",
  "js/gpt_category2.js",
  "js/gpt_autorefresh.js",
  "js/gpt_cmp_active.js",
  "js/gpt_commercial.js",
  "js/gpt_consent_tcf.js",
  "js/gpt_content_sources.js",
  "js/gpt_gam_bid_keys.js",
  "js/gpt_gdpr_key.js",
  "js/gpt_liveblog.js",
  "js/gpt_longread.js",
  "js/gpt_referrer.js",
  "js/gpt_reg_gate.js",
  "js/gpt_testgroup.js",
  "js/gpt_topictags.js",
  "js/gpt_anonymised_key.js",
  "js/gpt_untested_keys.js",
  "js/layout_ad_sequence.js",
  "js/env_is_mobile_or_tablet.js",
];

// Self-contained runner (same logic as background.js runAllTests, no closures)
function runAllTests() {
  const results = {};
  const tests = window.__adTests || {};
  for (const [name, fn] of Object.entries(tests)) {
    try { results[name] = (typeof fn === "function") ? fn() : { _error: "not a function" }; }
    catch (e) { results[name] = { _error: String(e) }; }
  }
  try {
    const logs = Array.isArray(window.__prebidWarningLogs) ? window.__prebidWarningLogs : [];
    const FAIL_PATTERN = "invalid bid sent to bidder";
    const failing = logs.filter(m => (m.text || "").toLowerCase().includes(FAIL_PATTERN)).slice(0, 50);
    const byBidder = {}, adslotsByBidder = {};
    for (const msg of failing) {
      const line = msg.text || "";
      const ll = line.toLowerCase();
      const idx = ll.indexOf(FAIL_PATTERN);
      const tok = idx === -1 ? "unknown" : ((line.slice(idx + FAIL_PATTERN.length) || "").trim().split(":")[0].split(" ")[0].trim().replace(/[^a-zA-Z0-9_-]/g, "") || "unknown");
      byBidder[tok] = (byBidder[tok] || 0) + 1;
      const slots = [];
      const re = /"adslot"\s*:\s*"([^"]+)"/gi; let m;
      while ((m = re.exec(line)) !== null) { if (!slots.includes(m[1])) slots.push(m[1]); }
      if (slots.length) { adslotsByBidder[tok] = adslotsByBidder[tok] || []; for (const s of slots) if (!adslotsByBidder[tok].includes(s)) adslotsByBidder[tok].push(s); }
    }
    results["pbjs_warnings"] = { prebidMessagesTotal: logs.length, matchedCount: failing.length, matchedByBidder: byBidder, invalidBidAdslotsByBidder: adslotsByBidder, init: { hasPbjs: !!window.pbjs } };
  } catch (e) { results["pbjs_warnings"] = { _error: String(e) }; }
  return results;
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------
function truncateUrl(url, maxLen = 55) {
  if (!url || url.length <= maxLen) return url || "";
  return url.slice(0, maxLen - 3) + "…";
}

function showState(id) {
  for (const sid of ["state-running", "state-waiting", "state-error"]) {
    document.getElementById(sid).style.display = sid === id ? "flex" : "none";
  }
}

function hideStates() {
  for (const sid of ["state-running", "state-waiting", "state-error"]) {
    document.getElementById(sid).style.display = "none";
  }
}

function renderResults(results, runAt) {
  hideStates();
  const resultsEl = document.getElementById("results");
  const summaryEl = document.getElementById("summary");
  const footerEl  = document.getElementById("footer");
  resultsEl.innerHTML = "";
  resultsEl.style.display = "block";

  let totalPass = 0, totalFail = 0, totalSkip = 0;

  for (const [category, testNames] of Object.entries(CATEGORIES)) {
    const catHeader = document.createElement("div");
    catHeader.className = "category-header";
    catHeader.textContent = category;
    resultsEl.appendChild(catHeader);

    for (const name of testNames) {
      const data = results[name];
      const row  = document.createElement("div");
      row.className = "test-row";

      const label = document.createElement("span");
      label.className = "test-name";
      label.textContent = name.replace(/_/g, " ");

      const badge  = document.createElement("span");
      badge.className = "badge";
      const detail = document.createElement("div");
      detail.className = "test-detail";

      if (data === undefined || data === null) {
        badge.className += " badge-skip";
        badge.textContent = "NO DATA";
        totalSkip++;
      } else if (data._error) {
        badge.className += " badge-fail";
        badge.textContent = "ERROR";
        detail.textContent = data._error;
        totalFail++;
      } else {
        const validator = VALIDATORS[name];
        if (!validator) {
          badge.className += " badge-info";
          badge.textContent = "INFO";
          try { detail.textContent = JSON.stringify(data, null, 2).slice(0, 300); } catch (_) {}
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

  summaryEl.textContent = `${totalPass} passed  /  ${totalFail} failed  /  ${totalSkip} no data`;
  summaryEl.className = "summary " + (totalFail > 0 ? "summary-fail" : "summary-pass");
  summaryEl.style.display = "block";

  if (runAt) {
    document.getElementById("run-at").textContent = "Run at " + runAt;
    footerEl.style.display = "flex";
  }
}

// ---------------------------------------------------------------------------
// Manual re-run (same logic as background.js but triggered from popup)
// ---------------------------------------------------------------------------
async function triggerRerun(tabId) {
  showState("state-running");
  document.getElementById("results").style.display = "none";
  document.getElementById("summary").style.display = "none";
  document.getElementById("footer").style.display = "none";

  const storageKey = `tab_${tabId}`;
  const url = (await chrome.tabs.get(tabId)).url;

  await chrome.storage.local.set({ [storageKey]: { url, status: "running", timestamp: Date.now() } });

  try {
    // Poll for readiness
    await chrome.scripting.executeScript({
      target: { tabId },
      world: "MAIN",
      func: function () {
        return new Promise((resolve) => {
          const start = Date.now();
          const check = () => {
            const hasPbjs   = !!(window.pbjs && Array.isArray(window.pbjs.que));
            const hasEvents = (window.__pbjsBidEventsDisplay || []).length > 0
                           || (window.__pbjsBidEventsVideo   || []).length > 0;
            if (hasPbjs && hasEvents) return resolve("ready");
            if (Date.now() - start > 15000) return resolve("timeout");
            setTimeout(check, 300);
          };
          check();
        });
      },
    });

    await chrome.scripting.executeScript({ target: { tabId }, files: TEST_FILES, world: "MAIN" });
    await new Promise((r) => setTimeout(r, 500));

    const [injection] = await chrome.scripting.executeScript({
      target: { tabId },
      world: "MAIN",
      func: runAllTests,
    });

    const results = injection?.result ?? {};
    const runAt = new Date().toLocaleTimeString();
    await chrome.storage.local.set({ [storageKey]: { url, status: "done", results, timestamp: Date.now(), runAt } });
    renderResults(results, runAt);
  } catch (e) {
    showState("state-error");
    document.getElementById("state-error").textContent = "Run failed: " + e.message;
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  const urlEl   = document.getElementById("tab-url");
  const toggle  = document.getElementById("enabled-toggle");
  const rerunBtn = document.getElementById("rerun-btn");

  // Load and apply toggle state
  const { enabled } = await chrome.storage.local.get("enabled");
  toggle.checked = Boolean(enabled);

  toggle.addEventListener("change", async () => {
    await chrome.storage.local.set({ enabled: toggle.checked });
  });

  // Get active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) { showState("state-waiting"); return; }

  urlEl.textContent = truncateUrl(tab.url, 55);
  urlEl.title = tab.url;

  const storageKey = `tab_${tab.id}`;

  rerunBtn.addEventListener("click", () => triggerRerun(tab.id));

  // Poll storage until we have results for the current URL
  const poll = async () => {
    const stored = await chrome.storage.local.get(storageKey);
    const entry  = stored[storageKey];

    if (!entry || entry.url !== tab.url) {
      // No results yet for this page
      if (toggle.checked) {
        showState("state-running");
      } else {
        showState("state-waiting");
      }
      setTimeout(poll, 600);
      return;
    }

    if (entry.status === "running") {
      showState("state-running");
      setTimeout(poll, 600);
      return;
    }

    if (entry.status === "error") {
      showState("state-error");
      document.getElementById("state-error").textContent = "Test run failed: " + (entry.error || "unknown error");
      document.getElementById("footer").style.display = "flex";
      return;
    }

    if (entry.status === "done") {
      renderResults(entry.results, entry.runAt);
    }
  };

  poll();
});
