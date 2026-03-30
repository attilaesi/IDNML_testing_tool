# tests/prebid_tests/pbjs_mantis_signals_bid_test.py
"""
prebid: PbjsMantisSignalsBidTest

Checks outgoing Prebid bidder requests for Mantis signals.

We inspect bidder *requests* (RTB payload) rather than Prebid config.

Paths inspected (per bidder request):
  - site.ext.data.mantis
  - site.ext.data.mantis_context

Option C (strict validation):
  - Both paths must exist for each bidder that made requests
  - Both must be arrays
  - Both must be non-empty
  - mantis entries must match: <label>-<GREEN|AMBER|RED>
  - mantis_context entries must match: lowercase snake_case tokens
"""

from typing import List, Any, Dict
import re

from core.base_test import BaseTest, TestResult, TestState

class PbjsMantisSignalsBidTest(BaseTest):

    # ORTB2 paths we inspect and record into diag
    PATH_KEYS: List[str] = [
        "site.ext.data.mantis",
        "site.ext.data.mantis_context",
    ]

    # Expectations (same rules for all bidders)
    EXPECTATIONS: Dict[str, Dict[str, Any]] = {
        "site.ext.data.mantis": {"required": True},
        "site.ext.data.mantis_context": {"required": True},
    }

    # Strict patterns (Option C)
    _MANTIS_ENTRY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*-(GREEN|AMBER|RED)$")
    _MANTIS_CONTEXT_ENTRY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

    # --- Setup ---

    async def setup(self, page, url: str) -> bool:
        has_pbjs = await page.evaluate("() => !!window.pbjs")
        return bool(has_pbjs)

    # --- Execute ---

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        js = """
        () => {
          const w = window;

          const diag = {
            hasPbjs: !!w.pbjs,
            totalRequests: 0,
            biddersSeen: [],
            perBidder: {},
            debug: {
              eventsLen: 0,
              eventTypes: [],
              rawEventsSample: []
            }
          };

          const events = Array.isArray(w.__pbjsBidEvents)
            ? w.__pbjsBidEvents
            : [];

          diag.debug.eventsLen = events.length;
          diag.debug.eventTypes = Array.from(
            new Set(events.map(e => e && e.type).filter(Boolean))
          );

          diag.debug.rawEventsSample = events.slice(0, 3).map(e => ({
            type: e && e.type,
            hasArgs: !!(e && e.args),
            bidderCode: e && e.args && (e.args.bidderCode || e.args.bidder || null),
            bidsLen: e && e.args && Array.isArray(e.args.bids) ? e.args.bids.length : 0
          }));

          if (!events.length) {
            return diag;
          }

          // treat each bidRequested event's args as a bidderRequest-like object
          const requests = events
            .filter(e => e && e.type === "bidRequested" && e.args)
            .map(e => e.args);

          diag.totalRequests = requests.length;

          const ensureBidder = (code) => {
            if (!diag.perBidder[code]) {
              const emptyPaths = {
                "site.ext.data.mantis": { seen: false, type: null, count: 0, sample: [] },
                "site.ext.data.mantis_context": { seen: false, type: null, count: 0, sample: [] }
              };
              diag.perBidder[code] = {
                requestCount: 0,
                paths: emptyPaths
              };
            }
            return diag.perBidder[code];
          };

          const getType = (v) => {
            if (v == null) return "null";
            if (Array.isArray(v)) return "array";
            return typeof v;
          };

          const normaliseValueToSample = (value) => {
            if (value == null) return [];
            const out = [];
            const pushVal = (v) => {
              if (v == null) return;
              try { out.push(String(v)); } catch (e) {}
            };

            if (Array.isArray(value)) {
              value.forEach(pushVal);
            } else if (typeof value === "object") {
              Object.values(value).forEach(v => {
                if (Array.isArray(v)) {
                  v.forEach(pushVal);
                } else if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
                  pushVal(v);
                }
              });
            } else {
              pushVal(value);
            }

            return out.slice(0, 400);
          };

          const recordPath = (bidder, path, value) => {
            const b = ensureBidder(bidder);
            const info = b.paths[path];
            if (!info) return;

            const present = value != null;
            info.seen = present;
            info.type = present ? getType(value) : "null";

            if (Array.isArray(value)) {
              info.count = value.length;
            } else {
              info.count = 0;
            }

            if (!present) return;

            const sample = normaliseValueToSample(value);
            const existing = Array.isArray(info.sample) ? info.sample : [];
            info.sample = existing.concat(sample).slice(0, 800);
          };

          if (!requests.length) {
            return diag;
          }

          // Walk each bidRequested args -> bids[0].ortb2.site.ext.data.*
          requests.forEach(req => {
            const bidder = req.bidderCode || req.bidder || "unknown";
            const b = ensureBidder(bidder);
            b.requestCount += 1;

            const bidsArr = Array.isArray(req.bids) ? req.bids : [];
            let ortb2 = {};
            if (bidsArr.length && bidsArr[0] && bidsArr[0].ortb2) {
              ortb2 = bidsArr[0].ortb2 || {};
            } else {
              ortb2 = req.ortb2 || {};
            }

            const site = ortb2.site || {};
            const siteExt = site.ext || {};
            const data = (siteExt && siteExt.data) ? siteExt.data : {};

            recordPath(bidder, "site.ext.data.mantis", data ? data.mantis : null);
            recordPath(bidder, "site.ext.data.mantis_context", data ? data.mantis_context : null);
          });

          diag.biddersSeen = Object.keys(diag.perBidder || {});
          return diag;
        }
        """

        diag = await page.evaluate(js)
        result.data = diag or {}

        if self.config.get("trace"):
            print(
                "[PbjsMantisSignalsBidTest] execute diag summary: "
                + f'hasPbjs={bool(diag.get("hasPbjs"))}, '
                + f'totalRequests={diag.get("totalRequests", 0)}, '
                + f"biddersSeen={(diag.get('biddersSeen') or [])}, "
                + f'eventsLen={(diag.get("debug") or {}).get("eventsLen", 0)}, '
                + f'eventTypes={(diag.get("debug") or {}).get("eventTypes", [])}'
            )

            per_bidder = (diag.get("perBidder") or {})
            for bidder, info in per_bidder.items():
                paths = info.get("paths") or {}

                def s(path):
                    p = paths.get(path) or {}
                    return {
                        "seen": bool(p.get("seen")),
                        "type": p.get("type"),
                        "count": p.get("count"),
                        "sample": (p.get("sample") or [])[:10],
                    }

                print(
                    f"[PbjsMantisSignalsBidTest] bidder={bidder}, "
                    f"requests={info.get('requestCount', 0)}, "
                    f"mantis={s('site.ext.data.mantis')}, "
                    f"mantis_context={s('site.ext.data.mantis_context')}"
                )

        return result

    # --- Validate ---

    async def validate(self, result: TestResult) -> TestResult:
        diag = result.data or {}

        if not diag.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.warnings.append("pbjs not present")
            return result

        if diag.get("totalRequests", 0) == 0:
            result.state = TestState.SKIPPED
            result.warnings.append("No bidder requests found")
            return result

        per_bidder = diag.get("perBidder", {}) or {}
        bidders = list(per_bidder.keys())

        if not bidders:
            result.state = TestState.SKIPPED
            result.warnings.append("No bidders found in requests")
            return result

        any_fail = False
        summary: List[str] = []

        def _validate_array(path_name: str, obs: Dict[str, Any]) -> List[str]:
            """Structural checks for Option C."""
            errs: List[str] = []
            seen = bool(obs.get("seen"))
            typ = obs.get("type")
            count = int(obs.get("count") or 0)

            if not seen:
                errs.append(f"{path_name}: missing")
                return errs

            if typ != "array":
                errs.append(f"{path_name}: wrong type (expected array, got {typ})")
                return errs

            if count <= 0:
                errs.append(f"{path_name}: empty array")
                return errs

            return errs

        # Tests ALL bidders observed
        for bidder in sorted(bidders):
            info = per_bidder.get(bidder) or {}
            if info.get("requestCount", 0) == 0:
                summary.append(f"{bidder}: SKIPPED (no requests)")
                continue

            failures: List[str] = []
            paths_info = info.get("paths", {}) or {}

            mantis_obs = paths_info.get("site.ext.data.mantis", {}) or {}
            mantis_ctx_obs = paths_info.get("site.ext.data.mantis_context", {}) or {}

            # 1) Presence + type(array) + non-empty
            failures.extend(_validate_array("site.ext.data.mantis", mantis_obs))
            failures.extend(_validate_array("site.ext.data.mantis_context", mantis_ctx_obs))

            # 2) Pattern validation (only if structural checks passed)
            if not failures:
                mantis_vals = [str(x) for x in (mantis_obs.get("sample") or []) if str(x)]
                mantis_ctx_vals = [str(x) for x in (mantis_ctx_obs.get("sample") or []) if str(x)]

                bad_mantis = [v for v in mantis_vals if not self._MANTIS_ENTRY_RE.match(v)]
                bad_ctx = [v for v in mantis_ctx_vals if not self._MANTIS_CONTEXT_ENTRY_RE.match(v)]

                if bad_mantis:
                    failures.append(
                        "site.ext.data.mantis: invalid entries (sample) -> "
                        + ", ".join(bad_mantis[:10])
                        + (" ..." if len(bad_mantis) > 10 else "")
                    )

                if bad_ctx:
                    failures.append(
                        "site.ext.data.mantis_context: invalid entries (sample) -> "
                        + ", ".join(bad_ctx[:10])
                        + (" ..." if len(bad_ctx) > 10 else "")
                    )

            if failures:
                any_fail = True
                summary.append(f"{bidder}: FAIL ({'; '.join(failures)})")
            else:
                summary.append(f"{bidder}: PASS")

        if any_fail:
            result.state = TestState.FAILED
            result.errors.append("FAILED\n" + "\n".join(summary))
        else:
            result.state = TestState.PASSED
            result.warnings.append("PASSED\n" + "\n".join(summary))

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return