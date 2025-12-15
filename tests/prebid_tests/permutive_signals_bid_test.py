# tests/prebid_tests/permutive_signals_bid_test.py
"""
prebid: PermutiveSignalsBidTest

Checks outgoing Prebid bidder requests for Permutive RTD signals for:
  - appnexus
  - ix
  - pubmatic
  - rubicon

We inspect the bidder *requests* (RTB payload) rather than Prebid config.

The signals we care about (per bidder) are:

  - user.ext.data.p_standard      (array of standard cohort IDs)
  - user.ext.data.permutive       (array of custom cohort IDs)
  - user.keywords                 (comma/space separated string or array
                                   containing p_standard=..., p_standard_aud=...,
                                   and permutive=... entries)
"""

from typing import Dict, List, Any

from core.base_test import BaseTest, TestResult, TestState


class PermutiveSignalsBidTest(BaseTest):
    """Checks Permutive signals inside bid requests."""

    # ONLY these 4 bidders
    REQUIRED_BIDDERS: List[str] = ["appnexus", "ix", "pubmatic", "rubicon"]

    # ORTB2 paths we inspect and record into diag
    PATH_KEYS: List[str] = [
        "site.ext.permutive",
        "site.ext.permutive.p_standard",
        "user.ext.data.p_standard",
        "user.ext.data.permutive",
        "user.data[0].name",
        "user.data[1].name",
        "user.keywords",
    ]

    # Expectations by bidder — same rules for all 4.
    #
    # For each bidder:
    #   - user.ext.data.p_standard must be present & non-empty
    #   - user.ext.data.permutive must be present & non-empty
    #   - user.keywords must contain:
    #         p_standard=...
    #         p_standard_aud=...
    #         permutive=...
    #
    # NOTE: Pubmatic currently does NOT send user.ext.data.permutive in production,
    # so this test will (correctly) FAIL for pubmatic and you can treat that as
    # an expected / known failure when reviewing results.
    PERMUTIVE_EXPECTATIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
        bidder: {
            "user.ext.data.p_standard": {
                "required": True,
            },
            "user.ext.data.permutive": {
                "required": True,  # pubmatic will fail this today
            },
            "user.keywords": {
                "required": True,
                # Need at least one of each:
                #   p_standard=...
                #   p_standard_aud=...
                #   permutive=...
                "tokens_all": ["p_standard=", "p_standard_aud=", "permutive="],
            },
        }
        for bidder in ["appnexus", "ix", "pubmatic", "rubicon"]
    }

    # --- Token match helpers ---

    @staticmethod
    def _sample_has_token(sample: List[str], token: str) -> bool:
        """
        Very forgiving token matcher. Normalises everything to lowercase and
        treats e.g. "p_standard_aud=foo" as satisfying "p_standard_aud=".
        """
        if not sample:
            return False

        token = token.lower()
        for raw in sample:
            txt = str(raw).lower()

            if token == "permutive":
                if "permutive" in txt:
                    return True
            elif token == "p_standard":
                if "p_standard" in txt:
                    return True
            elif token == "p_standard_aud":
                if "p_standard_aud" in txt:
                    return True
            elif token == "p_standard=":
                if "p_standard=" in txt:
                    return True
            elif token == "p_standard_aud=":
                if "p_standard_aud=" in txt:
                    return True
            elif token == "permutive=":
                if "permutive=" in txt:
                    return True
            else:
                if token in txt:
                    return True

        return False

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

          // store small sample of first few events for tracing
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
                "site.ext.permutive": { seen: false, sample: [] },
                "site.ext.permutive.p_standard": { seen: false, sample: [] },
                "user.ext.data.p_standard": { seen: false, sample: [] },
                "user.ext.data.permutive": { seen: false, sample: [] },
                "user.data[0].name": { seen: false, sample: [] },
                "user.data[1].name": { seen: false, sample: [] },
                "user.keywords": { seen: false, sample: [] }
              };
              diag.perBidder[code] = {
                requestCount: 0,
                paths: emptyPaths
              };
            }
            return diag.perBidder[code];
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
                if (typeof v === "string" || typeof v === "number") {
                  pushVal(v);
                }
              });
            } else {
              pushVal(value);
            }

            return out.slice(0, 200);
          };

          const recordPath = (bidder, path, value) => {
            const b = ensureBidder(bidder);
            if (!value) return;
            const sample = normaliseValueToSample(value);
            if (!sample.length) return;

            const info = b.paths[path];
            if (!info) return;

            info.seen = true;
            const existing = Array.isArray(info.sample) ? info.sample : [];
            info.sample = existing.concat(sample).slice(0, 400);
          };

          if (!requests.length) {
            return diag;
          }

          // Walk each bidRequested args -> bids[0].ortb2.*
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
            const sitePerm = siteExt.permutive;

            const user = ortb2.user || {};
            const userExt = user.ext || {};
            const extData = userExt.data || {};
            const userData = Array.isArray(user.data) ? user.data : [];
            const userKeywordsRaw = user.keywords;

            // site.ext.permutive
            if (sitePerm) {
              recordPath(bidder, "site.ext.permutive", sitePerm);
              if (sitePerm && sitePerm.p_standard) {
                recordPath(
                  bidder,
                  "site.ext.permutive.p_standard",
                  sitePerm.p_standard
                );
              }
            }

            // user.ext.data.p_standard / pstandard
            if (Array.isArray(extData.p_standard) || Array.isArray(extData.pstandard)) {
              const ps = Array.isArray(extData.p_standard)
                ? extData.p_standard
                : extData.pstandard;
              recordPath(bidder, "user.ext.data.p_standard", ps);
            }

            // user.ext.data.permutive
            if (extData.permutive) {
              recordPath(bidder, "user.ext.data.permutive", extData.permutive);
            }

            // user.data[0].name / user.data[1].name
            if (userData[0] && userData[0].name) {
              recordPath(bidder, "user.data[0].name", userData[0].name);
            }
            if (userData[1] && userData[1].name) {
              recordPath(bidder, "user.data[1].name", userData[1].name);
            }

            // user.keywords (string or array)
            if (Array.isArray(userKeywordsRaw)) {
              recordPath(bidder, "user.keywords", userKeywordsRaw);
            } else if (typeof userKeywordsRaw === "string") {
              const split = userKeywordsRaw.split(/[\\s,]+/).filter(Boolean);
              recordPath(bidder, "user.keywords", split);
            }
          });

          return diag;
        }
        """

        diag = await page.evaluate(js)
        result.data = diag or {}

        if self.config.get("trace"):
            # High-level summary
            print(
                "[PermutiveSignalsBidTest] execute diag summary: "
                + f'hasPbjs={bool(diag.get("hasPbjs"))}, '
                + f'totalRequests={diag.get("totalRequests", 0)}, '
                + f'eventsLen={(diag.get("debug") or {}).get("eventsLen", 0)}, '
                + f'eventTypes={(diag.get("debug") or {}).get("eventTypes", [])}'
            )

            # Per-bidder quick view: requestCount + first few samples for user.ext.data.*
            per_bidder = (diag.get("perBidder") or {})
            for bidder, info in per_bidder.items():
                paths = info.get("paths") or {}

                def s(path):
                    p = paths.get(path) or {}
                    return {
                        "seen": bool(p.get("seen")),
                        "sample": (p.get("sample") or [])[:5],
                    }

                print(
                    f"[PermutiveSignalsBidTest] bidder={bidder}, "
                    f"requests={info.get('requestCount', 0)}, "
                    f"user.ext.data.p_standard={s('user.ext.data.p_standard')}, "
                    f"user.ext.data.permutive={s('user.ext.data.permutive')}, "
                    f"user.keywords={s('user.keywords')}"
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
        any_fail = False
        summary: List[str] = []

        for bidder in self.REQUIRED_BIDDERS:
            info = per_bidder.get(bidder)
            if not info or info.get("requestCount", 0) == 0:
                summary.append(f"{bidder}: SKIPPED (no requests)")
                continue

            failures: List[str] = []
            expectations = self.PERMUTIVE_EXPECTATIONS.get(bidder, {})
            paths_info = info.get("paths", {}) or {}

            for path, rules in expectations.items():
                path_obs = paths_info.get(path, {}) or {}
                seen = bool(path_obs.get("seen"))
                sample = path_obs.get("sample") or []

                required = bool(rules.get("required"))
                must_be_missing = bool(rules.get("must_be_missing"))
                tokens_all: List[str] = rules.get("tokens_all") or []
                tokens_any: List[str] = rules.get("tokens_any") or []

                # missing required
                if required and not seen:
                    failures.append(f"{path}: missing")
                    continue

                # should NOT exist
                if must_be_missing and seen:
                    failures.append(f"{path}: present but should be absent")
                    continue

                # nothing else to do if we didn't see it
                if not seen:
                    continue

                # token checks
                if tokens_all:
                    missing = [
                        t for t in tokens_all
                        if not self._sample_has_token(sample, t)
                    ]
                    if missing:
                        failures.append(
                            f"{path}: missing tokens {', '.join(missing)}"
                        )
                        continue

                if tokens_any:
                    if not any(self._sample_has_token(sample, t) for t in tokens_any):
                        failures.append(
                            f"{path}: no tokens from {', '.join(tokens_any)}"
                        )
                        continue

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