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

function _formatJson(data) {
  try {
    const s = JSON.stringify(data, null, 2);
    return s.length > 4000 ? s.slice(0, 4000) + "\n… (truncated)" : s;
  } catch (_) { return String(data); }
}

function renderResults(results, runAt) {
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
        pre.textContent = _formatJson(data);
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
          const errors = validator(data, results);
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

      // Build copy payload entry for this test
      {
        let status = "NO DATA", errors = [];
        if (data !== undefined && data !== null) {
          if (data._error) { status = "ERROR"; errors = [data._error]; }
          else {
            const validator = VALIDATORS[name];
            if (!validator) { status = "INFO"; }
            else {
              const ve = validator(data, results);
              status = ve.length === 0 ? "PASS" : "FAIL";
              errors = ve;
            }
          }
        }
        copyResults[name] = { status, errors, data: data ?? null };
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
          function waitVideo() { var vs = Date.now(); function poll() { if (hasVideo()) return resolve("ready"); if (Date.now()-vs > MAX_VIDEO) return resolve("timeout_video"); setTimeout(poll, INTERVAL); } poll(); }
          function check() { if (hasPbjs() && hasDisplay()) { return getPageType() === "video" ? waitVideo() : resolve("ready"); } if (Date.now()-start > MAX_DISPLAY) return resolve("timeout"); setTimeout(check, INTERVAL); }
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
      renderResults(entry.results, entry.runAt);
    }
  };

  poll();
});
