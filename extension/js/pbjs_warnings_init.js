window.__adTests = window.__adTests || {};
window.__adTests["pbjs_warnings_init"] = (() => {
  const diag = {
    ok: false,
    reason: null,
    debugEnabled: false,
    hooked: false,
    hasPbjs: !!window.pbjs,
    hasGoogletag: !!window.googletag,
    adUnitsCount: 0
  };

  if (!window.pbjs || typeof window.pbjs.setConfig !== 'function') {
    diag.reason = 'pbjs_missing';
    return diag;
  }

  try {
    window.pbjs.setConfig({ debug: true });
    diag.debugEnabled = true;
  } catch (e) {
    diag.debugEnabled = true;
  }

  window.__prebidWarningLogs = window.__prebidWarningLogs || [];

  if (!window.__prebidWarningsHooked) {
    window.__prebidWarningsHooked = true;
    diag.hooked = true;

    const LEVELS = ["log","warn","error","info","debug"];

    const safeToString = (v) => {
      try {
        if (v === undefined) return "undefined";
        if (v === null) return "null";
        if (typeof v === "string") return v;
        if (typeof v === "number" || typeof v === "boolean") return String(v);
        if (v instanceof Error) return v.stack || v.message || String(v);
        try { return JSON.stringify(v); } catch (e) { return String(v); }
      } catch (e) {
        return "[unserializable]";
      }
    };

    const looksLikePrebid = (fullText) => {
      try {
        const t = String(fullText || "");
        return t.indexOf("Prebid") !== -1;
      } catch (e) { return false; }
    };

    LEVELS.forEach((level) => {
      try {
        const orig = console[level];
        if (typeof orig !== "function") return;

        console[level] = function () {
          try {
            const args = Array.prototype.slice.call(arguments);
            const text = args.map(safeToString).join(" ");
            if (looksLikePrebid(text)) {
              window.__prebidWarningLogs.push({ level, text, ts: Date.now() });
              if (window.__prebidWarningLogs.length > 3000) {
                window.__prebidWarningLogs.splice(0, window.__prebidWarningLogs.length - 3000);
              }
            }
          } catch (e) {}
          return orig.apply(console, arguments);
        };
      } catch (e) {}
    });
  }

  // Force DISPLAY activity (requestBids)
  const adUnits = Array.isArray(window.pbjs.adUnits) ? window.pbjs.adUnits : [];
  diag.adUnitsCount = adUnits.length;

  const doGptRefresh = () => {
    try {
      if (window.googletag && Array.isArray(window.googletag.cmd)) {
        window.googletag.cmd.push(() => {
          try {
            if (googletag.pubads && typeof googletag.pubads().refresh === "function") {
              googletag.pubads().refresh();
            }
          } catch (e) {}
        });
      }
    } catch (e) {}
  };

  if (adUnits.length && typeof window.pbjs.requestBids === "function") {
    try {
      window.pbjs.requestBids({
        adUnits,
        timeout: 1500,
        bidsBackHandler: function () {
          try {
            if (typeof window.pbjs.setTargetingForGPTAsync === "function") {
              window.pbjs.setTargetingForGPTAsync();
            }
          } catch (e) {}
          doGptRefresh();
        }
      });
    } catch (e) {
      doGptRefresh();
    }
  } else {
    diag.reason = diag.reason || "no_adunits_or_requestbids_missing";
  }

  diag.ok = true;
  return diag;
})();
;
