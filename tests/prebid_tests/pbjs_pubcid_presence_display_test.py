from core.base_test import BaseTest, TestResult, TestState


class PbjsDisplayPubcidPresenceTest(BaseTest):
    NORMALIZED_NAME = "pbjs_pubcid_presence_display_test"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = self.NORMALIZED_NAME

    """
    Validate PubCommonId (pubcid) for DISPLAY auctions only.

    Rule:
      PASS only if *every bidder* that appears in DISPLAY bidRequested bids
      has pubcid present in at least one of its bids.

    In-scope bidders:
      - derived from bids in window.__pbjsBidEventsDisplay (type="bidRequested")

    pubcid can be present via:
      a) bid.userId.pubCommonId   (string or {id:"..."} shape)
      OR
      b) bid.userIdAsEids contains an eid whose source hints pubcommon/pubcid
         and has at least one uid.id.

    FAIL:
      - pbjs exists but no DISPLAY bidRequested events captured
      - OR at least one DISPLAY bidder missing pubcid

    SKIP:
      - window.pbjs missing
    """

    name = "PbjsDisplayPubcidPresenceTest"

    async def setup(self, page, url: str) -> bool:
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        data = await page.evaluate(
            """
            () => {
              const out = {
                hasPbjs: !!window.pbjs,
                pbjsVersion: (window.pbjs && window.pbjs.version) || null,

                store: "__pbjsBidEventsDisplay",
                eventsLen: 0,
                bidRequestedEvents: 0,
                bidsScanned: 0,

                biddersSeen: [],
                biddersWithPubcid: [],
                biddersMissingPubcid: [],

                // per-bidder diagnostics (lightweight)
                perBidder: {}, // bidder -> { firstAdUnitCode, found, foundVia, examplePubcid }
              };

              const events = Array.isArray(window.__pbjsBidEventsDisplay)
                ? window.__pbjsBidEventsDisplay
                : [];

              out.eventsLen = events.length;

              const bidReqEvents = events.filter(e => e && e.type === "bidRequested");
              out.bidRequestedEvents = bidReqEvents.length;

              const getPubcidFromUserId = (userId) => {
                try {
                  if (!userId || typeof userId !== "object") return null;
                  const v = userId.pubCommonId;
                  if (!v) return null;
                  if (typeof v === "string") return v;
                  if (typeof v === "object" && v.id) return String(v.id);
                  return null;
                } catch (e) { return null; }
              };

              const getPubcidFromEids = (eids) => {
                try {
                  if (!Array.isArray(eids)) return null;
                  for (const eid of eids) {
                    if (!eid || typeof eid !== "object") continue;
                    const src = String(eid.source || "").toLowerCase();
                    const hint = src.includes("pubcommon") || src.includes("pubcid");
                    if (!hint) continue;
                    const uids = Array.isArray(eid.uids) ? eid.uids : [];
                    for (const u of uids) {
                      if (u && typeof u === "object" && u.id) {
                        return { source: eid.source || null, id: String(u.id) };
                      }
                    }
                  }
                  return null;
                } catch (e) { return null; }
              };

              const ensureBidder = (bidder, adUnitCode) => {
                if (!bidder) return;
                if (!out.perBidder[bidder]) {
                  out.perBidder[bidder] = {
                    firstAdUnitCode: adUnitCode || null,
                    found: false,
                    foundVia: null,
                    examplePubcid: null
                  };
                }
              };

              for (const ev of bidReqEvents) {
                const args = ev.args || {};
                const bids = Array.isArray(args.bids) ? args.bids : [];
                for (const b of bids) {
                  out.bidsScanned += 1;

                  const bidder = b && b.bidder;
                  if (!bidder) continue;

                  ensureBidder(bidder, b && b.adUnitCode);

                  // If we already found pubcid for this bidder, do NOT keep scanning its bids
                  if (out.perBidder[bidder].found) continue;

                  // Check pubcid via userId.pubCommonId
                  const v1 = getPubcidFromUserId(b && b.userId);
                  if (v1) {
                    out.perBidder[bidder].found = true;
                    out.perBidder[bidder].foundVia = "userId.pubCommonId";
                    out.perBidder[bidder].examplePubcid = v1;
                    continue;
                  }

                  // Check pubcid via userIdAsEids
                  const v2 = getPubcidFromEids(b && b.userIdAsEids);
                  if (v2) {
                    out.perBidder[bidder].found = true;
                    out.perBidder[bidder].foundVia = "userIdAsEids";
                    out.perBidder[bidder].examplePubcid = v2.id;
                    continue;
                  }
                }
              }

              const bidders = Object.keys(out.perBidder);
              out.biddersSeen = bidders;

              for (const bidder of bidders) {
                if (out.perBidder[bidder].found) out.biddersWithPubcid.push(bidder);
                else out.biddersMissingPubcid.push(bidder);
              }

              return out;
            }
            """
        )

        result.data = {
            "hasPbjs": data.get("hasPbjs"),
            "pbjsVersion": data.get("pbjsVersion"),
            "store": data.get("store"),
            "eventsLen": data.get("eventsLen"),
            "bidRequestedEvents": data.get("bidRequestedEvents"),
            "bidsScanned": data.get("bidsScanned"),
            "biddersSeen": data.get("biddersSeen"),
            "biddersWithPubcid": data.get("biddersWithPubcid"),
            "biddersMissingPubcid": data.get("biddersMissingPubcid"),
            # keep perBidder small; still useful for debugging
            "perBidder": data.get("perBidder"),
        }

        if not data.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.errors.append("window.pbjs not found; cannot validate pubcid in display bids.")
            return result

        if int(data.get("bidRequestedEvents") or 0) == 0:
            result.state = TestState.FAILED
            result.errors.append("No DISPLAY bidRequested events captured; cannot confirm pubcid for display bidders.")
            return result

        missing = data.get("biddersMissingPubcid") or []
        if missing:
            result.state = TestState.FAILED
            result.errors.append(f"pubcid missing for DISPLAY bidders: {', '.join(missing)}")
            return result

        result.state = TestState.PASSED
        return result

    async def validate(self, result: TestResult) -> TestResult:
        return result

    async def cleanup(self, page, url: str) -> None:
        return