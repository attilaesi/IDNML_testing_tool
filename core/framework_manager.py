# core/framework_manager.py

import importlib
import pkgutil
import csv
import asyncio
import inspect
import sys
import os
from pathlib import Path
from typing import List, Dict, Type, Optional
from urllib.parse import urlparse, urlunparse

from core.readiness_waiter import ReadinessWaiter
from core.base_test import BaseTest, TestResult, TestState
from core.browser_manager import BrowserManager
from core.cmp_handler import CMPHandler
from core.data_extractor import DataExtractor  # noqa: F401 (used by tests)

from config.site_test_plans import SITE_TEST_PLANS


class TestFramework:
    def __init__(self, config: Dict):
        self.config = config
        self.tests: Dict[str, Type[BaseTest]] = {}
        self.test_categories: Dict[str, List[str]] = {}
        self.browser_manager = BrowserManager(config)
        self.cmp_handler = CMPHandler(config)

        # Hold onto a warmup page so we can reuse it for tests
        self._warm_page = None

    # ------------- URL helpers -------------

    def _add_basic_auth_to_url(self, url: str) -> str:
        """
        If URL points to a UAT/DEV/FEAT environment, inject basic auth credentials
        like: https://demo:review@uat-web.independent.co.uk/...
        """
        if not url:
            return url

        url_l = url.lower()

        # Treat any host containing 'uat', 'feat', or 'dev' as pre-prod
        is_preprod_url = any(token in url_l for token in ("uat", "feat", "dev"))
        is_forced_uat = bool(self.config.get("uat_mode", False))

        # Only apply if clearly pre-prod OR uat_mode is explicitly enabled
        if not (is_preprod_url or is_forced_uat):
            return url

        username = "demo"
        password = "review"

        parsed = urlparse(url)

        # Avoid double-injecting
        if parsed.username or parsed.password:
            return url

        netloc = parsed.netloc
        if not netloc:
            return url

        parsed = parsed._replace(netloc=f"{username}:{password}@{netloc}")
        auth_url = urlunparse(parsed)
        print(f"🔐 Injected basic auth into URL for pre-prod (uat/feat/dev): {auth_url}")
        return auth_url

    async def _set_context_cookies(self, page, url: str) -> None:
        """
        Set cookies BEFORE navigation.

        Always:
          - is_mobile_or_tablet

        For pre-prod (UAT / FEAT / DEV):
          - feature flag cookies from config['uat_cookies']
        """
        is_mobile = bool(self.config.get("mobile", True))
        uat_cookies = self.config.get("uat_cookies", [])

        raw = url or self.config.get("site_url", "")
        parsed = urlparse(raw if raw else "https://www.independent.co.uk")
        host = parsed.hostname or "www.independent.co.uk"
        domain = host  # host-only cookie

        raw_l = (raw or "").lower()
        # Pre-prod if URL contains uat/feat/dev OR global uat_mode is set
        is_preprod_url = any(token in raw_l for token in ("uat", "feat", "dev"))
        uat_mode = bool(self.config.get("uat_mode", False) or is_preprod_url)

        cookies = [
            {
                "name": "is_mobile_or_tablet",
                "value": "true" if is_mobile else "false",
                "domain": domain,
                "path": "/",
            }
        ]

        if uat_mode and uat_cookies:
            for base_cookie in uat_cookies:
                c = dict(base_cookie)           # shallow copy
                c.setdefault("domain", domain)  # apply current host if not set
                cookies.append(c)

        try:
            await page.context.add_cookies(cookies)
            print(
                f"🌍 Context cookies set (mobile={is_mobile}, preprod={uat_mode}): "
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

        timeout = float(self.config.get("page_type_timeout", 3.0))
        interval = 0.25
        elapsed = 0.0

        while elapsed < timeout:
            val = await page.evaluate(js)
            if val:
                return str(val).strip().lower()

            await asyncio.sleep(interval)
            elapsed += interval

        return "unknown"


    async def _wait_for_gpt_slot_responses(self, page, log_fn) -> None:
        """
        Wait until GPT fires 'slotResponseReceived'.
        Logs ONLY the slot names (last path segment).
        """
        timeout = float(self.config.get("gpt_slot_timeout", 7.0))
        interval = 0.25
        elapsed = 0.0

        # Helper to extract slot name from full path
        extract_js = """
        (path) => {
            try {
                if (!path) return "unknown";
                const parts = path.split("/");
                return parts[parts.length - 1] || "unknown";
            } catch (e) {
                return "unknown";
            }
        }
        """

        # Init listener + capture any initial slots
        init_js = f"""
        () => {{
            try {{
                if (!window.googletag || !googletag.pubads) {{
                    return {{ ok: false, reason: "googletag/pubads missing" }};
                }}
                const pubads = googletag.pubads();

                if (!window.__idnmlSlotResponses) {{
                    window.__idnmlSlotResponses = [];

                    // Capture any already-responded slots
                    try {{
                        const slots = pubads.getSlots() || [];
                        for (const s of slots) {{
                            if (!s || !s.getResponseInformation) continue;
                            const info = s.getResponseInformation();
                            if (info) {{
                                const path = s.getAdUnitPath ? s.getAdUnitPath() : "unknown";
                                if (!window.__idnmlSlotResponses.includes(path)) {{
                                    window.__idnmlSlotResponses.push(path);
                                }}
                            }}
                        }}
                    }} catch(e) {{}}

                    // Listen for new responses
                    pubads.addEventListener("slotResponseReceived", (event) => {{
                        try {{
                            const slot = event && event.slot;
                            const path = slot && slot.getAdUnitPath ? slot.getAdUnitPath() : "unknown";
                            if (!window.__idnmlSlotResponses.includes(path)) {{
                                window.__idnmlSlotResponses.push(path);
                            }}
                        }} catch(e) {{}}
                    }});
                }}
                return {{ ok: true, count: window.__idnmlSlotResponses.length }};
            }} catch (e) {{
                return {{ ok: false, reason: String(e) }};
            }}
        }}
        """

        init_result = await page.evaluate(init_js)
        if not init_result.get("ok"):
            log_fn(f"⚠️ Could not attach GPT listener: {init_result.get('reason')}")
            return

        # Already had responses?
        if init_result.get("count", 0) > 0:
            slots = await page.evaluate(
                f"""
                () => {{
                    const toName = {extract_js};
                    return (window.__idnmlSlotResponses || []).map(toName);
                }}
                """
            )
            names = ", ".join(slots) if slots else "unknown"
            log_fn(f"✅ GPT slotResponseReceived already seen for {len(slots)} slot(s): {names}")
            return

        # Poll for slot responses
        while elapsed < timeout:
            res = await page.evaluate(
                f"""
                () => {{
                    const toName = {extract_js};
                    const arr = Array.isArray(window.__idnmlSlotResponses)
                        ? window.__idnmlSlotResponses.slice()
                        : [];
                    return {{
                        count: arr.length,
                        slots: arr.map(toName)
                    }};
                }}
                """
            )
            count = res.get("count", 0)
            slots = res.get("slots", [])

            if count > 0:
                names = ", ".join(slots)
                log_fn(f"✅ GPT slotResponseReceived seen for {count} slot(s): {names}")
                return

            await asyncio.sleep(interval)
            elapsed += interval

        # Timeout: partial or no data
        res = await page.evaluate(
            f"""
            () => {{
                const toName = {extract_js};
                const arr = Array.isArray(window.__idnmlSlotResponses)
                    ? window.__idnmlSlotResponses.slice()
                    : [];
                return {{
                    count: arr.length,
                    slots: arr.map(toName)
                }};
            }}
            """
        )
        count = res.get("count", 0)
        slots = res.get("slots", [])

        if count > 0:
            names = ", ".join(slots)
            log_fn(f"⚠️ GPT slotResponseReceived partial ({count}) before timeout: {names}")
        else:
            log_fn("⚠️ No GPT slotResponseReceived seen before timeout.")

    # ------------- Test discovery -------------

    def _iter_test_module_names(self):
        """
        Dynamically discover and yield all test module names under the top-level
        'tests' directory — including all subpackages like prebid_tests, gpt_tests, etc.

        We include any module that contains "test" in its module name.
        """
        root_pkg = "tests"
        tests_root = Path(__file__).resolve().parent.parent / "tests"

        # Ensure tests_root’s parent (project root) is on sys.path
        tests_root_parent = tests_root.parent
        if str(tests_root_parent) not in sys.path:
            sys.path.insert(0, str(tests_root_parent))

        # Import the top-level tests package
        try:
            importlib.import_module(root_pkg)
        except Exception as e:
            print(f"⚠️  Could not import root package {root_pkg}: {e}")
            return

        # Recursively walk all packages and yield .py modules that look like test files
        for _importer, modname, _ispkg in pkgutil.walk_packages(
            [str(tests_root)], prefix=f"{root_pkg}."
        ):
            # Skip dunder/private
            if modname.split(".")[-1].startswith("_"):
                continue
            # Only yield modules that look like tests by name
            if "test" in modname.lower():
                yield modname

    def discover_tests(self) -> None:
        """
        Import test modules and collect classes that inherit BaseTest.
        Populates self.tests (name -> class) and self.test_categories (category -> [names]).
        """
        self.tests = {}
        self.test_categories = {}

        for module_name in self._iter_test_module_names():
            try:
                test_module = importlib.import_module(module_name)
            except Exception as e:
                print(f"❌ Failed to import {module_name}: {e}")
                continue

            # Determine category from folder name (informational only)
            if ".prebid_tests." in module_name:
                category = "PREBID"
            elif ".gpt_tests." in module_name:
                category = "GPT"
            else:
                category = "OTHER"

            self.test_categories.setdefault(category, [])

            # Collect concrete subclasses defined in this module
            for name, obj in inspect.getmembers(test_module, inspect.isclass):
                if obj.__module__ != module_name:
                    continue
                if not issubclass(obj, BaseTest) or obj is BaseTest:
                    continue

                self.tests[name] = obj
                self.test_categories[category].append(name)
                print(f"Discovered test: {name} in category {category}")

    def get_tests_by_category(self, category: str) -> List[Type[BaseTest]]:
        """Get all tests in a specific category."""
        test_names = self.test_categories.get(category.upper(), [])
        return [self.tests[name] for name in test_names]

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
            f"({self.config.get('active_site')} | "
            f"{'UAT' if self.config.get('uat_mode') else 'LIVE'})"
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
        await self._set_context_cookies(page, auth_url)
        await page.goto(auth_url, wait_until="domcontentloaded")

        if handle_cmp:
            await self.cmp_handler.handle_consent(page)

        waiter = ReadinessWaiter(timeout=self.config.get("prebid_ready_timeout", 10))
        await waiter.wait_for_prebid_and_gpt(page)

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
    ) -> List[TestResult]:
        """
        Navigate to URL, prepare environment, run all tests, return results.

        All logging for this URL is buffered and printed as a single
        grouped block (helps readability when running in parallel).
        """
        # Per-URL log buffer
        log: List[str] = []

        def logprint(*args):
            msg = " ".join(str(a) for a in args)
            log.append(msg)

        logprint(f"[{url_idx}/{total_urls}] Processing {url}")

        # Inject credentials for UAT/DEV/feature branches if needed
        auth_url = self._add_basic_auth_to_url(url)

        # Set device + UAT/feature cookies before navigation
        await self._set_context_cookies(page, auth_url)

        # Navigate & wait for DOM
        await page.goto(auth_url, wait_until="domcontentloaded")

        # CMP only once per session / first URL (per mode)
        if handle_cmp:
            await self.cmp_handler.handle_consent(page)

        # Wait until pbjs & GPT are fully ready
        waiter = ReadinessWaiter(timeout=self.config.get("prebid_ready_timeout", 10))
        await waiter.wait_for_prebid_and_gpt(page)

        # NEW: wait for GPT slotResponseReceived before running tests
        await self._wait_for_gpt_slot_responses(page, logprint)

        # Detect page type from GPT key-values (with small polling window)
        page_type_norm = await self._detect_page_type(page)
        logprint(f"🧩 Detected page type: {page_type_norm}")

        # Detect locale from Locale cookie (UK / US)
        locale = await self._detect_locale(page)
        logprint(f"🗺️  Detected locale: {locale}")

        # 🔸 Apply site test plan (inherit-all, then exclude by page type)
        site_id = str(self.config.get("active_site", "independent")).lower()
        site_plan = SITE_TEST_PLANS.get(site_id, {})

        def _class_name(cls: Type[BaseTest]) -> str:
            return getattr(cls, "name", cls.__name__)

        if site_plan and site_plan.get("exclude") is not None:
            excluded_site = set(site_plan.get("exclude", []))
            exclude_map = site_plan.get("exclude_by_page_type", {}) or {}
            excluded_pt = set(exclude_map.get(page_type_norm, []))

            # Final disallowed set for this URL
            disallowed = excluded_site | excluded_pt

            # Only instantiate / run tests that are allowed for this URL
            run_classes = [
                cls for cls in test_classes if _class_name(cls) not in disallowed
            ]
        else:
            # No site plan -> run everything discovered
            run_classes = list(test_classes)

        url_results: List[TestResult] = []

        # Run each test for this URL (fresh instance per class)
        for cls in run_classes:
            test_name = _class_name(cls)
            test = cls(self.config)

            # Expose locale on the test instance so tests can read self.locale
            try:
                setattr(test, "locale", locale)
            except Exception:
                pass

            try:
                result = await test.run(page, url)

                # Attach page_type and locale into metadata so tests/reporting can use it later
                try:
                    if hasattr(result, "metadata"):
                        if result.metadata is None:
                            result.metadata = {}
                        if isinstance(result.metadata, dict):
                            result.metadata.setdefault("page_type", page_type_norm)
                            result.metadata.setdefault("locale", locale)
                except Exception:
                    pass

                url_results.append(result)
                logprint(f"  {test_name}: {result.state.value}")
            except Exception as e:
                logprint(f"  {test_name}: ERROR - {str(e)}")

        left = total_urls - url_idx
        logprint(f"[{url_idx}/{total_urls}] done, {left} left")

        # Flush the buffered log as a single block so parallel runs don't interleave
        block_lines = [
            "",
            "=" * 80,
            f"📄 RESULT BLOCK FOR URL {url_idx}/{total_urls}",
            url,
            "=" * 80,
        ]
        block_lines.extend(log)
        block_lines.append("=" * 80)
        block_lines.append("")

        print("\n".join(block_lines))

        return url_results

    # ------------- Main runner -------------

    async def run_tests(
        self, test_names: Optional[List[str]] = None, category: str = None
    ) -> List[TestResult]:
        """Run specified tests, using either single-page mode or parallel mode."""
        results: List[TestResult] = []

        # Which tests to run? (we build the full pool of *classes*; site plan is applied per URL)
        if test_names:
            test_classes: List[Type[BaseTest]] = [
                self.tests[name]
                for name in test_names
                if name in self.tests
            ]
        elif category:
            test_classes = self.get_tests_by_category(category)
        else:
            test_classes = list(self.tests.values())

        if not test_classes:
            print("No tests found to run")
            return results

        # Start browser / context
        await self.browser_manager.start()
        print(f"🛫 Browser launched (mobile = {self.config.get('mobile', True)})")

        # Get URLs
        selected_urls = await self._get_selected_urls()
        total_urls = len(selected_urls)
        print(
            f"▶️  Starting crawl: {total_urls} URLs "
            f"(mobile={self.config.get('mobile', True)})"
        )

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
            # Reuse warmup page if we have one; otherwise create a new page
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
                )
                results.extend(url_results)

            # Do NOT close the page explicitly here – closing the browser/context
            # at the end will clean up all pages.
        else:
            # -------- PARALLEL MODE (bounded concurrency) --------
            concurrency = self.config.get("concurrency", 4)
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
                        )
                    finally:
                        await page.close()

            tasks = [
                asyncio.create_task(run_for_url(idx, url))
                for idx, url in enumerate(selected_urls, start=1)
            ]
            url_results_lists = await asyncio.gather(*tasks)
            for url_results in url_results_lists:
                results.extend(url_results)

        # Close browser/context (this closes all pages, including warmup page)
        await self.browser_manager.close()
        self._warm_page = None

        # Write CSV output (still test × URL at this stage)
        await self._write_csv_output(results)

        # Write additional page-type summary CSV
        await self._write_pagetype_summary(results)

        return results

    # ------------- CSV output -------------

    async def _write_csv_output(self, results: List[TestResult]):
        if not results:
            return

        # Use configured path, defaulting inside output/
        output_file = self.config.get("output_file", "output/output.csv")
        output_path = Path(output_file)

        # Ensure parent directory exists
        if output_path.parent:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Unique URLs (columns)
        urls: List[str] = []
        for r in results:
            if getattr(r, "url", None) and r.url not in urls:
                urls.append(r.url)

        # URL -> page_type
        url_page_type: Dict[str, str] = {}
        for r in results:
            url = getattr(r, "url", None)
            if not url:
                continue
            meta = getattr(r, "metadata", None)
            if isinstance(meta, dict):
                pt = meta.get("page_type")
                if pt and url not in url_page_type:
                    url_page_type[url] = str(pt)

        # Unique test names
        test_names: List[str] = []
        for r in results:
            if r.test_name not in test_names:
                test_names.append(r.test_name)

        # Index results by (test_name, url)
        result_map: Dict[tuple, TestResult] = {}
        for r in results:
            url = getattr(r, "url", None)
            if url:
                result_map[(r.test_name, url)] = r

        # Header
        header_labels = []
        for url in urls:
            pt = url_page_type.get(url)
            header_labels.append(f"{url} ({pt})" if pt else url)

        cols = ["TestName"] + header_labels

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()

            for test_name in test_names:
                row: Dict[str, str] = {"TestName": test_name}
                for url, col_name in zip(urls, header_labels):
                    res = result_map.get((test_name, url))
                    if not res:
                        row[col_name] = ""
                        continue
                    status = res.state.value if hasattr(res, "state") else "UNKNOWN"
                    if res.errors:
                        detail = "; ".join(res.errors)
                        row[col_name] = f"{status}\n{detail}"
                    else:
                        row[col_name] = status
                writer.writerow(row)

        print(f"📄 Results written to: {output_path}")

    async def _write_pagetype_summary(self, results: List[TestResult]):
        if not results:
            return

        # Use configured path, defaulting inside output/
        output_file = self.config.get(
            "output_pagetype_file", "output/output_by_pagetype.csv"
        )
        output_path = Path(output_file)

        # Ensure parent directory exists
        if output_path.parent:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        page_types: List[str] = []
        pt_urls: Dict[str, set[str]] = {}

        for r in results:
            url = getattr(r, "url", None)
            meta = getattr(r, "metadata", None)
            pt = None
            if isinstance(meta, dict):
                pt = meta.get("page_type")
            if not pt:
                pt = "unknown"
            pt = str(pt)
            if pt not in page_types:
                page_types.append(pt)
            if url:
                pt_urls.setdefault(pt, set()).add(url)

        if "unknown" in page_types and len(page_types) > 1:
            page_types = [p for p in page_types if p != "unknown"] + ["unknown"]

        test_names: List[str] = []
        for r in results:
            if r.test_name not in test_names:
                test_names.append(r.test_name)

        grouped: Dict[tuple[str, str], List[TestResult]] = {}
        for r in results:
            meta = getattr(r, "metadata", None)
            pt = None
            if isinstance(meta, dict):
                pt = meta.get("page_type")
            if not pt:
                pt = "unknown"
            pt = str(pt)
            key = (r.test_name, pt)
            grouped.setdefault(key, []).append(r)

        def summarise(cell_results: List[TestResult]) -> str:
            if not cell_results:
                return ""
            error_res = next(
                (cr for cr in cell_results if cr.state.name == "ERROR"), None
            )
            if error_res:
                msg = "; ".join(error_res.errors) if error_res.errors else ""
                return f"ERROR\n{msg}" if msg else "ERROR"
            fail_res = next(
                (cr for cr in cell_results if cr.state.name == "FAILED"), None
            )
            if fail_res:
                msg = "; ".join(fail_res.errors) if fail_res.errors else ""
                return f"FAILED\n{msg}" if msg else "FAILED"
            passed = any(cr.state.name == "PASSED" for cr in cell_results)
            if passed:
                return "PASSED"
            any_state = (
                cell_results[0].state.value
                if hasattr(cell_results[0], "state")
                else "UNKNOWN"
            )
            return any_state

        cols = ["TestName"] + page_types

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()

            for test_name in test_names:
                row: Dict[str, str] = {"TestName": test_name}
                for pt in page_types:
                    cell_results = grouped.get((test_name, pt), [])
                    row[pt] = summarise(cell_results)
                writer.writerow(row)

            writer.writerow({})
            writer.writerow({"TestName": "Page types (page_type -> URLs):"})
            for pt in page_types:
                urls_for_pt = sorted(pt_urls.get(pt, []))
                if not urls_for_pt:
                    continue
                joined = "; ".join(urls_for_pt)
                writer.writerow({"TestName": f"{pt}: {joined}"})

        print(f"📄 Page-type summary written to: {output_path}")