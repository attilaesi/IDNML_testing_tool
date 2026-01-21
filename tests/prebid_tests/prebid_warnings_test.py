import re
from typing import Any, Dict, List

from core.base_test import BaseTest, TestResult, TestState


class PrebidWarningsTest(BaseTest):
    name = "PrebidWarningsTest"

    FAIL_PATTERN = "invalid bid sent to bidder"

    WAIT_AFTER_TRIGGER_MS = 5000

    # Trace controls
    TRACE_FAILING_ONLY = True
    TRACE_FAILING_LINE_LEN = 900         # truncate failing line in trace
    TRACE_FULL_FAILING_LINES = False     # True = print full failing lines (no truncation)
    TRACE_MAX_FAILING_LINES = 10         # max failing lines to print in trace

    MAX_TOTAL_MATCHED_LINES = 50         # safety cap

    # Regex helpers for extracting adslot/gpid from the invalid-bid payload
    AD_SLOT_RE = re.compile(r'"adslot"\s*:\s*"([^"]+)"', re.IGNORECASE)
    GPID_RE = re.compile(r'"gpid"\s*:\s*"([^"]+)"', re.IGNORECASE)

    def _clean_console_line(self, text: str) -> str:
        """
        Remove Prebid %c styling noise and compress whitespace to make lines readable.
        Works on both:
          "%cPrebid ... INFO: ..."
          "%cPrebid%ccriteo ... WARNING: ..."
        """
        try:
            t = (text or "").strip()

            # Normalize the common styled prefix patterns
            t = t.replace("%cPrebid%c", "Prebid ")
            t = t.replace("%cPrebid% c", "Prebid ")  # defensive (rare spacing)
            t = t.replace("%cPrebid", "Prebid")

            # Some bidder-tagged logs look like "%cPrebid%cttd ..." -> make it "Prebid ttd ..."
            t = re.sub(r"%cPrebid%c([a-zA-Z0-9_\-]+)\s*", r"Prebid \1 ", t)

            # Strip CSS chunks that appear inline in our capture
            # (Keep these broad; they’re only used for readability.)
            t = re.sub(r"(display:\s*inline-block;[^;]*;?)", "", t, flags=re.IGNORECASE)
            t = re.sub(r"(color:\s*#[0-9a-fA-F]{3,6};?)", "", t, flags=re.IGNORECASE)
            t = re.sub(r"(background:\s*#[0-9a-fA-F]{3,6};?)", "", t, flags=re.IGNORECASE)
            t = re.sub(r"(padding:\s*[^;]+;?)", "", t, flags=re.IGNORECASE)
            t = re.sub(r"(border-radius:\s*[^;]+;?)", "", t, flags=re.IGNORECASE)

            # Also remove leftover "; ; ;" / extra punctuation spacing
            t = re.sub(r"\s*;\s*", "; ", t)

            # Collapse whitespace
            t = re.sub(r"\s+", " ", t).strip()
            return t
        except Exception:
            return (text or "").strip()

    def _extract_bidder(self, line: str) -> str:
        """
        Extract bidder from the *invalid bid* line:
          "... Invalid bid sent to bidder criteo: {...}"
        """
        try:
            l = line or ""
            ll = l.lower()
            marker = self.FAIL_PATTERN
            idx = ll.find(marker)
            if idx == -1:
                return "unknown"
            after = (l[idx + len(marker) :] or "").strip()
            if not after:
                return "unknown"
            tok = after.split(":")[0].split()[0].strip()
            cleaned = "".join(ch for ch in tok if ch.isalnum() or ch in ("_", "-")).strip()
            return cleaned or "unknown"
        except Exception:
            return "unknown"

    def _extract_adslots(self, line: str) -> List[str]:
        """
        Extract GAM adslot(s) from the invalid-bid payload.
        Prefer `"adslot":"..."` (ortb2Imp.ext.data.adserver.adslot),
        fallback to `"gpid":"..."` if adslot not present.
        Returns unique list in stable order.
        """
        try:
            t = line or ""
            found: List[str] = []

            for m in self.AD_SLOT_RE.finditer(t):
                s = (m.group(1) or "").strip()
                if s and s not in found:
                    found.append(s)

            # If we didn't find adslot, try gpid (often equals adunit path)
            if not found:
                for m in self.GPID_RE.finditer(t):
                    s = (m.group(1) or "").strip()
                    if s and s not in found:
                        found.append(s)

            return found
        except Exception:
            return []

    async def setup(self, page, url: str) -> bool:
        try:
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        # Init: enable debug + hook console (page-scoped)
        init = await page.evaluate(
            """
            (() => {
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
            """
        )

        # Wait for forced auction to log warnings
        try:
            await page.wait_for_timeout(self.WAIT_AFTER_TRIGGER_MS)
        except Exception:
            pass

        raw_logs: List[Dict[str, Any]] = await page.evaluate("window.__prebidWarningLogs || []")
        raw_logs = raw_logs or []

        # Clean lines for matching / readability
        cleaned_logs: List[Dict[str, Any]] = []
        for m in raw_logs:
            cleaned_logs.append(
                {
                    "level": (m or {}).get("level") or "unknown",
                    "text": self._clean_console_line((m or {}).get("text") or ""),
                    "ts": (m or {}).get("ts"),
                }
            )

        # Find failing lines (cleaned matching)
        failing: List[Dict[str, Any]] = []
        for m in cleaned_logs:
            t = (m.get("text") or "")
            if self.FAIL_PATTERN in t.lower():
                failing.append(m)

        failing = failing[: self.MAX_TOTAL_MATCHED_LINES]

        # Group by bidder (counts + keep representative lines)
        by_bidder: Dict[str, List[str]] = {}
        adslots_by_bidder: Dict[str, List[str]] = {}

        for m in failing:
            line = m.get("text") or ""
            bidder = self._extract_bidder(line)

            by_bidder.setdefault(bidder, []).append(line)

            # collect unique adslots per bidder
            slots = self._extract_adslots(line)
            if slots:
                adslots_by_bidder.setdefault(bidder, [])
                for s in slots:
                    if s not in adslots_by_bidder[bidder]:
                        adslots_by_bidder[bidder].append(s)

        matched_by_bidder = {
            k: len(v) for k, v in sorted(by_bidder.items(), key=lambda x: (-len(x[1]), x[0]))
        }

        # If a bidder has no extracted slots, keep it explicit
        adslots_by_bidder_final: Dict[str, List[str]] = {}
        for bidder in matched_by_bidder.keys():
            slots = adslots_by_bidder.get(bidder) or []
            adslots_by_bidder_final[bidder] = slots

        diag: Dict[str, Any] = {
            "url": url,
            "debugEnabled": bool((init or {}).get("debugEnabled")),
            "prebidMessagesTotal": len(cleaned_logs),
            "matchedCount": len(failing),
            "matchedByBidder": matched_by_bidder,
            "invalidBidAdslotsByBidder": adslots_by_bidder_final,
            # keep full failing lines for validate() / reporting decisions
            "failingLines": failing,  # list of {level,text,ts}
            "init": init,
        }

        result.data = diag

        if self.config.get("trace"):
            # Print only failing lines, cleaned + truncated
            to_print = failing if self.TRACE_FAILING_ONLY else cleaned_logs
            to_print = to_print[: self.TRACE_MAX_FAILING_LINES]

            formatted = []
            for m in to_print:
                lvl = (m.get("level") or "unknown").upper()
                line = m.get("text") or ""
                if not self.TRACE_FULL_FAILING_LINES and len(line) > self.TRACE_FAILING_LINE_LEN:
                    line = line[: self.TRACE_FAILING_LINE_LEN] + "…"
                formatted.append(f"[{lvl}] {line}")

            print(
                "[PrebidWarningsTest] execute diag:",
                {
                    "url": url,
                    "debugEnabled": diag["debugEnabled"],
                    "prebidMessagesTotal": diag["prebidMessagesTotal"],
                    "matchedCount": diag["matchedCount"],
                    "matchedByBidder": diag["matchedByBidder"],
                    "invalidBidAdslotsByBidder": diag["invalidBidAdslotsByBidder"],
                    "failingLines": formatted,
                    "init": init,
                },
            )

        return result

    async def validate(self, result: TestResult) -> TestResult:
        diag: Dict[str, Any] = result.data or {}
        init = diag.get("init") or {}

        if not init.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.warnings.append("pbjs not present on page; cannot run PrebidWarningsTest.")
            return result

        matched_by_bidder: Dict[str, int] = diag.get("matchedByBidder") or {}
        adslots_by_bidder: Dict[str, List[str]] = diag.get("invalidBidAdslotsByBidder") or {}

        if matched_by_bidder:
            result.state = TestState.FAILED

            # ✅ Roundup-friendly single line: bidder (+ adslots if found)
            parts: List[str] = []
            for bidder in sorted(matched_by_bidder.keys()):
                slots = adslots_by_bidder.get(bidder) or []
                if slots:
                    parts.append(f"{bidder} -> {', '.join(slots)}")
                else:
                    parts.append(f"{bidder}")

            result.errors.append("Invalid bids: " + " | ".join(parts))
        else:
            result.state = TestState.PASSED

        result.metadata.update(
            {
                "prebid_messages_total": diag.get("prebidMessagesTotal", 0),
                "matched_count": int(diag.get("matchedCount") or 0),
                "invalid_bids_by_bidder": matched_by_bidder,
                "invalid_bid_adslots_by_bidder": adslots_by_bidder,
                "adUnitsCount": init.get("adUnitsCount", 0),
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return