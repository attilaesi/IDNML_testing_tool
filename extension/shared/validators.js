// Shared validators — loaded by background.js (importScripts) and popup.html (<script>).
// Each function receives (data, allResults).
// Returns string[] — empty = PASS, non-empty = FAIL with those messages.

// Helper: check if the current page is a video page from GPT targeting.
// gpt_page_type extractor returns an array of values.
function _isVideoPage(allResults) {
  var d = allResults && allResults.gpt_page_type;
  if (!d) return false;
  var vals = Array.isArray(d) ? d : ((d && d.pageType) || []);
  return vals.some(function(v) { return String(v).toLowerCase() === "video"; });
}

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

  "pbjs_display_bidder_presence": (data, allResults, dbContext) => {
    const errors = [];
    if (!data || !data.hasPbjs) { errors.push("window.pbjs not present; cannot run display bidder presence test."); return errors; }
    if (parseInt(data.bidRequestedEvents || 0, 10) === 0) {
      errors.push("No DISPLAY bidRequested events captured. Prebid may not have fired yet.");
      return errors;
    }
    if (dbContext && dbContext.displayBidders && dbContext.displayBidders.length) {
      const observed = new Set((data.biddersFromRequests || []).map(b => String(b).toLowerCase()));
      const missing = dbContext.displayBidders.filter(b => !observed.has(String(b).toLowerCase()));
      if (missing.length) {
        const ctx = [dbContext.geo, dbContext.device].filter(Boolean).join(", ");
        errors.push(
          "Expected display bidders not observed: " + missing.join(", ") +
          (ctx ? " — " + ctx : "") +
          ". Expected: " + dbContext.displayBidders.join(", ") + "."
        );
      }
    }
    return errors;
  },

  "pbjs_video_bidder_presence": (data, allResults, dbContext) => {
    if (!data || !data.hasPbjs) return ["window.pbjs not present; cannot run video bidder presence test."];
    if (parseInt(data.heroBidRequestedEvents || 0, 10) === 0) {
      return _isVideoPage(allResults)
        ? ["No hero_player VIDEO bidRequested events found (video page — expected video activity)."]
        : null; // SKIP — no video on this page type
    }
    const errors = [];
    if (dbContext && dbContext.videoBidders && dbContext.videoBidders.length) {
      const observed = new Set((data.biddersFromHeroRequests || []).map(b => String(b).toLowerCase()));
      const missing = dbContext.videoBidders.filter(b => !observed.has(String(b).toLowerCase()));
      if (missing.length) {
        const ctx = [dbContext.geo, dbContext.device].filter(Boolean).join(", ");
        errors.push(
          "Expected video bidders not observed: " + missing.join(", ") +
          (ctx ? " — " + ctx : "") +
          ". Expected: " + dbContext.videoBidders.join(", ") + "."
        );
      }
    }
    return errors;
  },

  "pbjs_display_auction_activity": (data) => {
    const errors = [];
    const activity = (data && data.prebid_auction_activity) ? data.prebid_auction_activity : (data || {});
    for (const e of (activity.errors || [])) errors.push("Extraction error: " + e);
    const debug = activity.debug || {};
    if (parseInt(activity.total_bid_responses || 0, 10) === 0 && parseInt(debug.bidRequestedCount || 0, 10) === 0)
      errors.push("No bid responses recorded and no bidRequested events seen.");
    return errors;
  },

  "pbjs_adunit_configuration": (data) => {
    const errors = [];
    const adUnitData = (data && data.prebid_ad_units) ? data.prebid_ad_units : (data || {});
    for (const e of (adUnitData.errors || [])) errors.push("Extraction error: " + e);
    const adUnits = adUnitData.ad_units || [];
    if (!adUnits.length) { errors.push("No Prebid ad units configured (pbjs.adUnits is empty)"); return errors; }
    const missingCode = [], missingBidders = [];
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
      errors.push("Prebid consentManagement config not present in pbjs.getConfig()."); return errors;
    }
    const configured = [], missingCmpApi = [];
    for (const [ns, cfg] of Object.entries({ gdpr: data.gdpr, usp: data.usp, gpp: data.gpp })) {
      if (!cfg) continue;
      configured.push(ns);
      if (typeof cfg === "object" && !cfg.cmpApi) missingCmpApi.push(ns);
    }
    if (!configured.length) { errors.push("consentManagement present but no gdpr/usp/gpp namespaces configured."); return errors; }
    if (missingCmpApi.length) errors.push("cmpApi not configured for: " + missingCmpApi.join(", "));
    return errors;
  },

  "pbjs_identity_modules": (data) => {
    if (!data) return ["No data returned"];
    const userIds = data.userIds || data.actual_identity_modules || [];
    return userIds.length ? [] : ["No identity modules found in pbjs.getConfig().userSync.userIds"];
  },

  "pbjs_display_price_floors": (data, allResults, dbContext) => {
    if (!data || !data.hasPbjs) return ["window.pbjs not present"];
    if (!data.has_display_store || !parseInt(data.display_bidrequested_events || 0, 10)) {
      return ["No DISPLAY Prebid activity observed — cannot check floor values."];
    }
    const errors = [];
    for (const e of (data.errors || [])) errors.push("JS error: " + e);

    const units = data.ad_units || [];
    const floors = data.configured_floors || {};

    if (!units.length) {
      errors.push("No banner ad units found in pbjs.adUnits.");
      return errors;
    }

    const nullKeys = Object.keys(floors).filter(k => floors[k] === null);
    if (nullKeys.length) errors.push("No floor configured on: " + nullKeys.join(", "));

    if (dbContext && dbContext.floors) {
      const TOL = 0.001;
      const wrong = [];
      for (const [key, actual] of Object.entries(floors)) {
        if (actual === null) continue;
        const expected = dbContext.floors[key] ?? null;
        if (expected != null && Math.abs(actual - expected) > TOL) {
          wrong.push(key + ": got " + actual.toFixed(4) + ", expected " + expected.toFixed(4));
        }
      }
      if (wrong.length) errors.push("Floor value mismatch: " + wrong.join("; "));
    }

    return errors;
  },

  "pbjs_display_get_floors": (data, allResults, dbContext) => {
    if (!data || !data.hasPbjs) return null; // SKIP — pbjs not available
    if (!data.has_display_store || !parseInt(data.display_bidrequested_events || 0, 10)) return null; // SKIP

    if (!data.get_floors_available) {
      return ["bid.getFloor is not a function on any observed bid — priceFloors module not active."];
    }

    const errors = [];
    const resultsPerUnit = data.results_per_unit || {};
    const without = data.units_without_floor || [];
    const withFloor = data.units_with_floor || [];

    for (const unit of without) {
      const info = resultsPerUnit[unit] || {};
      errors.push(unit + ": getFloors() failed — " + (info.error || "no floor returned"));
    }

    if (dbContext && dbContext.floors) {
      const TOL = 0.001;
      const wrong = [];
      for (const unit of withFloor) {
        const info = resultsPerUnit[unit] || {};
        const actual = info.floor;
        if (actual == null) continue;
        const key = unit + "|banner";
        const expected = dbContext.floors[key] ?? null;
        if (expected != null && Math.abs(actual - expected) > TOL) {
          wrong.push(unit + ": getFloors()=" + actual.toFixed(4) + ", expected=" + expected.toFixed(4));
        }
      }
      if (wrong.length) errors.push("Floor value mismatch: " + wrong.join("; "));
    }

    return errors;
  },

  "pbjs_video_price_floors": (data, allResults, dbContext) => {
    if (!data || !data.hasPbjs) return ["window.pbjs not present"];
    if (!data.has_video_store || !parseInt(data.video_bidrequested_events || 0, 10)) {
      return _isVideoPage(allResults)
        ? ["No VIDEO Prebid activity observed on video page."]
        : null; // SKIP — no video on this page type
    }
    const errors = [];
    for (const e of (data.errors || [])) errors.push("JS error: " + e);

    const units = data.ad_units || [];
    const floors = data.configured_floors || {};

    if (!units.length) {
      return _isVideoPage(allResults)
        ? ["No video ad units found in pbjs.adUnits."]
        : null;
    }

    const nullKeys = Object.keys(floors).filter(k => floors[k] === null);
    if (nullKeys.length) errors.push("No floor configured on: " + nullKeys.join(", "));

    if (dbContext && dbContext.floors) {
      const TOL = 0.001;
      const wrong = [];
      for (const [key, actual] of Object.entries(floors)) {
        if (actual === null) continue;
        const expected = dbContext.floors[key] ?? null;
        if (expected != null && Math.abs(actual - expected) > TOL) {
          wrong.push(key + ": got " + actual.toFixed(4) + ", expected " + expected.toFixed(4));
        }
      }
      if (wrong.length) errors.push("Video floor value mismatch: " + wrong.join("; "));
    }

    return errors;
  },

  "pbjs_display_pubcid_presence": (data) => {
    if (!data || !data.hasPbjs) return ["window.pbjs not found"];
    if (parseInt(data.bidRequestedEvents || 0, 10) === 0) return ["No DISPLAY bidRequested events captured; cannot confirm pubcid."];
    const missing = data.biddersMissingPubcid || [];
    return missing.length ? ["pubcid missing for DISPLAY bidders: " + missing.join(", ")] : [];
  },

  "pbjs_video_pubcid_presence": (data, allResults) => {
    if (!data || !data.hasPbjs) return ["window.pbjs not found"];
    if (parseInt(data.heroBidsConsidered || 0, 10) === 0) {
      return _isVideoPage(allResults)
        ? ["No VIDEO hero_player bids captured on a video page; cannot confirm pubcid."]
        : null; // SKIP — no video on this page type
    }
    const missing = data.biddersMissingPubcid || [];
    return missing.length ? ["pubcid missing for VIDEO bidders: " + missing.join(", ")] : [];
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

  "pbjs_video_hero_player_placement": (data, allResults) => {
    if (!data || !data.hasPbjs) return ["window.pbjs not present"];
    if (parseInt(data.eventsLen || 0, 10) === 0 || parseInt(data.heroBidsTotal || 0, 10) === 0) {
      return _isVideoPage(allResults)
        ? ["No hero_player bids found on a video page (poller waited but no video events fired)."]
        : null;
    }
    const expP = data.expectedPlacement ?? 1;
    const expC = data.expectedPlcmt ?? 2;
    const lines = [];
    for (const bidder of Object.keys(data.perBidder || {}).sort()) {
      const info = data.perBidder[bidder] || {};
      const missP = parseInt(info.missingPlacement || 0, 10), invP = parseInt(info.invalidPlacement || 0, 10);
      const missC = parseInt(info.missingPlcmt || 0, 10),     invC = parseInt(info.invalidPlcmt || 0, 10);
      if (!missP && !invP && !missC && !invC) continue;
      const r = [];
      if (missP) r.push("missing placement=" + missP);
      if (invP)  r.push("invalid placement=" + invP + " (expected " + expP + ")");
      if (missC) r.push("missing plcmt=" + missC);
      if (invC)  r.push("invalid plcmt=" + invC + " (expected " + expC + ")");
      lines.push(bidder + ": " + r.join("; "));
    }
    return lines.length ? ["Hero player placement failures:\n" + lines.join("\n")] : [];
  },

  "pbjs_msft_keywords": (data, allResults, dbContext) => {
    if (!data || !data.hasPbjs) return null; // SKIP

    // Skip if msft didn't bid on this page — checked against DB profile if available,
    // otherwise fall back to what the JS observed in the bid events.
    const _displayBidders = (dbContext && dbContext.displayBidders) || [];
    if (_displayBidders.length) {
      if (!_displayBidders.map(b => String(b).toLowerCase()).includes("msft")) return null;
    } else if (!data.msft_bid_observed) {
      return null; // SKIP — msft not seen in auction and no DB context to override
    }

    const userKw = data.user_keywords;
    const siteKw = data.site_keywords;
    const errors = [];

    if (userKw === null) {
      errors.push("ortb2.user.keywords not found.");
    } else {
      if (!data.user_has_p_standard) errors.push("user.keywords: 'p_standard=' key not present.");
      if (!data.user_has_permutive)  errors.push("user.keywords: 'permutive=' key not present.");
      if (data.user_spaces_found)    errors.push("user.keywords: spaces around comma separators.");
    }

    if (siteKw === null) {
      errors.push("ortb2.site.keywords not found.");
    } else {
      if (!data.site_has_mantis)         errors.push("site.keywords: 'mantis=' key not present.");
      if (!data.site_has_mantis_context) errors.push("site.keywords: 'mantis_context=' key not present.");
      if (data.site_spaces_found)        errors.push("site.keywords: spaces around comma separators.");
    }

    return errors;
  },

  "pbjs_display_mantis_signals_bid": (data) => {
    if (!data || !data.hasPbjs) return ["pbjs not present"];
    if (!parseInt(data.totalRequests || 0, 10)) return ["No bidder requests found"];
    const bidders = Object.keys(data.perBidder || {});
    if (!bidders.length) return ["No bidders found in requests"];
    const MANTIS_RE = /^[A-Za-z0-9][A-Za-z0-9_-]*-(GREEN|AMBER|RED)$/;
    const CTX_RE    = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
    const chk = (name, obs, re) => {
      if (!obs || !obs.seen) return [name + ": missing"];
      if (obs.type !== "array") return [name + ": wrong type (got " + obs.type + ")"];
      if (!parseInt(obs.count || 0, 10)) return [name + ": empty array"];
      const bad = (obs.sample || []).map(String).filter(v => !re.test(v));
      return bad.length ? [name + ": invalid entries -> " + bad.slice(0, 5).join(", ")] : [];
    };
    const errors = [];
    for (const bidder of bidders.sort()) {
      const info = data.perBidder[bidder] || {};
      if (!parseInt(info.requestCount || 0, 10)) continue;
      const p = info.paths || {};
      const f = [...chk("site.ext.data.mantis", p["site.ext.data.mantis"] || {}, MANTIS_RE),
                 ...chk("site.ext.data.mantis_context", p["site.ext.data.mantis_context"] || {}, CTX_RE)];
      if (f.length) errors.push(bidder + ": " + f.join("; "));
    }
    return errors;
  },

  "pbjs_display_permutive_signals_bid": (data) => {
    if (!data || !data.hasPbjs) return ["pbjs not present"];
    if (!parseInt(data.totalRequests || 0, 10)) return ["No bidder requests found"];
    const REQUIRED = ["ix", "rubicon", "msft", "pubmatic"];
    const pb = data.perBidder || {};
    if (!REQUIRED.some(b => parseInt((pb[b] || {}).requestCount || 0, 10) > 0))
      return ["No requests for required bidders: " + REQUIRED.join(", ")];
    const hasToken = (sample, t) => (sample || []).some(r => String(r).toLowerCase().includes(t.toLowerCase()));
    const errors = [];
    for (const bidder of REQUIRED) {
      const info = pb[bidder]; if (!info || !parseInt(info.requestCount || 0, 10)) continue;
      const p = info.paths || {}, f = [];
      if (!p["user.ext.data.p_standard"]?.seen) f.push("user.ext.data.p_standard: missing");
      if (!p["user.ext.data.permutive"]?.seen)  f.push("user.ext.data.permutive: missing");
      const kw = p["user.keywords"] || {};
      if (!kw.seen) { f.push("user.keywords: missing"); }
      else { const mt = ["p_standard=","p_standard_aud=","permutive="].filter(t => !hasToken(kw.sample, t)); if (mt.length) f.push("user.keywords: missing tokens " + mt.join(", ")); }
      if (f.length) errors.push(bidder + ": FAIL (" + f.join("; ") + ")");
    }
    return errors;
  },

  "gpt_page_type": (data) => {
    if (data == null) return ["GPT targeting not available."];
    const vals = (Array.isArray(data) ? data : (data.pageType || [])).map(v => String(v).trim()).filter(v => v);
    return vals.length ? [] : ["pageType targeting key missing or empty."];
  },

  "gpt_mantis_context": (data) => {
    if (!data) return ["GPT targeting not available."];
    if (!data.present) return ["mantis_context key not found in GPT targeting."];
    return (data.values || []).map(v => String(v).trim()).filter(v => v).length ? [] : ["mantis_context present but all values empty."];
  },

  "gpt_anonymised_key": (data) => {
    if (!data || !data.hasGpt) return [];
    if (data.error) return ["Error: " + data.error];
    return (data.keyUsed && (data.values || []).length) ? [] : ["No anonymised targeting found (keys tried: AnonymisedSignalLift, anonymised)."];
  },

  "gpt_article_id": (data) => {
    if (!data) return [];
    const pt = ((data.pageType || [])[0] || "").toLowerCase().trim();
    if (pt === "index" || pt === "homepage") return [];
    const norm = {}; for (const [k, v] of Object.entries(data)) norm[k.toLowerCase()] = (v || []).map(String);
    const CANDS = ["article", "articleid", "article_id", "content_id"];
    let ok = false; const empty = [];
    for (const c of CANDS) { if (!(c in norm)) continue; const g = norm[c].filter(v => v && !["null","none","undefined"].includes(v.toLowerCase())); if (g.length) { ok = true; break; } empty.push(c); }
    return ok ? [] : ["No valid article ID targeting found. Empty/invalid: " + (empty.join(", ") || "none found")];
  },

  "gpt_autorefresh":        (data) => { const v = ((data||{}).autorefresh||[]).map(v=>String(v).trim()); if(!v.length) return []; const b=v.filter(x=>!["yes","no"].includes(x.toLowerCase())); return b.length?["Invalid autorefresh values: "+b.join(", ")]:[];},
  "gpt_category1":          (data) => { if(!data) return []; const pt=((data.pageType||[])[0]||"").toLowerCase().trim(); if(pt==="index"||pt==="homepage") return []; const v=(data.category1||[]).map(v=>String(v).trim()).filter(v=>v); return v.length?[]:["category1 targeting missing or empty on article-like page."]; },
  "gpt_category2":          (data) => { if(!data) return []; const pt=((data.pageType||[])[0]||"").toLowerCase().trim(); if(pt==="index"||pt==="homepage") return []; const c1=(data.category1||[]).map(v=>String(v).trim()).filter(v=>v); const c2=(data.category2||[]).map(v=>String(v).trim()).filter(v=>v); if(!c2.length&&c1.length) return []; return c2.length?[]:["category2 targeting empty/invalid for article-like page."]; },
  "gpt_cmp_active":         (data) => { const v=((data||{}).cmpActive||[]).map(v=>String(v).trim()); if(!v.length) return []; const b=v.filter(x=>!["true","false"].includes(x.toLowerCase())); return b.length?["Invalid cmpActive values: "+b.join(", ")]:[];},
  "gpt_commercial":         (data) => { const v=((data||{}).commercial||[]).map(v=>String(v).trim()); if(!v.length) return []; const b=v.filter(x=>!["y","n"].includes(x.toLowerCase())); return b.length?["Invalid commercial values: "+b.join(", ")]:[];},
  "gpt_consent_tcf":        (data) => { if(!data||!data.hasGpt) return []; return (!data.gdprKey&&!data.tcString)?["For UK locale, neither gdpr key nor euconsent-v2 TCString found."]:[];},
  "gpt_content_sources":    (data) => { const v=((data||{}).contentSources||[]).map(v=>String(v).trim()); if(!v.length) return []; return v.filter(x=>x).length?[]:["contentSources present but all values empty."];},
  "gpt_gam_bid_keys":       (data) => { if(!data||data.error||!data.hasGpt||!data.auctionEndCount) return []; const e=[]; if(!data.hasPrebid) e.push("No hb_* keys; Prebid did not enrich GAM."); if(!data.hasTam) e.push("No amzn* keys; TAM did not enrich GAM."); return e;},
  "gpt_gdpr_key":           (data) => { if(!data||!data.hasGpt) return []; const v=(data.gdprValues||[]).map(v=>String(v).trim()); if(!v.length) return ["gdpr targeting key missing."]; return v.filter(x=>x==="0"||x==="1").length?[]:["Invalid gdpr value(s): "+v.join(", ")];},
  "gpt_liveblog":           (data) => { const v=((data||{}).liveblog||[]).map(v=>String(v).trim()); if(!v.length) return []; const b=v.filter(x=>!["y","n"].includes(x.toLowerCase())); return b.length?["Invalid liveblog values: "+b.join(", ")]:[];},
  "gpt_longread":           (data) => { const v=((data||{}).longread||[]).map(v=>String(v).trim()); if(!v.length) return []; const b=v.filter(x=>!["y","n"].includes(x.toLowerCase())); return b.length?["Invalid longread values: "+b.join(", ")]:[];},
  "gpt_mantis":             (data) => { const v=((data||{}).mantis||[]).map(v=>String(v).trim()); if(!v.length) return []; return v.filter(x=>x).length?[]:["mantis targeting present but all values empty."];},
  "gpt_permutive_composite":(data) => { const v=((data||{}).permutive||[]).map(v=>String(v).trim()); if(!v.length) return []; return v.filter(x=>x).length?[]:["permutive targeting present but all values empty."];},
  "gpt_referrer":           (data) => { if(!data||!data.hasGpt) return []; const g=(data.gptReferrer||"").trim(), d=(data.docReferrer||"").trim(); if(!g||!d) return []; return (g.includes(d)||d.includes(g))?[]:["GPT referrer '"+g+"' does not match document.referrer '"+d+"'."];},
  "gpt_reg_gate":           (data) => { const v=((data||{}).reg_gate||[]).map(v=>String(v).trim()); if(!v.length) return []; return v.filter(x=>x).length?[]:["reg_gate targeting present but empty."];},
  "gpt_testgroup":          (data) => { const v=((data||{}).testgroup||[]).map(v=>String(v).trim()); if(!v.length) return []; return v.filter(x=>x).length?[]:["testgroup targeting present but empty."];},
  "gpt_topictags":          (data) => { const v=((data||{}).topictags||[]).map(v=>String(v).trim()); if(!v.length) return []; return v.filter(x=>x).length?[]:["topictags targeting present but all empty."];},

  "gpt_untested_keys": (data) => {
    const KNOWN = new Set(["pageType","article","articleId","article_id","content_id","category1","category2","commercial","liveblog","longread","reg_gate","testgroup","topictags","mantis","mantis_context","gdpr","autorefresh","cmpActive","contentSources","referrer","permutive","AnonymisedSignalLift"]);
    const keys = (data || {}).keys || []; if (!keys.length) return [];
    const u = keys.filter(k => !KNOWN.has(k));
    return u.length ? ["Unknown GPT keys: " + u.sort().join(", ")] : [];
  },

  "env_is_mobile_or_tablet": (data) => {
    const val = (data && typeof data === "object") ? data.cookie_value : data;
    if (val == null) return ["Cookie 'is_mobile_or_tablet' is not set."];
    return (val === "true" || val === "false") ? [] : ["Cookie 'is_mobile_or_tablet' has unexpected value: '" + val + "'"];
  },

  "layout_ad_sequence": (data) => {
    if (!data || data.error) return data?.error ? ["JS error: " + data.error] : [];
    if (data.skipped) return [];
    const f = (data.rows || []).filter(r => (r.status || "").startsWith("FAIL"));
    return f.map(r => r.slot + ": " + r.status + (r.reason ? " — " + r.reason : ""));
  },

  // -------------------------------------------------------------------------
  // IMA (video VAST cust_params) validators
  // null data = no IMA request captured → SKIP
  // [] data   = key absent from cust_params
  // ["v"]     = key present with value v
  // -------------------------------------------------------------------------

  "ima_strategy_player": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return ["No JW Player strategy rules log captured."];
    return data.some(v => v) ? [] : ["No JW Player strategy rules log captured."];
  },

  "ima_page_type": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return null;
    if (!data.length) return ["pageType missing from IMA cust_params"];
    if (!data.some(v => v)) return ["pageType present but empty in IMA cust_params"];
    return [];
  },

  "ima_category1": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return null;
    if (!data.length) return ["category1 missing from IMA cust_params"];
    if (!data.some(v => v)) return ["category1 present but empty in IMA cust_params"];
    return [];
  },

  "ima_category2": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return null;
    const cat2 = (data.category2 || []);
    if (!cat2.length) return ["category2 missing from IMA cust_params"];
    if (!cat2.some(v => v)) return ["category2 present but empty in IMA cust_params"];
    return [];
  },

  "ima_mantis": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return null;
    if (!data.length) return ["mantis missing from IMA cust_params"];
    if (!data.some(v => v)) return ["mantis present but empty in IMA cust_params"];
    return [];
  },

  "ima_mantis_context": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return null;
    if (!data.length) return ["mantis_context missing from IMA cust_params"];
    if (!data.some(v => v)) return ["mantis_context present but empty in IMA cust_params"];
    return [];
  },

  "ima_permutive": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return null;
    if (!data.length) return ["permutive missing from IMA cust_params"];
    if (!data.some(v => v)) return ["permutive present but empty in IMA cust_params"];
    return [];
  },

  "ima_topictags": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return null;
    if (!data.length) return ["topictags missing from IMA cust_params"];
    if (!data.some(v => v)) return ["topictags present but empty in IMA cust_params"];
    return [];
  },

  "ima_liveblog": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return null;
    if (!data.length) return ["liveblog missing from IMA cust_params"];
    if (!data.some(v => v)) return ["liveblog present but empty in IMA cust_params"];
    const bad = data.filter(v => !["y", "n"].includes(String(v).toLowerCase()));
    if (bad.length) return ["liveblog invalid in IMA cust_params (expected 'y'/'n'): " + bad.join(", ")];
    return [];
  },

  "ima_video_id": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return null;
    if (!data.length) return ["videoID missing from IMA cust_params"];
    if (!data.some(v => v)) return ["videoID present but empty in IMA cust_params"];
    const invalid = data.filter(v => !/^[a-zA-Z0-9]{4,}$/.test(String(v).trim()));
    if (invalid.length) return ["videoID format invalid (expected alphanumeric, e.g. yYEQtO0C): " + invalid.join(", ")];
    return [];
  },

  "ima_bsc": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return null;
    if (!data.length) return ["BSC missing from IMA cust_params"];
    if (!data.some(v => v)) return ["BSC present but empty in IMA cust_params"];
    return [];
  },

  "ima_abs": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return null;
    if (!data.length) return ["ABS missing from IMA cust_params"];
    if (!data.some(v => v)) return ["ABS present but empty in IMA cust_params"];
    return [];
  },

  "ima_adpos": (data, allResults) => {
    if (!_isVideoPage(allResults)) return null;
    if (data === null) return null;
    if (!data.length) return ["adpos missing from IMA cust_params"];
    if (!data.some(v => v)) return ["adpos present but empty in IMA cust_params"];
    return [];
  },

};

// Count how many tests fail validation against raw results object
// null = SKIP, [] = PASS, ["msg"] = FAIL
function countValidatorFails(results) {
  let fails = 0;
  for (const [name, data] of Object.entries(results || {})) {
    if (!data || data._error) { fails++; continue; }
    const validator = VALIDATORS[name];
    if (!validator) continue;
    const result = validator(data, results);
    if (result !== null && result.length > 0) fails++;
  }
  return fails;
}
