"use strict";

// ---------------------------------------------------------------------------
// Category map
// ---------------------------------------------------------------------------
const CATEGORIES = {
  "PREBID": [
    "pbjs_environment",
    "pbjs_display_bidder_presence",
    "pbjs_video_bidder_presence",
    "pbjs_display_auction_activity",
    "pbjs_adunit_configuration",
    "pbjs_consent_integration",
    "pbjs_identity_modules",
    "pbjs_display_price_floors",
    "pbjs_display_get_floors",
    "pbjs_video_price_floors",
    "pbjs_display_pubcid_presence",
    "pbjs_video_pubcid_presence",
    "pbjs_timeout_config",
    "pbjs_video_hero_player_placement",
    "pbjs_display_mantis_signals_bid",
    "pbjs_display_permutive_signals_bid",
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
  "IMA": [
    "ima_strategy_player",
    "ima_page_type",
    "ima_category1",
    "ima_category2",
    "ima_mantis",
    "ima_mantis_context",
    "ima_permutive",
    "ima_topictags",
    "ima_liveblog",
    "ima_video_id",
    "ima_adpos",
    "ima_bsc",
    "ima_abs",
  ],
};


// ---------------------------------------------------------------------------
// Test files to inject (must match background.js)
// ---------------------------------------------------------------------------
const TEST_FILES = [
  "js/pbjs_environment.js",
  "js/pbjs_display_bidder_presence.js",
  "js/pbjs_video_bidder_presence.js",
  "js/pbjs_display_auction_activity.js",
  "js/pbjs_adunit_configuration.js",
  "js/pbjs_consent_integration.js",
  "js/pbjs_identity_modules.js",
  "js/pbjs_display_price_floors.js",
  "js/pbjs_display_get_floors.js",
  "js/pbjs_video_price_floors.js",
  "js/pbjs_display_pubcid_presence.js",
  "js/pbjs_video_pubcid_presence.js",
  "js/pbjs_timeout_config.js",
  "js/pbjs_video_hero_player_placement.js",
  "js/pbjs_display_mantis_signals_bid.js",
  "js/pbjs_display_permutive_signals_bid.js",
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
  "js/ima_strategy_player.js",
  "js/ima_page_type.js",
  "js/ima_category1.js",
  "js/ima_category2.js",
  "js/ima_mantis.js",
  "js/ima_mantis_context.js",
  "js/ima_permutive.js",
  "js/ima_topictags.js",
  "js/ima_liveblog.js",
  "js/ima_video_id.js",
  "js/ima_adpos.js",
  "js/ima_bsc.js",
  "js/ima_abs.js",
];

// ── Supabase helpers ──────────────────────────────────────────────────────────
const SUPABASE_URL = "https://jcrcmwyidwsoakfearwg.supabase.co";
const SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpjcmNtd3lpZHdzb2FrZmVhcndnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQxMTE0MTksImV4cCI6MjA3OTY4NzQxOX0.1oW4JWzvA1CR6IPKoQEZWqhB0pytnHgXMTwTCv8LALg";
const _SB_HEADERS = {
  apikey: SUPABASE_ANON_KEY,
  Authorization: "Bearer " + SUPABASE_ANON_KEY,
};

function _derivePubEnv(url) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    if (host.includes("uat-web.independent.co.uk") || host.includes("staging-web.independent.co.uk"))
      return { publisher: "independent", env: "uat" };
    if (host.endsWith("independent.co.uk")) return { publisher: "independent", env: "prod" };
    if (host.endsWith("standard.co.uk"))    return { publisher: "evening_standard", env: "prod" };
  } catch (e) {}
  return { publisher: null, env: null };
}

function _extractGeo(results) {
  const d = results.pbjs_display_bidder_presence
         || results.pbjs_display_price_floors
         || results.pbjs_display_get_floors;
  if (!d) return null;
  const loc = String(d.locale || "").toUpperCase().trim();
  return ["UK", "US", "CAN", "ROW"].includes(loc) ? loc : (loc ? "ROW" : null);
}

function _extractDevice(results) {
  const d = results.env_is_mobile_or_tablet;
  if (!d) return null;
  const val = typeof d === "object" ? String(d.cookie_value || "") : String(d);
  return val.trim() === "true" ? "mobile" : "desktop";
}

function _extractPageType(results) {
  const d = results.gpt_page_type;
  if (!d) return null;
  const vals = Array.isArray(d) ? d : ((d && d.pageType) || []);
  const raw = String(vals[0] || "").toLowerCase().trim();
  const MAP = {
    article: "image_article", video: "video_article",
    homepage: "index", index: "index",
    blog: "blog_article", quiz: "quiz_article", gallery: "gallery_article",
  };
  return MAP[raw] || null;
}

async function _buildDbContext(tabUrl, results) {
  const ctx = { floors: null, floorsElse: null, bidders: null };
  const { publisher, env } = _derivePubEnv(tabUrl || "");
  if (!publisher) return ctx;

  const geo = _extractGeo(results);

  // Floor prices — fetch banner + video rows for this publisher/geo in one request
  if (geo) {
    try {
      const pubDomain = publisher === "independent"     ? "independent.co.uk"
                      : publisher === "evening_standard" ? "standard.co.uk"
                      : publisher + ".co.uk";
      const params = new URLSearchParams({
        select: "geo,ad_unit,media_type,floor_usd",
        publisher: "eq." + pubDomain,
        geo: "in.(" + geo + ",ELSE)",
      });
      const res = await fetch(SUPABASE_URL + "/rest/v1/prebid_floor_prices?" + params, {
        headers: _SB_HEADERS,
      });
      if (res.ok) {
        const rows = await res.json();
        ctx.floors = {};
        for (const r of (rows || [])) {
          const rowGeo    = String(r.geo       || "").toUpperCase();
          const adUnit    = String(r.ad_unit   || "").trim();
          const mediaType = String(r.media_type || "").trim();
          const floor     = parseFloat(r.floor_usd);
          if (isNaN(floor)) continue;
          if (rowGeo === "ELSE" && adUnit === "ELSE") {
            ctx.floorsElse = floor;
          } else if (rowGeo === geo) {
            ctx.floors[adUnit + "|" + mediaType] = floor;
          }
        }
      }
    } catch (e) {}
  }

  // Expected bidders from profile
  const device   = _extractDevice(results);
  const pageType = _extractPageType(results);
  const geoLower = geo === "UK" ? "uk" : geo === "US" ? "us" : "row";

  if (geo && device && pageType) {
    try {
      const res = await fetch(SUPABASE_URL + "/rest/v1/rpc/get_profile_bidders", {
        method: "POST",
        headers: { ..._SB_HEADERS, "Content-Type": "application/json" },
        body: JSON.stringify({
          p_publisher_code: publisher,
          p_env_code:       env,
          p_geo_code:       geoLower,
          p_device_code:    device,
          p_page_type_code: pageType,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          ctx.bidders = data
            .map(item => typeof item === "string" ? item : (item.bidder_code || item.code || ""))
            .filter(Boolean);
        }
      }
    } catch (e) {}
  }

  return ctx;
}

// Self-contained runner (same logic as background.js runAllTests, no closures)
function runAllTests() {
  const results = {};
  const tests = window.__adTests || {};
  for (const [name, fn] of Object.entries(tests)) {
    try { results[name] = (typeof fn === "function") ? fn() : { _error: "not a function" }; }
    catch (e) { results[name] = { _error: String(e) }; }
  }
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

// Last rendered payload — populated by renderResults(), read by copy button.
let _copyPayload = null;

function _stripNoise(data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) return data;
  const out = {};
  for (const [k, v] of Object.entries(data)) {
    if (k === "installed_modules") continue;
    out[k] = v;
  }
  return out;
}

function _formatJson(data) {
  try {
    const s = JSON.stringify(data, null, 2);
    return s.length > 4000 ? s.slice(0, 4000) + "\n… (truncated)" : s;
  } catch (_) { return String(data); }
}

function renderResults(results, runAt, dbContext) {
  dbContext = dbContext || {};
  hideStates();
  const resultsEl = document.getElementById("results");
  const summaryEl = document.getElementById("summary");
  const footerEl  = document.getElementById("footer");
  resultsEl.innerHTML = "";
  resultsEl.style.display = "block";

  let totalPass = 0, totalFail = 0, totalSkip = 0;
  const copyResults = {};

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

      // Expandable data panel — shown on click
      const expandBtn = document.createElement("span");
      expandBtn.className = "expand-btn";
      expandBtn.textContent = "▶";

      const dataPanel = document.createElement("div");
      dataPanel.className = "test-data";

      if (data !== undefined && data !== null && !data._error) {
        const pre = document.createElement("pre");
        pre.className = "data-json";
        pre.textContent = _formatJson(_stripNoise(data));
        dataPanel.appendChild(pre);
      }

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
        } else {
          const errors = validator(data, results, dbContext);
          if (errors === null) {
            badge.className += " badge-skip";
            badge.textContent = "SKIP";
            totalSkip++;
          } else if (errors.length === 0) {
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

      // Build copy payload entry for this test
      {
        let status = "NO DATA", errors = [];
        if (data !== undefined && data !== null) {
          if (data._error) { status = "ERROR"; errors = [data._error]; }
          else {
            const validator = VALIDATORS[name];
            if (!validator) { status = "INFO"; }
            else {
              const ve = validator(data, results, dbContext);
              if (ve === null)       { status = "SKIP"; }
              else if (ve.length === 0) { status = "PASS"; }
              else                   { status = "FAIL"; errors = ve; }
            }
          }
        }
        copyResults[name] = { status, errors, data: _stripNoise(data ?? null) };
      }

      // Wire expand toggle
      row.addEventListener("click", () => {
        const open = dataPanel.classList.toggle("open");
        expandBtn.textContent = open ? "▼" : "▶";
      });

      const topRow = document.createElement("div");
      topRow.className = "test-top";
      topRow.appendChild(label);
      topRow.appendChild(badge);
      topRow.appendChild(expandBtn);
      row.appendChild(topRow);
      if (detail.textContent) row.appendChild(detail);
      row.appendChild(dataPanel);
      resultsEl.appendChild(row);
    }
  }

  summaryEl.textContent = `${totalPass} passed  /  ${totalFail} failed  /  ${totalSkip} no data`;
  summaryEl.className = "summary " + (totalFail > 0 ? "summary-fail" : "summary-pass");
  summaryEl.style.display = "block";

  // Store copy payload
  _copyPayload = {
    url:     document.getElementById("tab-url").title || document.getElementById("tab-url").textContent,
    run_at:  runAt || "",
    summary: { passed: totalPass, failed: totalFail, no_data: totalSkip },
    results: copyResults,
  };

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
        return new Promise(function (resolve) {
          var MAX_DISPLAY = 15000, MAX_VIDEO = 15000, INTERVAL = 300, start = Date.now();
          function hasPbjs()    { return !!(window.pbjs && Array.isArray(window.pbjs.que)); }
          function hasDisplay() { return (window.__pbjsBidEventsDisplay || []).length > 0; }
          function hasVideo()   { return (window.__pbjsBidEventsVideo   || []).length > 0; }
          function getPageType() { try { var pt = window.googletag && googletag.pubads && googletag.pubads().getTargeting("pageType"); return pt && pt[0] ? String(pt[0]).toLowerCase() : ""; } catch(e) { return ""; } }
          function waitVideo() { var vs = Date.now(); function poll() { if (hasVideo()) return resolve("ready_video"); if (Date.now()-vs > MAX_VIDEO) return resolve("timeout_video"); setTimeout(poll, INTERVAL); } poll(); }
          function check() { if (hasPbjs() && hasDisplay()) { return getPageType() === "video" ? waitVideo() : resolve("ready"); } if (Date.now()-start > MAX_DISPLAY) return resolve("timeout"); setTimeout(check, INTERVAL); }
          check();
        });
      },
    });

    // Ask background for the IMA capture for this tab, then inject it before tests
    const bgImaData = await chrome.runtime.sendMessage({ type: "getImaCapture", tabId });
    await chrome.scripting.executeScript({
      target: { tabId },
      world: "MAIN",
      func: (data) => { window.__imaAdRequest = data; },
      args: [bgImaData ?? null],
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
    const dbContext = await _buildDbContext(url, results);
    renderResults(results, runAt, dbContext);
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

  const copyBtn = document.getElementById("copy-btn");
  copyBtn.addEventListener("click", async () => {
    if (!_copyPayload) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(_copyPayload, null, 2));
      copyBtn.textContent = "Copied!";
      setTimeout(() => { copyBtn.textContent = "Copy JSON"; }, 2000);
    } catch (_) {
      copyBtn.textContent = "Failed";
      setTimeout(() => { copyBtn.textContent = "Copy JSON"; }, 2000);
    }
  });

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
      const dbContext = await _buildDbContext(tab.url, entry.results);
      renderResults(entry.results, entry.runAt, dbContext);
    }
  };

  poll();
});
