() => {
  try {
    if (!window.googletag || !googletag.pubads) {
      return { hasGpt: false };
    }

    // --- Prebid: extract hb_* keys from auctionEnd bidsReceived ---
    // auctionEnd fires after all bids are in and winners determined.
    // On video pages the event may be routed to __pbjsBidEventsVideo
    // (if the auction contains hero_player), so check both stores.
    const allEvents = (window.__pbjsBidEventsDisplay || [])
      .concat(window.__pbjsBidEventsVideo || []);
    const auctionEndEvents = allEvents
      .filter(function(ev) { return ev && ev.type === "auctionEnd"; });

    const prebidKeys = [];
    let bidsReceivedCount = 0;
    auctionEndEvents.forEach(function(ev) {
      const bids = (ev.args && ev.args.bidsReceived) || [];
      bidsReceivedCount += bids.length;
      bids.forEach(function(bid) {
        Object.keys(bid.adserverTargeting || {}).forEach(function(k) {
          if (k.startsWith("hb_") && !prebidKeys.includes(k)) prebidKeys.push(k);
        });
      });
    });

    // --- TAM: check page-level AND slot-level targeting for amzn* keys ---
    const tamKeys = [];
    try {
      const pageKeys = googletag.pubads().getTargetingKeys() || [];
      pageKeys.forEach(function(k) {
        if (k.startsWith("amzn") && !tamKeys.includes(k)) tamKeys.push(k);
      });
    } catch(e) {}
    try {
      const slots = googletag.pubads().getSlots() || [];
      slots.forEach(function(slot) {
        (slot.getTargetingKeys() || []).forEach(function(k) {
          if (k.startsWith("amzn") && !tamKeys.includes(k)) tamKeys.push(k);
        });
      });
    } catch(e) {}

    return {
      hasGpt: true,
      auctionEndCount: auctionEndEvents.length,
      bidsReceivedCount: bidsReceivedCount,
      prebidKeys: prebidKeys,
      tamKeys: tamKeys,
      hasPrebid: prebidKeys.length > 0,
      hasTam: tamKeys.length > 0,
    };
  } catch (e) {
    return { error: String(e) };
  }
}
