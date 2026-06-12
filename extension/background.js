"use strict";
importScripts("shared/validators.js");

// ---------------------------------------------------------------------------
// IMA capture — intercepts hero_player GAM video ad requests at the network
// level via webRequest. Reliable regardless of frame or execution context.
// ---------------------------------------------------------------------------
const _imaCaptures = new Map(); // tabId → { cust_params }

const _IMA_URL_FILTER = {
  urls: [
    "*://pubads.g.doubleclick.net/gampad/ads*",
    "*://securepubads.g.doubleclick.net/gampad/ads*",
    "*://pagead2.googlesyndication.com/gampad/ads*",
    "*://pubads.g.doubleclick.net/gampad/live/ads*",
    "*://securepubads.g.doubleclick.net/gampad/live/ads*",
    "*://pagead2.googlesyndication.com/gampad/live/ads*",
  ],
};

chrome.webRequest.onBeforeRequest.addListener((details) => {
  try {
    const _IMA_AD_UNITS = ["hero_player", "primis_hero_player_DIRECT"];
    if (!_IMA_AD_UNITS.some(u => details.url.indexOf(u) !== -1)) return;
    const u = new URL(details.url);
    if (u.searchParams.get("env") !== "vp") return;
    const raw = u.searchParams.get("cust_params");
    if (!raw) return;
    const params = {};
    new URLSearchParams(raw).forEach((v, k) => { params[k] = v; });
    _imaCaptures.set(details.tabId, { cust_params: params });
  } catch (e) {}
}, _IMA_URL_FILTER);


// ---------------------------------------------------------------------------
// Test files to inject (order matters — warnings_init last before runner)
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

// ---------------------------------------------------------------------------
// Readiness poller — injected into the page. Self-contained (no closures).
// Phase 1: wait for pbjs + display events (up to 15s).
// Phase 2: if pageType === "video", also wait for video events (up to 15s).
// Returns "ready_video" on video pages so background.js knows to wait for IMA.
// IMA capture itself is handled by webRequest in the service worker.
// ---------------------------------------------------------------------------
function pbjsReadinessPoller() {
  return new Promise((resolve) => {
    const MAX_DISPLAY = 15000;
    const MAX_VIDEO   = 15000;
    const INTERVAL    = 300;
    const start = Date.now();

    function hasPbjs()    { return !!(window.pbjs && Array.isArray(window.pbjs.que)); }
    function hasDisplay() { return (window.__pbjsBidEventsDisplay || []).length > 0; }
    function hasVideo()   { return (window.__pbjsBidEventsVideo   || []).length > 0; }
    function getPageType() {
      try {
        var pt = window.googletag && googletag.pubads && googletag.pubads().getTargeting("pageType");
        return pt && pt[0] ? String(pt[0]).toLowerCase() : "";
      } catch (e) { return ""; }
    }

    function waitVideo() {
      var vs = Date.now();
      function poll() {
        if (hasVideo()) return resolve("ready_video");
        if (Date.now() - vs > MAX_VIDEO) return resolve("timeout_video");
        setTimeout(poll, INTERVAL);
      }
      poll();
    }

    function check() {
      if (hasPbjs() && hasDisplay()) {
        return getPageType() === "video" ? waitVideo() : resolve("ready");
      }
      if (Date.now() - start > MAX_DISPLAY) return resolve("timeout");
      setTimeout(check, INTERVAL);
    }

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
    const [pollerResult] = await chrome.scripting.executeScript({
      target: { tabId },
      world: "MAIN",
      func: pbjsReadinessPoller,
    });

    // On video pages, wait up to 10s for the IMA request to be captured
    if (pollerResult?.result === "ready_video") {
      const imaDeadline = Date.now() + 10000;
      while (!_imaCaptures.has(tabId) && Date.now() < imaDeadline) {
        await new Promise((r) => setTimeout(r, 300));
      }
    }

    // If we captured an IMA request, inject it into the page before tests run
    const imaData = _imaCaptures.get(tabId) ?? null;
    await chrome.scripting.executeScript({
      target: { tabId },
      world: "MAIN",
      func: (data) => { window.__imaAdRequest = data; },
      args: [imaData],
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

// Clear stored results and IMA capture when a tab navigates away
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo) => {
  if (changeInfo.status !== "loading") return;
  _imaCaptures.delete(tabId);
  await chrome.storage.local.remove(`tab_${tabId}`);
  chrome.action.setBadgeText({ tabId, text: "" });
});

// Clean up when tab closes
chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.local.remove(`tab_${tabId}`);
  _imaCaptures.delete(tabId);
});

// Allow popup to request IMA capture data for re-runs
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "getImaCapture") {
    sendResponse(_imaCaptures.get(msg.tabId) ?? null);
  }
  return false;
});

