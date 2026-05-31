(function () {
  try {
    // ------------------------------------------------------------
    // Prebid event stores
    // ------------------------------------------------------------
    window.__pbjsBidEvents = window.__pbjsBidEvents || [];                 // legacy: combined
    window.__pbjsBidEventsDisplay = window.__pbjsBidEventsDisplay || [];   // display stream (everything NOT hero_player)
    window.__pbjsBidEventsVideo = window.__pbjsBidEventsVideo || [];       // hero_player stream only

    // Tiny meta snapshot to help verification/debugging.
    window.__pbjsBidEventStoresMeta = window.__pbjsBidEventStoresMeta || {
      displayCount: 0,
      videoCount: 0,
      last: null
    };

    // Prevent double-hooking on repeated navigations in the same context
    window.__pbjsEventHooked = window.__pbjsEventHooked || false;

    const HERO_CODES = new Set(["hero_player"]);

    const norm = (x) => {
      try { return (x == null ? "" : String(x)).trim().toLowerCase(); }
      catch (e) { return ""; }
    };

    const isHeroCode = (code) => HERO_CODES.has(norm(code));

    const isHeroBidLike = (bid) => {
      try {
        if (!bid) return false;
        const adUnitCode = norm(bid.adUnitCode || bid.code);
        return isHeroCode(adUnitCode);
      } catch (e) {
        return false;
      }
    };

    const isHeroAdUnitLike = (u) => {
      try {
        if (!u) return false;
        const code = norm(u.code || u.adUnitCode);
        return isHeroCode(code);
      } catch (e) {
        return false;
      }
    };

    const classifyEventStream = (type, args) => {
      try {
        if (!type) return "display";

        if (type === "bidRequested" && args) {
          const bids = Array.isArray(args.bids) ? args.bids : [];
          return bids.some(isHeroBidLike) ? "video" : "display";
        }

        if (type === "auctionInit" && args) {
          const aus = Array.isArray(args.adUnits) ? args.adUnits : [];
          return aus.some(isHeroAdUnitLike) ? "video" : "display";
        }

        if (type === "auctionEnd" && args) {
          const aus = Array.isArray(args.adUnits) ? args.adUnits : [];
          if (aus.some(isHeroAdUnitLike)) return "video";

          const bidsRec = Array.isArray(args.bidsReceived) ? args.bidsReceived : [];
          if (bidsRec.some(isHeroBidLike)) return "video";
        }

        if ((type === "bidResponse" || type === "bidWon") && args) {
          return isHeroBidLike(args) ? "video" : "display";
        }
      } catch (e) {
        // ignore
      }
      return "display";
    };

    const pushEvent = (ev) => {
      try {
        window.__pbjsBidEvents.push(ev);

        if (ev.stream === "video") {
          window.__pbjsBidEventsVideo.push(ev);
          window.__pbjsBidEventStoresMeta.videoCount += 1;
        } else {
          window.__pbjsBidEventsDisplay.push(ev);
          window.__pbjsBidEventStoresMeta.displayCount += 1;
        }

        window.__pbjsBidEventStoresMeta.last = {
          type: ev.type,
          stream: ev.stream,
          t: Date.now()
        };
      } catch (e) {
        // ignore
      }
    };

    const hookPbjs = () => {
      try {
        if (!window.pbjs || typeof window.pbjs.onEvent !== "function") return false;
        if (window.__pbjsEventHooked) return true;

        window.__pbjsEventHooked = true;

        const eventsToHook = [
          "auctionInit",
          "bidRequested",
          "bidResponse",
          "bidWon",
          "auctionEnd",
        ];

        eventsToHook.forEach((type) => {
          try {
            window.pbjs.onEvent(type, function (args) {
              const stream = classifyEventStream(type, args);
              pushEvent({
                type,
                stream,
                args,
                ts: Date.now(),
              });
            });
          } catch (e) {
            // ignore
          }
        });

        return true;
      } catch (e) {
        return false;
      }
    };

    if (!hookPbjs()) {
      let tries = 0;
      const maxTries = 60;
      const t = setInterval(() => {
        tries++;
        if (hookPbjs() || tries >= maxTries) {
          clearInterval(t);
        }
      }, 250);
    }

    // ----------------------------------------------------------------
    // Console hook — captures Prebid log messages for warnings test.
    // Runs at document_start so we catch messages from the page's own
    // auction without triggering a second requestBids() call.
    // ----------------------------------------------------------------
    window.__prebidWarningLogs = window.__prebidWarningLogs || [];

    if (!window.__prebidWarningsHooked) {
      window.__prebidWarningsHooked = true;

      const safeStr = (v) => {
        try {
          if (v == null) return String(v);
          if (typeof v === "string") return v;
          if (typeof v === "number" || typeof v === "boolean") return String(v);
          if (v instanceof Error) return v.stack || v.message || String(v);
          try { return JSON.stringify(v); } catch (_) { return String(v); }
        } catch (_) { return "[unserializable]"; }
      };

      ["log", "warn", "error", "info", "debug"].forEach((level) => {
        try {
          const orig = console[level];
          if (typeof orig !== "function") return;
          console[level] = function () {
            try {
              const text = Array.prototype.slice.call(arguments).map(safeStr).join(" ");
              if (text.indexOf("Prebid") !== -1) {
                window.__prebidWarningLogs.push({ level, text, ts: Date.now() });
                if (window.__prebidWarningLogs.length > 3000) {
                  window.__prebidWarningLogs.splice(0, window.__prebidWarningLogs.length - 3000);
                }
              }
            } catch (_) {}
            return orig.apply(console, arguments);
          };
        } catch (_) {}
      });
    }

  } catch (e) {
    // ignore top-level errors
  }
})();
