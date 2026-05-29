# core/framework_manager.py

import asyncio
import sys
from collections import defaultdict
from typing import List, Dict, Type, Optional
from urllib.parse import urlparse

from core.readiness_waiter import ReadinessWaiter
from core.base_test import BaseTest, TestResult, TestState, _to_snake
from core.browser_manager import BrowserManager
from core.device_helpers import device_label, is_mobile_viewport
from core.cmp_handler import CMPHandler
from core.url_context_helpers import (
    map_pagetype_to_db,
    publisher_from_url,
    env_from_url,
)
from core.ansi import colour_cell, colour_state, dim

from config.site_test_plans import SITE_TEST_PLANS

from core.framework.discovery import discover_tests, get_tests_by_category


class TestFramework:
    def __init__(self, config: Dict):
        self.config = config
        self.tests: Dict[str, Type[BaseTest]] = {}
        self.test_categories: Dict[str, List[str]] = {}
        self.browser_manager = BrowserManager(config)
        self.cmp_handler = CMPHandler(config)

        # Hold onto a warmup page so we can reuse it for tests
        self._warm_page = None

        # Keep URL order for the session (so matrix cols are stable)
        self.selected_urls: List[str] = []

    # ------------- URL helpers -------------

    def _is_preprod_url(self, url: str) -> bool:
        """
        Preprod environments should behave the same for:
          - UAT (uat/feat/dev)
          - staging (staging)
        """
        u = (url or "").lower()
        return any(t in u for t in ("uat", "feat", "dev", "staging"))

    def _publisher_from_url(self, url: str) -> str:
        result = publisher_from_url(url)
        if result == "unknown":
            return str(self.config.get("active_site", "independent")).lower()
        return result

    def _add_basic_auth_to_url(self, url: str) -> str:
        """
        IMPORTANT:
        Do NOT inject credentials into the URL (demo:review@...).

        It breaks JS on staging (History.replaceState / fetch), because the page tries
        to manipulate the URL without credentials, which becomes cross-origin / invalid.

        Basic auth is now handled via Playwright context http_credentials.
        """
        return url

    async def _set_context_cookies(self, page, url: str) -> None:
        """
        Set cookies BEFORE navigation.

        For UAT / FEAT / DEV only (NOT staging):
          - feature flag cookies from config['preprod_cookies']

        Note:
          - is_mobile_or_tablet is set for UAT/FEAT/DEV only (not staging, not live).
            Live and staging set it themselves from UA/viewport.
            The environment test verifies it is present and correct on all environments.
        """
        is_mobile = device_label(self.config) == "mobile"
        preprod_cookies = self.config.get("preprod_cookies", [])
        light_ad_rules = self.config.get("light_ad_rules", None)  # True / False / None

        raw = url or self.config.get("site_url", "")
        parsed = urlparse(raw if raw else "https://www.independent.co.uk")
        host = parsed.hostname or "www.independent.co.uk"
        domain = host  # host-only cookie

        raw_l = (raw or "").lower()

        # UAT/FEAT/DEV get feature-flag cookies; STAGING does not.
        # Also treat "independent_feat" active_site as UAT-like (branch names vary).
        is_uat_like = (
            any(tok in raw_l for tok in ("uat", "feat", "dev"))
            or self.config.get("active_site", "") == "independent_feat"
        )
        is_staging = "staging" in raw_l
        apply_preprod_cookies = is_uat_like and not is_staging

        cookies = []

        if apply_preprod_cookies and preprod_cookies:
            for base_cookie in preprod_cookies:
                c = dict(base_cookie)  # shallow copy
                c.setdefault("domain", domain)  # apply current host if not set
                cookies.append(c)

        # Preprod only: set is_mobile_or_tablet from viewport so the site behaves
        # as if device detection already ran. Live/staging set this themselves.
        if apply_preprod_cookies:
            cookies.append({
                "name": "is_mobile_or_tablet",
                "value": "true" if is_mobile_viewport(self.config) else "false",
                "domain": domain,
                "path": "/",
            })

        if light_ad_rules is not None:
            cookies.append({
                "name": "feat__use_light_ad_rules",
                "value": "true" if light_ad_rules else "false",
                "domain": domain,
                "path": "/",
            })

        try:
            await page.context.add_cookies(cookies)
            print(
                f"🌍 Context cookies set (device={device_label(self.config)}, preprod_cookies={apply_preprod_cookies}): "
                f"{[c['name'] + '=' + c['value'] for c in cookies]}"
            )
        except Exception as e:
            print(f"⚠️ Failed to set context cookies: {e}")

    # ------------- Locale detection -------------

    async def _detect_locale(self, page) -> str:
        """
        Detect geo from the 'Locale' cookie.

        Expected values: "UK", "US" (case-insensitive).
        Falls back to "UK" if missing/unknown.
        """
        js = """
        () => {
          try {
            const cookies = document.cookie ? document.cookie.split(/;\\s*/) : [];
            for (const c of cookies) {
              const [name, ...rest] = c.split("=");
              if (!name) continue;
              if (name.trim() === "Locale") {
                const val = (rest.join("=") || "").trim();
                return val || null;
              }
            }
            return null;
          } catch (e) {
            return null;
          }
        }
        """
        val = await page.evaluate(js)
        if not val:
            return "UK"
        val = str(val).strip().upper()
        if val not in ("UK", "US"):
            return "UK"
        return val

    # ------------- PageType detection -------------

    async def _detect_page_type(self, page) -> str:
        """
        Poll GPT page-level targeting for pageType on googletag.pubads().

        Assumes ReadinessWaiter has already confirmed that GPT is up.
        """
        js = """
        () => {
          try {
            if (!window.googletag || !googletag.pubads) return null;
            const pubads = googletag.pubads();
            if (!pubads || !pubads.getTargeting) return null;

            const v = pubads.getTargeting("pageType");
            return (v && v[0]) || null;
          } catch (e) {
            return null;
          }
        }
        """

        timeout = max(float(self.config.get("page_type_timeout", 3.0)), 0.25)
        interval = 0.25
        elapsed = 0.0

        while elapsed < timeout:
            val = await page.evaluate(js)
            if val:
                return str(val).strip().lower()

            await asyncio.sleep(interval)
            elapsed += interval

        return "unknown"

    # ------------- Global context trace helpers -------------

    def _env_from_url(self, url: str) -> str:
        return env_from_url(url)

    async def _detect_liveblog(self, page) -> str:
        """
        Read GPT targeting key 'liveblog' (best-effort).
        """
        js = """
        () => {
          try {
            if (!window.googletag || !googletag.pubads) return "";
            const pubads = googletag.pubads();
            if (!pubads || !pubads.getTargeting) return "";
            const v = pubads.getTargeting("liveblog");
            return (v && v[0]) ? String(v[0]).toLowerCase() : "";
          } catch (e) {
            return "";
          }
        }
        """
        try:
            return (await page.evaluate(js)) or ""
        except Exception:
            return ""

    def _map_pagetype_to_db(self, page_type: str, liveblog: str) -> str:
        return map_pagetype_to_db(page_type, liveblog)

    async def _get_event_store_counts(self, page) -> Dict[str, int]:
        """
        Count events in display/video global stores so we can *verify* capture.
        """
        js = """
        () => {
          const d = Array.isArray(window.__pbjsBidEventsDisplay) ? window.__pbjsBidEventsDisplay : [];
          const v = Array.isArray(window.__pbjsBidEventsVideo) ? window.__pbjsBidEventsVideo : [];
          const dbr = d.filter(e => e && e.type === "bidRequested").length;
          const vbr = v.filter(e => e && e.type === "bidRequested").length;
          return {
            displayEvents: d.length,
            videoEvents: v.length,
            displayBidReq: dbr,
            videoBidReq: vbr
          };
        }
        """
        try:
            out = await page.evaluate(js)
            if isinstance(out, dict):
                return out
        except Exception:
            pass
        return {"displayEvents": 0, "videoEvents": 0, "displayBidReq": 0, "videoBidReq": 0}

    # ------------- Matrix helpers -------------

    def _short_hint(self, msg: object, max_len: int = 28) -> str:
        try:
            s = str(msg).strip()
        except Exception:
            return ""
        if not s:
            return ""
        s = s.splitlines()[0]
        return s[:max_len] + ("…" if len(s) > max_len else "")

    def _format_cell(self, state: TestState, errors, warnings) -> str:
        if state == TestState.PASSED:
            return "PASS"
        if state == TestState.SKIPPED:
            return "SKIP"
        if state == TestState.ERROR:
            hint = self._short_hint(errors[0]) if errors else ""
            return f"ERROR ({hint})" if hint else "ERROR"
        if state == TestState.FAILED:
            msgs = errors if errors else warnings
            hint = self._short_hint(msgs[0]) if msgs else ""
            return f"FAIL ({hint})" if hint else "FAIL"
        return str(state)

    def _print_matrix_summary(self, results: List[TestResult], urls: List[str]) -> None:
        """
        Boxed matrix with:
          - separator AFTER EVERY ROW
          - width caps
          - auto column-chunking based on terminal width (prevents wrapping like URL6 on left)
          - URL header includes (video|display|unknown)
        """
        import shutil

        if not urls:
            seen = set()
            urls = []
            for r in results:
                u = getattr(r, "url", None)
                if u and u not in seen:
                    seen.add(u)
                    urls.append(u)

        # ----------------------------
        # Determine page type per URL
        # ----------------------------
        url_page_type: Dict[str, str] = {}
        for r in results:
            u = getattr(r, "url", None)
            if not u or u in url_page_type:
                continue

            meta = getattr(r, "metadata", None) or {}
            pt = (meta.get("page_type") or "").strip().lower()

            if pt == "video":
                url_page_type[u] = "video"
            elif pt:
                # treat any non-video page_type as display for matrix scan purposes
                url_page_type[u] = "display"
            else:
                url_page_type[u] = "unknown"

        # URL labels (now include page type)
        url_labels_all = []
        for i, u in enumerate(urls, start=1):
            pt = url_page_type.get(u, "unknown")
            url_labels_all.append(f"URL{i} ({pt})")

        # Map URL -> label (must match the new labels above)
        url_to_label = {u: lbl for u, lbl in zip(urls, url_labels_all)}
        label_to_url = {lbl: u for u, lbl in zip(urls, url_labels_all)}  # kept in case you use later

        test_names = sorted({r.test_name for r in results if getattr(r, "test_name", None)})

        # Build matrix[test][URLx] = cell
        matrix = defaultdict(dict)
        for r in results:
            t = getattr(r, "test_name", None)
            u = getattr(r, "url", None)
            if not t or not u:
                continue
            lbl = url_to_label.get(u)
            if not lbl:
                continue
            matrix[t][lbl] = self._format_cell(
                r.state,
                getattr(r, "errors", None) or [],
                getattr(r, "warnings", None) or [],
            )

        # Width caps (tunable)
        max_test_col = int(self.config.get("matrix_max_test_width", 36) or 36)
        max_cell_col = int(self.config.get("matrix_max_cell_width", 22) or 22)

        def clip(s: str, max_len: int) -> str:
            s = str(s)
            if len(s) <= max_len:
                return s
            return s[: max_len - 1] + "…"

        # Terminal width → decide how many URL columns fit without wrapping
        term_width = shutil.get_terminal_size(fallback=(160, 40)).columns

        def estimated_table_width(num_url_cols: int) -> int:
            # pipes/spaces overhead is baked into +4 per col, conservative
            return 4 + (max_test_col + 3) + num_url_cols * (max_cell_col + 3) + (num_url_cols + 2)

        # Minimum 1 URL col per block
        max_cols = 1
        for n in range(1, len(url_labels_all) + 1):
            if estimated_table_width(n) <= term_width:
                max_cols = n
            else:
                break

        max_cols = max(1, max_cols)

        def print_block(block_labels: List[str], block_idx: int, total_blocks: int) -> None:
            header = ["Test"] + block_labels
            rows = [[t] + [matrix[t].get(lbl, "-") for lbl in block_labels] for t in test_names]

            # Compute widths for this block (still capped)
            widths = [len("Test")] + [len(h) for h in block_labels]
            for row in rows:
                widths[0] = min(max(widths[0], len(str(row[0]))), max_test_col)
                for i in range(1, len(row)):
                    widths[i] = min(max(widths[i], len(str(row[i]))), max_cell_col)

            def fmt_row(cols, is_header=False):
                out = []
                for i, c in enumerate(cols):
                    clipped = clip(c, widths[i])
                    if not is_header and i > 0:
                        # Pad based on visible length (before ANSI codes), then colorise
                        padding = " " * max(0, widths[i] - len(clipped))
                        padded = colour_cell(clipped) + padding
                    else:
                        padded = clipped.ljust(widths[i])
                    out.append(padded)
                return "| " + " | ".join(out) + " |"

            def sep(char: str = "-") -> str:
                parts = ["+" + (char * (w + 2)) for w in widths]
                return "".join(parts) + "+"

            title = "📊 TEST SUMMARY MATRIX (rows=tests, cols=URLs)"
            if total_blocks > 1:
                title += f"  [block {block_idx}/{total_blocks}]"

            # Compute actual table width from the separator (strip ANSI-safe)
            table_width = len(sep("-"))
            border = "=" * max(table_width, len(title))

            print("\n" + border)
            print(title)
            print(border)

            print(sep("-"))
            print(fmt_row(header, is_header=True))
            print(sep("="))
            for row in rows:
                print(fmt_row(row))
                print(sep("-"))

        # Chunk URL labels into blocks
        blocks = [
            url_labels_all[i:i + max_cols]
            for i in range(0, len(url_labels_all), max_cols)
        ]

        for idx, block in enumerate(blocks, start=1):
            print_block(block, idx, len(blocks))

        print("\nURL KEY")
        for i, u in enumerate(urls, start=1):
            pt = url_page_type.get(u, "unknown")
            print(f"URL{i} ({pt}) = {u}")    

    # ------------- Test discovery -------------

    def discover_tests(self) -> None:
        """
        Import test modules and collect classes that inherit BaseTest.
        Populates self.tests (name -> class) and self.test_categories (category -> [names]).
        """
        self.tests, self.test_categories = discover_tests()

    def get_tests_by_category(self, category: str) -> List[Type[BaseTest]]:
        """Get all tests in a specific category."""
        return get_tests_by_category(self.tests, self.test_categories, category)

    def create_test_instance(self, test_name: str) -> BaseTest:
        """Create instance of specific test."""
        if test_name in self.tests:
            return self.tests[test_name](self.config)
        raise ValueError(f"Test {test_name} not found")

    # ------------- URL selection -------------

    async def _get_selected_urls(self) -> List[str]:
        """
        Decide which URLs to test: now driven entirely by config['urls'].
        """
        urls = list(self.config.get("urls", []))
        if not urls:
            print("⚠️ No URLs configured. Check config/site_urls.py and base_config.py")

        print(
            f"🧭 Using {len(urls)} URLs from site profile "
            f"({self.config.get('active_site')})"
        )
        return urls

    # ------------- Warmup runner -------------

    async def _warmup_url(
        self,
        page,
        url: str,
        warm_idx: int,
        total_warm: int,
        handle_cmp: bool,
    ) -> None:
        """
        Warmup-only navigation:
        - basic auth
        - context cookies
        - CMP (optional, usually first warmup only)
        - wait for Prebid + GPT

        No tests are run and no results are recorded.
        """
        print(f"[WARMUP {warm_idx}/{total_warm}] {url}")

        auth_url = self._add_basic_auth_to_url(url)
        nav_timeout = int(self.config.get("timeout", 30000))

        try:
            await self._set_context_cookies(page, auth_url)
            await page.goto(auth_url, wait_until="domcontentloaded", timeout=nav_timeout)
        except Exception as e:
            print(f"[WARMUP {warm_idx}/{total_warm}] ⚠️  Skipped (navigation failed: {type(e).__name__})")
            return

        try:
            if handle_cmp:
                await self.cmp_handler.handle_consent(page)

            waiter = ReadinessWaiter(timeout=self.config.get("prebid_ready_timeout", 10))
            await waiter.wait_for_prebid_and_gpt(page)

            await page.evaluate("""
                async () => {
                    const delay = ms => new Promise(r => setTimeout(r, ms));
                    const total = document.body.scrollHeight;
                    const step = Math.max(600, Math.floor(total / 12));
                    for (let y = 0; y < total; y += step) {
                        window.scrollTo(0, y);
                        await delay(150);
                    }
                    window.scrollTo(0, total);
                    await delay(300);
                    window.scrollTo(0, 0);
                }
            """)
        except Exception as e:
            print(f"[WARMUP {warm_idx}/{total_warm}] ⚠️  Partial warmup (post-nav error: {type(e).__name__})")
            return

        print(f"[WARMUP {warm_idx}/{total_warm}] done")

    # ------------- Per-URL runner -------------

    async def _run_tests_for_url(
        self,
        page,
        url: str,
        test_classes: List[Type[BaseTest]],
        url_idx: int,
        total_urls: int,
        handle_cmp: bool,
        explicit_tests: bool = False,
    ) -> List[TestResult]:
        """
        Navigate to URL, prepare environment, run all tests, return results.

        Logs are printed directly to stdout so you can see activity as it happens.
        """
        print(f"[{url_idx}/{total_urls}] Processing {url}")

        # Inject credentials for UAT/DEV/feature branches/staging if needed
        auth_url = self._add_basic_auth_to_url(url)

        # Set device + preprod feature cookies before navigation
        await self._set_context_cookies(page, auth_url)

        # Navigate & wait for DOM
        nav_timeout = int(self.config.get("timeout", 30000))
        await page.goto(auth_url, wait_until="domcontentloaded", timeout=nav_timeout)

        # CMP only once per session / first URL (per mode)
        if handle_cmp:
            await self.cmp_handler.handle_consent(page)

        # Wait until pbjs & GPT are fully ready
        waiter = ReadinessWaiter(timeout=self.config.get("prebid_ready_timeout", 10))
        await waiter.wait_for_prebid_and_gpt(page)

        # Scroll through the full page to trigger lazy-loaded ad slots,
        # then return to top before tests run.
        await page.evaluate("""
            async () => {
                const delay = ms => new Promise(r => setTimeout(r, ms));
                const total = document.body.scrollHeight;
                const step = Math.max(600, Math.floor(total / 12));
                for (let y = 0; y < total; y += step) {
                    window.scrollTo(0, y);
                    await delay(150);
                }
                window.scrollTo(0, total);
                await delay(300);
                window.scrollTo(0, 0);
            }
        """)

        def _skipped_results(reason: str) -> List[TestResult]:
            results = []
            for cls in test_classes:
                r = TestResult(_to_snake(cls.__name__))
                r.url = url
                r.state = TestState.SKIPPED
                r.warnings.append(reason)
                results.append(r)
            return results

        # Skip bulletin pages — ad rules not defined yet.
        if "bulletin" in (url or "").lower():
            print(f"[{url_idx}/{total_urls}] ⏭️  Skipping bulletin page: {url}")
            return _skipped_results("Bulletin page — ad rules not defined; skipping all tests.")

        # Skip premium pages — not monetised, no ads to test.
        is_premium = await page.evaluate(
            "() => !!document.querySelector('path[fill=\"#337E81\"]')"
        )
        if is_premium:
            print(f"[{url_idx}/{total_urls}] ⏭️  Skipping premium page: {url}")
            return _skipped_results("Premium page — not monetised; skipping all tests.")

        # Detect page type from GPT key-values (with small polling window)
        page_type_norm = await self._detect_page_type(page)
        print(f"[{url_idx}/{total_urls}] 🧩 Detected page type: {page_type_norm}")

        # Detect locale from Locale cookie (UK / US)
        locale = await self._detect_locale(page)
        print(f"[{url_idx}/{total_urls}] 🗺️  Detected locale: {locale}")

        # ---- GLOBAL CONTEXT TRACE (one line per URL; very useful for bidder presence debugging) ----
        liveblog = await self._detect_liveblog(page)
        db_page_type = self._map_pagetype_to_db(page_type_norm, liveblog)
        env = self._env_from_url(auth_url or url)
        device = device_label(self.config)
        geo = (locale or "UK").strip().lower()
        publisher = self._publisher_from_url(auth_url or url)
        counts = await self._get_event_store_counts(page)

        context_summary = {
            "publisher": publisher,
            "env": env,
            "device": device,
            "geo": geo,
            "gpt_page_type": page_type_norm,
            "liveblog": (liveblog or "n/a"),
            "db_page_type": db_page_type,
            "displayEvents": counts.get("displayEvents", 0),
            "videoEvents": counts.get("videoEvents", 0),
            "displayBidReq": counts.get("displayBidReq", 0),
            "videoBidReq": counts.get("videoBidReq", 0),
        }

        tag = f"[{url_idx}/{total_urls}]"
        print(
            f"{tag} 🔎 {publisher}  env={env}  device={device}  geo={geo}"
            f"  page={page_type_norm}  db_page={db_page_type}  liveblog={(liveblog or 'n/a')}"
        )
        print(
            f"{tag}    events → display={counts.get('displayEvents')}  video={counts.get('videoEvents')}"
            f"  bidReq display={counts.get('displayBidReq')}  video={counts.get('videoBidReq')}"
        )

        # 🔸 Apply site test plan (inherit-all, then exclude by page type)
        # IMPORTANT: site plans are keyed by publisher, not by active_site variants
        # When tests are explicitly named (--test / --tests), bypass plan exclusions entirely.
        site_plan = SITE_TEST_PLANS.get(publisher, {})

        def _class_name(cls: Type[BaseTest]) -> str:
            return _to_snake(cls.__name__)

        # ENVIRONMENT tests are always exempt from site-plan exclusions
        env_test_names = set(
            _class_name(cls)
            for cls in self.get_tests_by_category("ENVIRONMENT")
        )

        if not explicit_tests and site_plan and site_plan.get("exclude") is not None:
            excluded_site = set(site_plan.get("exclude", []))
            exclude_map = site_plan.get("exclude_by_page_type", {}) or {}
            excluded_pt = set(exclude_map.get(page_type_norm, []))

            # Final disallowed set for this URL (env tests are never disallowed)
            disallowed = (excluded_site | excluded_pt) - env_test_names

            # Only instantiate / run tests that are allowed for this URL
            run_classes = [cls for cls in test_classes if _class_name(cls) not in disallowed]
        else:
            # No site plan -> run everything discovered
            run_classes = list(test_classes)

        url_results: List[TestResult] = []

        # --- progress helpers ---
        def _supports_inline_progress() -> bool:
            try:
                if not bool(self.config.get("progress_inline", True)):
                    return False
                return bool(getattr(sys.stdout, "isatty", lambda: False)())
            except Exception:
                return False

        inline = _supports_inline_progress()

        def _progress_start(prefix: str) -> None:
            if inline:
                try:
                    sys.stdout.write(prefix + "running..." + "\r")
                    sys.stdout.flush()
                    return
                except Exception:
                    pass
            print(prefix + "running...")

        def _progress_end(prefix: str, status: str) -> None:
            """
            Print final test status, then add spacing so the next test block doesn't
            visually run into this one.

            Toggle with config["trace_spacing_between_tests"] (default: True).
            """
            line = prefix + status

            # Default ON
            spacing = bool(self.config.get("trace_spacing_between_tests", True))

            if inline:
                try:
                    sys.stdout.write("\r\033[2K" + line + "\n")
                    sys.stdout.flush()
                    if spacing:
                        # One extra blank line => visible separation between tests
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                    return
                except Exception:
                    pass

            print(line)
            if spacing:
                print()  # blank line between tests

        # Run each test for this URL (fresh instance per class)
        for cls in run_classes:
            test_name = _class_name(cls)
            test = cls(self.config)

            test.locale = locale

            prefix = f"[{url_idx}/{total_urls}]   {test_name}: "
            _progress_start(prefix)

            try:
                result = await test.run(page, url)

                # Attach page_type, locale, device and GLOBAL CONTEXT TRACE into metadata
                result.device = self.config.get("device_key") or device_label(self.config)
                try:
                    if hasattr(result, "metadata"):
                        if result.metadata is None:
                            result.metadata = {}
                        if isinstance(result.metadata, dict):
                            result.metadata.setdefault("page_type", page_type_norm)
                            result.metadata.setdefault("locale", locale)
                            result.metadata.setdefault("context_summary", context_summary)
                except Exception:
                    pass

                url_results.append(result)
                _progress_end(prefix, colour_state(result.state.value))
                if result.state in (TestState.FAILED, TestState.ERROR):
                    msgs = result.errors if result.errors else result.warnings
                    if msgs:
                        first = str(msgs[0]).strip().splitlines()[0][:120]
                        print(dim(f"{'':>{len(prefix)}}  ↳ {first}"))
                elif result.state == TestState.SKIPPED:
                    msgs = result.warnings if result.warnings else result.errors
                    if msgs:
                        first = str(msgs[0]).strip().splitlines()[0][:120]
                        print(dim(f"{'':>{len(prefix)}}  ↳ {first}"))

            except Exception as e:
                err_result = TestResult(test_name)
                err_result.url = url
                err_result.device = self.config.get("device_key") or device_label(self.config)
                err_result.state = TestState.ERROR
                err_result.errors.append(str(e))
                try:
                    if hasattr(err_result, "metadata"):
                        if err_result.metadata is None:
                            err_result.metadata = {}
                        if isinstance(err_result.metadata, dict):
                            err_result.metadata.setdefault("page_type", page_type_norm)
                            err_result.metadata.setdefault("locale", locale)
                            err_result.metadata.setdefault("context_summary", context_summary)
                except Exception:
                    pass

                url_results.append(err_result)
                _progress_end(prefix, colour_state("error"))
                print(dim(f"{'':>{len(prefix)}}  ↳ {str(e).strip().splitlines()[0][:120]}"))

        left = total_urls - url_idx
        print(f"[{url_idx}/{total_urls}] done, {left} left")

        return url_results

    # ------------- Main runner -------------

    async def run_tests(
        self,
        test_names: Optional[List[str]] = None,
        category: str = None,
    ) -> List[TestResult]:
        """Run specified tests, using either single-page mode or parallel mode."""
        results: List[TestResult] = []

        # Which tests to run? (we build the full pool of *classes*; site plan is applied per URL)
        explicit_tests = bool(test_names)  # True when caller named specific tests
        if test_names:
            test_classes: List[Type[BaseTest]] = [self.tests[name] for name in test_names if name in self.tests]
        elif category:
            test_classes = self.get_tests_by_category(category)
        else:
            test_classes = list(self.tests.values())

        # Always prepend ENVIRONMENT tests so they run first.
        # They are exempt from site-plan exclusions (handled in _run_tests_for_url).
        env_classes = self.get_tests_by_category("ENVIRONMENT")
        env_class_set = set(id(cls) for cls in env_classes)
        # Remove env tests from their current position (if present), then prepend
        non_env = [cls for cls in test_classes if id(cls) not in env_class_set]
        test_classes = env_classes + non_env

        if not test_classes:
            print("No tests found to run")
            return results

        # Start browser / context
        await self.browser_manager.start()
        print(f"🛫 Browser launched (device = {device_label(self.config)}, viewport = {self.config.get('viewport')})")

        # Get URLs
        selected_urls = await self._get_selected_urls()
        self.selected_urls = list(selected_urls)  # preserve crawl order for matrix
        total_urls = len(selected_urls)
        print(f"▶️  Starting crawl: {total_urls} URLs (device={device_label(self.config)})")

        if total_urls == 0:
            print("⚠️ No URLs found to test (config['urls'] is empty).")
            await self.browser_manager.close()
            return results

        # ---------- Warmup phase ----------
        warmup_pages = int(self.config.get("warmup_pages", 0) or 0)
        warmup_pages = max(0, min(warmup_pages, total_urls))

        self._warm_page = None

        if warmup_pages > 0:
            print(f"🔥 Warmup phase: loading first {warmup_pages} URL(s) without running tests")
            self._warm_page = await self.browser_manager.new_page()
            for w_idx, w_url in enumerate(selected_urls[:warmup_pages], start=1):
                await self._warmup_url(
                    page=self._warm_page,
                    url=w_url,
                    warm_idx=w_idx,
                    total_warm=warmup_pages,
                    handle_cmp=(w_idx == 1),
                )
            print("🔥 Warmup phase complete.\n")

        parallel = self.config.get("parallel_tests", False)

        if not parallel:
            # -------- SINGLE-PAGE, SEQUENTIAL MODE --------
            if self._warm_page is not None:
                page = self._warm_page
                print("♻️ Reusing warmup page for main test run")
            else:
                page = await self.browser_manager.new_page()

            for url_idx, url in enumerate(selected_urls, start=1):
                url_results = await self._run_tests_for_url(
                    page=page,
                    url=url,
                    test_classes=test_classes,
                    url_idx=url_idx,
                    total_urls=total_urls,
                    handle_cmp=(url_idx == 1 and warmup_pages == 0),
                    explicit_tests=explicit_tests,
                )
                results.extend(url_results)

        else:
            # -------- PARALLEL MODE (bounded concurrency) --------
            concurrency = int(self.config.get("concurrency", 4) or 4)
            semaphore = asyncio.Semaphore(concurrency)

            async def run_for_url(url_idx: int, url: str) -> List[TestResult]:
                async with semaphore:
                    page = await self.browser_manager.new_page()
                    try:
                        return await self._run_tests_for_url(
                            page=page,
                            url=url,
                            test_classes=test_classes,
                            url_idx=url_idx,
                            total_urls=total_urls,
                            handle_cmp=(url_idx == 1 and warmup_pages == 0),
                            explicit_tests=explicit_tests,
                        )
                    except Exception as e:
                        print(f"[{url_idx}/{total_urls}] ⚠️  Worker error for {url}: {e}")
                        return []
                    finally:
                        try:
                            await page.close()
                        except Exception:
                            pass

            tasks = [asyncio.create_task(run_for_url(idx, url)) for idx, url in enumerate(selected_urls, start=1)]
            url_results_lists = await asyncio.gather(*tasks, return_exceptions=False)
            for url_results in url_results_lists:
                results.extend(url_results)

        # Close browser/context (this closes all pages, including warmup page)
        await self.browser_manager.close()
        self._warm_page = None

        if bool(self.config.get("print_matrix_summary", True)):
            self._print_matrix_summary(results, self.selected_urls)

        return results

    # ------------- Cross-device comparison matrix -------------

    @staticmethod
    def print_device_comparison_matrix(
        all_results: List[TestResult],
        device_keys: List[str],
    ) -> None:
        """
        Print a compact cross-device summary.

        Rows  = test names (sorted)
        Cols  = device keys (e.g. desktop, mobile_ios, mobile_android, tablet)
        Cell  = aggregated result across all URLs for that test × device:
                  PASS          — every URL passed
                  FAIL (N/M)    — N out of M URLs failed or errored
                  SKIP          — every URL skipped
                  MIXED         — mix of pass and skip (no failures)
                  -             — no results recorded
        """
        import shutil
        from core.ansi import colour_cell

        # Aggregate: (test_name, device) → list of states
        from collections import defaultdict
        buckets: Dict[tuple, List] = defaultdict(list)
        for r in all_results:
            key = (getattr(r, "test_name", ""), getattr(r, "device", ""))
            buckets[key].append(r.state)

        test_names = sorted({r.test_name for r in all_results if getattr(r, "test_name", None)})

        def _agg_cell(states: List) -> str:
            if not states:
                return "-"
            total = len(states)
            n_pass = sum(1 for s in states if s == TestState.PASSED)
            n_skip = sum(1 for s in states if s == TestState.SKIPPED)
            n_fail = sum(1 for s in states if s in (TestState.FAILED, TestState.ERROR))
            if n_fail:
                return f"FAIL ({n_fail}/{total})" if n_fail < total else "FAIL"
            if n_skip == total:
                return "SKIP"
            if n_pass == total:
                return "PASS"
            return "MIXED"

        max_test = 36
        max_cell = max(18, max(len(d) for d in device_keys) + 2)

        def clip(s: str, n: int) -> str:
            return s if len(s) <= n else s[:n - 1] + "…"

        widths = [max_test] + [max(max_cell, len(d)) for d in device_keys]

        def sep(c: str = "-") -> str:
            return "".join("+" + (c * (w + 2)) for w in widths) + "+"

        def fmt_row(cols, is_header: bool = False) -> str:
            out = []
            for i, c in enumerate(cols):
                clipped = clip(str(c), widths[i])
                if not is_header and i > 0:
                    pad = " " * max(0, widths[i] - len(clipped))
                    out.append(colour_cell(clipped) + pad)
                else:
                    out.append(clipped.ljust(widths[i]))
            return "| " + " | ".join(out) + " |"

        title = "📊 CROSS-DEVICE SUMMARY (rows=tests, cols=devices)"
        border = "=" * max(len(sep()), len(title))

        print("\n" + border)
        print(title)
        print(border)
        print(sep())
        print(fmt_row(["Test"] + device_keys, is_header=True))
        print(sep("="))
        for t in test_names:
            row = [t] + [_agg_cell(buckets.get((t, d), [])) for d in device_keys]
            print(fmt_row(row))
            print(sep())