"use strict";
importScripts("shared/validators.js");

// ---------------------------------------------------------------------------
// Test files to inject (order matters — warnings_init last before runner)
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

// ---------------------------------------------------------------------------
// Readiness poller — injected into the page, resolves when Prebid has fired
// or after MAX_WAIT ms. Self-contained (no closure references).
// ---------------------------------------------------------------------------
function pbjsReadinessPoller() {
  return new Promise((resolve) => {
    const MAX_WAIT = 15000;
    const INTERVAL = 300;
    const start = Date.now();

    const check = () => {
      const hasPbjs   = !!(window.pbjs && Array.isArray(window.pbjs.que));
      const hasEvents = (window.__pbjsBidEventsDisplay || []).length > 0
                     || (window.__pbjsBidEventsVideo   || []).length > 0;
      if (hasPbjs && hasEvents) return resolve("ready");
      if (Date.now() - start > MAX_WAIT) return resolve("timeout");
      setTimeout(check, INTERVAL);
    };

    check();
  });
}

// ---------------------------------------------------------------------------
// Runner — collects raw data from every registered test.
// Self-contained (no closure references).
// ---------------------------------------------------------------------------
function runAllTests() {
  const results = {};
  const tests = window.__adTests || {};

  for (const [name, fn] of Object.entries(tests)) {
    try {
      results[name] = (typeof fn === "function") ? fn() : { _error: "not a function" };
    } catch (e) {
      results[name] = { _error: String(e) };
    }
  }

  return results;
}

// ---------------------------------------------------------------------------
// Badge helpers
// ---------------------------------------------------------------------------
function setBadgeRunning(tabId) {
  chrome.action.setBadgeText({ tabId, text: "…" });
  chrome.action.setBadgeBackgroundColor({ tabId, color: "#718096" });
}

function setBadgeDone(tabId, failCount) {
  chrome.action.setBadgeText({ tabId, text: failCount > 0 ? String(failCount) : "✓" });
  chrome.action.setBadgeBackgroundColor({ tabId, color: failCount > 0 ? "#c53030" : "#276749" });
}

function setBadgeError(tabId) {
  chrome.action.setBadgeText({ tabId, text: "!" });
  chrome.action.setBadgeBackgroundColor({ tabId, color: "#c53030" });
}


// ---------------------------------------------------------------------------
// Main: listen for tab load complete
// ---------------------------------------------------------------------------
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete") return;
  if (!tab.url || !tab.url.startsWith("http")) return;

  // Check enabled state
  const { enabled } = await chrome.storage.local.get("enabled");
  if (!enabled) return;

  const storageKey = `tab_${tabId}`;
  const url = tab.url;

  // Mark this tab as running for this URL — clears any previous page results
  await chrome.storage.local.set({
    [storageKey]: { url, status: "running", timestamp: Date.now() },
  });

  setBadgeRunning(tabId);

  try {
    // Wait for Prebid to actually fire before running tests
    await chrome.scripting.executeScript({
      target: { tabId },
      world: "MAIN",
      func: pbjsReadinessPoller,
    });

    // Inject all test definition files
    await chrome.scripting.executeScript({
      target: { tabId },
      files: TEST_FILES,
      world: "MAIN",
    });

    // Brief pause for the warnings IIFE to settle
    await new Promise((r) => setTimeout(r, 500));

    // Collect raw results from every registered test
    const [injection] = await chrome.scripting.executeScript({
      target: { tabId },
      world: "MAIN",
      func: runAllTests,
    });

    const results = injection?.result ?? {};

    await chrome.storage.local.set({
      [storageKey]: {
        url,
        status: "done",
        results,
        timestamp: Date.now(),
        runAt: new Date().toLocaleTimeString(),
      },
    });

    setBadgeDone(tabId, countValidatorFails(results));
  } catch (e) {
    await chrome.storage.local.set({
      [storageKey]: { url, status: "error", error: e.message, timestamp: Date.now() },
    });
    setBadgeError(tabId);
  }
});

// Clear stored results when a tab navigates away (new URL loading)
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo) => {
  if (changeInfo.status !== "loading") return;
  await chrome.storage.local.remove(`tab_${tabId}`);
  chrome.action.setBadgeText({ tabId, text: "" });
});

// Clean up when tab closes
chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.local.remove(`tab_${tabId}`);
});

