# core/framework_manager.py

import asyncio
from typing import List, Dict, Type, Optional
from urllib.parse import urlparse, urlunparse

from core.readiness_waiter import ReadinessWaiter
from core.base_test import BaseTest, TestResult, TestState  # TestState kept for completeness
from core.browser_manager import BrowserManager
from core.cmp_handler import CMPHandler
from core.data_extractor import DataExtractor  # noqa: F401 (used by tests)

from config.site_test_plans import SITE_TEST_PLANS

from core.framework.discovery import discover_tests, get_tests_by_category
from core.framework.csv_writer import CSVWriter


class TestFramework:
    def __init__(self, config: Dict):
        self.config = config
        self.tests: Dict[str, Type[BaseTest]] = {}
        self.test_categories: Dict[str, List[str]] = {}
        self.browser_manager = BrowserManager(config)
        self.cmp_handler = CMPHandler(config)

        # Hold onto a warmup page so we can reuse it for tests
        self._warm_page = None

        # CSV writer helper
        self.csv_writer = CSVWriter(config)

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

        # Wait until pbjs & GPT are fully ready (inc. GPT slotResponseReceived logic)
        waiter = ReadinessWaiter(timeout=self.config.get("prebid_ready_timeout", 10))
        await waiter.wait_for_prebid_and_gpt(page)

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
        await self.csv_writer.write_main(results)

        # Write additional page-type summary CSV
        await self.csv_writer.write_pagetype_summary(results)

        return results