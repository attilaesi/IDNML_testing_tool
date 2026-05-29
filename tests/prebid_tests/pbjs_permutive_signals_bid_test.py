# tests/prebid_tests/pbjs_permutive_signals_bid_test.py
"""
prebid: PbjsPermutiveSignalsBidTest

What this test checks
---------------------
Inspects outgoing Prebid bidder requests (RTB payload) to verify that Permutive RTD
signals are present for required bidders: ix, rubicon, msft, pubmatic.

Signals validated per required bidder:
  - user.ext.data.p_standard   (array of standard cohort IDs)
  - user.ext.data.permutive    (array of custom cohort IDs)
  - user.keywords              (contains p_standard=..., p_standard_aud=..., permutive=...)

Test conditions
---------------
- window.pbjs must be present (otherwise skipped).
- At least one required bidder must have made requests (otherwise skipped).

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: all required bidders that made requests have the expected Permutive signal paths
  present with non-empty values.
- FAILED: a required bidder made requests but is missing one or more Permutive signal paths.
- SKIPPED: window.pbjs missing, no bidder requests found, or none of the required bidders
  made requests (e.g. non-display page).
"""

from typing import Dict, List, Any

from core.base_test import BaseTest, TestResult, TestState

class PbjsPermutiveSignalsBidTest(BaseTest):

    """Checks Permutive signals inside bid requests."""

    # Only these bidders are validated
    REQUIRED_BIDDERS: List[str] = [ "ix", "rubicon", "msft", "pubmatic"]

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

    PERMUTIVE_EXPECTATIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
        bidder: {
            "user.ext.data.p_standard": {"required": True},
            "user.ext.data.permutive": {"required": True},
            "user.keywords": {
                "required": True,
                "tokens_all": ["p_standard=", "p_standard_aud=", "permutive="],
            },
        }
        for bidder in REQUIRED_BIDDERS
    }

    # --- Token match helpers ---

    @staticmethod
    def _sample_has_token(sample: List[str], token: str) -> bool:
        if not sample:
            return False

        token = token.lower()
        for raw in sample:
            txt = str(raw).lower()

            if token in ("permutive", "p_standard", "p_standard_aud"):
                if token in txt:
                    return True
            else:
                if token in txt:
                    return True

        return False

    # --- Setup ---

    async def setup(self, page, url: str) -> bool:
        return bool(await page.evaluate("() => !!window.pbjs"))

    # --- Execute ---

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        required_bidders_js = self.REQUIRED_BIDDERS  # baked into js string below

        js = f"""
        () => {{
          const w = window;

          const REQUIRED = {required_bidders_js};

          const diag = {{
            hasPbjs: !!w.pbjs,
            totalRequests: 0,

            // useful for downstream reporting clarity
            requiredBidders: REQUIRED,
            biddersSeen: [],
            ignoredBidders: [],

            // we still capture all bidders for debugging
            perBidder: {{}},

            // convenience filtered view: only required bidders
            perBidderRequired: {{}},

            debug: {{
              eventsLen: 0,
              eventTypes: [],
              rawEventsSample: []
            }}
          }};

          const events = Array.isArray(w.__pbjsBidEvents) ? w.__pbjsBidEvents : [];

          diag.debug.eventsLen = events.length;
          diag.debug.eventTypes = Array.from(new Set(events.map(e => e && e.type).filter(Boolean)));

          diag.debug.rawEventsSample = events.slice(0, 3).map(e => ({{
            type: e && e.type,
            hasArgs: !!(e && e.args),
            bidderCode: e && e.args && (e.args.bidderCode || e.args.bidder || null),
            bidsLen: e && e.args && Array.isArray(e.args.bids) ? e.args.bids.length : 0
          }}));

          if (!events.length) return diag;

          const requests = events
            .filter(e => e && e.type === "bidRequested" && e.args)
            .map(e => e.args);

          diag.totalRequests = requests.length;

          const ensureBidder = (code) => {{
            if (!diag.perBidder[code]) {{
              const emptyPaths = {{
                "site.ext.permutive": {{ seen: false, sample: [] }},
                "site.ext.permutive.p_standard": {{ seen: false, sample: [] }},
                "user.ext.data.p_standard": {{ seen: false, sample: [] }},
                "user.ext.data.permutive": {{ seen: false, sample: [] }},
                "user.data[0].name": {{ seen: false, sample: [] }},
                "user.data[1].name": {{ seen: false, sample: [] }},
                "user.keywords": {{ seen: false, sample: [] }}
              }};
              diag.perBidder[code] = {{
                requestCount: 0,
                paths: emptyPaths
              }};
            }}
            return diag.perBidder[code];
          }};

          const normaliseValueToSample = (value) => {{
            if (value == null) return [];
            const out = [];
            const pushVal = (v) => {{
              if (v == null) return;
              try {{ out.push(String(v)); }} catch (e) {{}}
            }};

            if (Array.isArray(value)) {{
              value.forEach(pushVal);
            }} else if (typeof value === "object") {{
              Object.values(value).forEach(v => {{
                if (typeof v === "string" || typeof v === "number") pushVal(v);
              }});
            }} else {{
              pushVal(value);
            }}

            return out.slice(0, 200);
          }};

          const recordPath = (bidder, path, value) => {{
            const b = ensureBidder(bidder);
            if (!value) return;
            const sample = normaliseValueToSample(value);
            if (!sample.length) return;

            const info = b.paths[path];
            if (!info) return;

            info.seen = true;
            const existing = Array.isArray(info.sample) ? info.sample : [];
            info.sample = existing.concat(sample).slice(0, 400);
          }};

          requests.forEach(req => {{
            const bidder = req.bidderCode || req.bidder || "unknown";
            const b = ensureBidder(bidder);
            b.requestCount += 1;

            const bidsArr = Array.isArray(req.bids) ? req.bids : [];
            let ortb2 = {{}};
            if (bidsArr.length && bidsArr[0] && bidsArr[0].ortb2) {{
              ortb2 = bidsArr[0].ortb2 || {{}};
            }} else {{
              ortb2 = req.ortb2 || {{}};
            }}

            const site = ortb2.site || {{}};
            const siteExt = site.ext || {{}};
            const sitePerm = siteExt.permutive;

            const user = ortb2.user || {{}};
            const userExt = user.ext || {{}};
            const extData = userExt.data || {{}};
            const userData = Array.isArray(user.data) ? user.data : [];
            const userKeywordsRaw = user.keywords;

            if (sitePerm) {{
              recordPath(bidder, "site.ext.permutive", sitePerm);
              if (sitePerm && sitePerm.p_standard) {{
                recordPath(bidder, "site.ext.permutive.p_standard", sitePerm.p_standard);
              }}
            }}

            // p_standard is the canonical key; pstandard (no underscore) is a known
            // mis-casing seen in some Permutive adapter versions — accept both.
            if (Array.isArray(extData.p_standard) || Array.isArray(extData.pstandard)) {{
              const ps = Array.isArray(extData.p_standard) ? extData.p_standard : extData.pstandard;
              recordPath(bidder, "user.ext.data.p_standard", ps);
            }}

            if (extData.permutive) {{
              recordPath(bidder, "user.ext.data.permutive", extData.permutive);
            }}

            if (userData[0] && userData[0].name) recordPath(bidder, "user.data[0].name", userData[0].name);
            if (userData[1] && userData[1].name) recordPath(bidder, "user.data[1].name", userData[1].name);

            if (Array.isArray(userKeywordsRaw)) {{
              recordPath(bidder, "user.keywords", userKeywordsRaw);
            }} else if (typeof userKeywordsRaw === "string") {{
              const split = userKeywordsRaw.split(/[\\s,]+/).filter(Boolean);
              recordPath(bidder, "user.keywords", split);
            }}
          }});

          diag.biddersSeen = Object.keys(diag.perBidder || {{}});
          diag.ignoredBidders = diag.biddersSeen.filter(b => !REQUIRED.includes(b));

          // build filtered view
          REQUIRED.forEach(b => {{
            if (diag.perBidder[b]) diag.perBidderRequired[b] = diag.perBidder[b];
          }});

          return diag;
        }}
        """

        diag = await page.evaluate(js)
        result.data = diag or {}

        if self.config.get("trace"):
            print(
                "[PbjsPermutiveSignalsBidTest] execute diag summary: "
                + f'hasPbjs={bool(diag.get("hasPbjs"))}, '
                + f'totalRequests={diag.get("totalRequests", 0)}, '
                + f"requiredBidders={(diag.get('requiredBidders') or [])}, "
                + f"biddersSeen={(diag.get('biddersSeen') or [])}, "
                + f"ignoredBidders={(diag.get('ignoredBidders') or [])}"
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

        # If none of the required bidders appear at all, skip (clearer than a wall of SKIPPED lines)
        if not any((per_bidder.get(b) or {}).get("requestCount", 0) > 0 for b in self.REQUIRED_BIDDERS):
            result.state = TestState.SKIPPED
            result.warnings.append("No requests for required bidders: " + ", ".join(self.REQUIRED_BIDDERS))
            return result

        any_fail = False
        summary: List[str] = []

        for bidder in self.REQUIRED_BIDDERS:
            info = per_bidder.get(bidder)
            if not info or info.get("requestCount", 0) == 0:
                summary.append(f"{bidder}: SKIPPED (no requests)")
                continue

            failures: List[str] = []
            passes: List[str] = []

            expectations = self.PERMUTIVE_EXPECTATIONS.get(bidder, {})
            paths_info = info.get("paths", {}) or {}

            for path, rules in expectations.items():
                path_obs = paths_info.get(path, {}) or {}
                seen = bool(path_obs.get("seen"))
                sample = path_obs.get("sample") or []

                required = bool(rules.get("required"))
                tokens_all: List[str] = rules.get("tokens_all") or []
                tokens_any: List[str] = rules.get("tokens_any") or []

                path_failures: List[str] = []

                if required and not seen:
                    path_failures.append("missing")
                elif seen:
                    if tokens_all:
                        missing = [t for t in tokens_all if not self._sample_has_token(sample, t)]
                        if missing:
                            path_failures.append(f"missing tokens {', '.join(missing)}")

                    if tokens_any:
                        if not any(self._sample_has_token(sample, t) for t in tokens_any):
                            path_failures.append(f"no tokens from {', '.join(tokens_any)}")

                if path_failures:
                    failures.append(f"{path}: {'; '.join(path_failures)}")
                else:
                    # mark as present / passing only if the check actually succeeded
                    if seen:
                        passes.append(path)

            if failures:
                any_fail = True
                if passes:
                    summary.append(
                        f"{bidder}: FAIL ({'; '.join(failures)}; present: {', '.join(passes)})"
                    )
                else:
                    summary.append(f"{bidder}: FAIL ({'; '.join(failures)})")
            else:
                if passes:
                    summary.append(f"{bidder}: PASS ({', '.join(passes)})")
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