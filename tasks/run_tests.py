# tasks/run_tests.py
# Entry point: discover and run all ad tests against configured site URLs.
# Usage: python -m tasks.run_tests [--test TEST_NAME]

import argparse
import asyncio
import time
from datetime import datetime

from config.base_config import TestConfig
from core.framework_manager import TestFramework
from core.device_helpers import device_label
from tasks.common import print_results, print_runner_banner

VALID_SITES = [
    "independent", "independent_uat", "independent_staging",
    "standard", "standard_uat", "standard_staging", "standard_dev_master",
]


async def main():
    parser = argparse.ArgumentParser(description="Ad Testing Framework")
    parser.add_argument(
        "--test",
        metavar="TEST_NAME",
        help="Run only this test (e.g. gpt_gam_bid_keys_test). Omit to run all tests.",
    )
    parser.add_argument(
        "--site",
        metavar="SITE_PROFILE",
        choices=VALID_SITES,
        help=f"Site profile to use. One of: {', '.join(VALID_SITES)}",
    )
    parser.add_argument(
        "--regression",
        action="store_true",
        help="Upload results to Supabase and include regression diff in the sheet.",
    )
    parser.add_argument(
        "--browserstack",
        action="store_true",
        help="Run via BrowserStack Automate instead of local Playwright.",
    )
    parser.add_argument(
        "--geo",
        metavar="GEO",
        choices=["uk", "us"],
        help="Geo to test from (uk or us). Sets BrowserStack geoLocation and tags Supabase rows.",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Open a visible browser window instead of running headless.",
    )
    parser.add_argument(
        "--nosheet",
        action="store_true",
        help="Skip Google Sheets output at the end of the run.",
    )
    args = parser.parse_args()

    cfg = TestConfig()
    if args.site:
        cfg.active_site = args.site
    if args.browserstack:
        cfg.browserstack_config["browserstack_enabled"] = True
    if args.geo:
        cfg.geo = args.geo.lower()
        if not args.browserstack:
            print(f"WARNING: --geo {args.geo} has no effect on browser location without --browserstack. CMP handling will still run.")
    if args.no_headless:
        cfg.browser_config["headless"] = False
    CONFIG = cfg.get_config()

    print_runner_banner(CONFIG, label="AD TEST RUN")
    if args.test:
        print(f"  filter  : {args.test}")
    print("-" * 50)

    framework = TestFramework(CONFIG)
    framework.discover_tests()

    if args.test and args.test not in framework.tests:
        known = sorted(framework.tests.keys())
        print(f"❌ Test '{args.test}' not found. Known tests:\n" + "\n".join(f"  {t}" for t in known))
        return

    test_names = [args.test] if args.test else None
    _t_start = time.monotonic()
    results = await framework.run_tests(test_names=test_names)
    _elapsed = time.monotonic() - _t_start

    print_results(results, framework, CONFIG, _elapsed)

    # Supabase upload + regression diff (--regression only)
    regression = None
    if args.regression and results:
        from core.supabase_writer import (
            SupabaseResultsWriter, new_run_id,
            geo_from_results, publisher_from_results, environment_from_results,
        )
        ts_iso = datetime.utcnow().isoformat() + "Z"
        run_id = new_run_id()
        geo = geo_from_results(results)
        publisher = publisher_from_results(results)
        environment = environment_from_results(results)
        print("\n📤 Uploading results to Supabase…")
        sw = SupabaseResultsWriter(CONFIG)
        await sw.write_results(results, run_id, ts_iso)
        print("📊 Fetching regression diff…")
        regression = await sw.fetch_regression_diff(run_id, publisher, environment, geo)

    # Google Sheets output (single-device run — one device tab + Summary)
    if bool(CONFIG.get("sheets_enabled", False)) and results and not args.nosheet:
        from core.sheets_writer import SheetsWriter
        from core.url_context_helpers import env_from_url
        from core.supabase_writer import geo_from_results as _geo_from_results
        dev_key = CONFIG.get("device_key") or device_label(CONFIG)
        dev_name = CONFIG.get("device_name", "")
        _geo = (CONFIG.get("geo") or "").upper() or _geo_from_results(results)
        run_meta = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "site": CONFIG.get("active_site", ""),
            "env": env_from_url(CONFIG.get("site_url", "")),
            "geo": _geo,
            "runner": "BrowserStack" if args.browserstack else "Local Playwright",
            "device_names": {dev_key: dev_name},
            "regression": regression,
        }
        writer = SheetsWriter(CONFIG)
        sheet_url = await writer.write_report(
            all_results=results,
            device_keys=[dev_key],
            run_meta=run_meta,
        )
        if sheet_url:
            print(f"\n📊 Google Sheet: {sheet_url}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
