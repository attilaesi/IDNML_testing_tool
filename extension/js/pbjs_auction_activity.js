window.__adTests = window.__adTests || {};
window.__adTests["pbjs_auction_activity"] = () => {
    const out = {
        source: null,  // "__pbjsBidEvents" | "pbjs.getBidResponsesForAdUnitCode"
        adUnits_with_responses: [],
        total_bid_responses: 0,
        winning_bids: [],
        errors: [],
        debug: {
          eventsLen: 0,
          eventTypes: [],
          bidRequestedCount: 0,
          bidResponseCount: 0
        }
    };

    const w = window;
    const pbjs = w.pbjs;

    if (!pbjs) {
        out.errors.push("window.pbjs is not defined");
        return out;
    }

    try {
        const events = Array.isArray(w.__pbjsBidEvents)
          ? w.__pbjsBidEvents
          : [];

        out.debug.eventsLen = events.length;
        out.debug.eventTypes = Array.from(
          new Set(events.map(e => e && e.type).filter(Boolean))
        );

        const bidRequestedEvents = events.filter(
          e => e && e.type === "bidRequested" && e.args
        );
        const bidRespEvents = events.filter(
          e => e && e.type === "bidResponse" && e.args
        );

        out.debug.bidRequestedCount = bidRequestedEvents.length;
        out.debug.bidResponseCount = bidRespEvents.length;

        // ---- primary: bidResponse events ----
        if (bidRespEvents.length) {
            out.source = "__pbjsBidEvents";

            const perAdUnit = new Map();

            bidRespEvents.forEach(ev => {
                const b = ev.args || {};
                const code = b.adUnitCode || b.adUnitCode;
                if (!code) return;

                let entry = perAdUnit.get(code);
                if (!entry) {
                    entry = { code, bids: [] };
                    perAdUnit.set(code, entry);
                }
                entry.bids.push(b);
            });

            const adUnits_with_responses = [];
            let total = 0;

            perAdUnit.forEach(({ code, bids }) => {
                const bidders = bids
                  .map(b => b && b.bidder)
                  .filter(Boolean);
                adUnits_with_responses.push({
                    code,
                    bidCount: bids.length,
                    bidders
                });
                total += bids.length;
            });

            out.adUnits_with_responses = adUnits_with_responses;
            out.total_bid_responses = total;
        }
    } catch (e) {
        out.errors.push("error reading __pbjsBidEvents: " + String(e));
    }

    // ---------------------------------------------
    // FALLBACK: pbjs.getBidResponsesForAdUnitCode
    // ---------------------------------------------
    if (!out.total_bid_responses) {
        try {
            if (typeof pbjs.getBidResponsesForAdUnitCode !== "function") {
                out.errors.push("pbjs.getBidResponsesForAdUnitCode is not available");
            } else {
                const adUnits = Array.isArray(pbjs.adUnits) ? pbjs.adUnits : [];
                const adUnits_with_responses = [];
                let total = 0;

                adUnits.forEach((unit) => {
                    const code = unit.code || unit.adUnitCode;
                    if (!code) return;

                    const resp = pbjs.getBidResponsesForAdUnitCode(code) || {};
                    const bids = Array.isArray(resp.bids) ? resp.bids : [];

                    if (bids.length > 0) {
                        adUnits_with_responses.push({
                            code,
                            bidCount: bids.length,
                            bidders: bids
                                .map(b => b && b.bidder)
                                .filter(Boolean)
                        });
                        total += bids.length;
                    }
                });

                if (total > 0) {
                    out.source = "pbjs.getBidResponsesForAdUnitCode";
                    out.adUnits_with_responses = adUnits_with_responses;
                    out.total_bid_responses = total;
                }
            }
        } catch (e) {
            out.errors.push("fallback extraction error: " + String(e));
        }
    }

    // --------------------
    // Winning bids (PBJS)
    // --------------------
    try {
        if (typeof pbjs.getAllWinningBids === "function") {
            const wins = pbjs.getAllWinningBids() || [];
            out.winning_bids = wins.map((b) => ({
                adUnitCode: b && b.adUnitCode,
                bidder: b && b.bidder,
                cpm: b && b.cpm,
                currency: b && b.currency
            }));
        }
    } catch (e) {
        out.errors.push("getAllWinningBids error: " + String(e));
    }

    return out;
}
;
