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
from tasks.common import print_results

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
    args = parser.parse_args()

    cfg = TestConfig()
    if args.site:
        cfg.active_site = args.site
    CONFIG = cfg.get_config()

    print("🚀 Ad Testing Framework")
    print(f"Active site: {CONFIG.get('active_site', '')}")
    print(f"Site URL: {CONFIG.get('site_url', '')}")
    print(f"Max pages: {CONFIG.get('max_pages', 10)}")
    print(f"Mobile mode: {CONFIG.get('mobile', False)}")
    print(f"Headless: {CONFIG.get('headless', True)}")
    if args.test:
        print(f"🎯 Single-test mode: {args.test}")
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

    if bool(CONFIG.get("write_text_report", True)):
        from tasks.common import _get_url_order
        url_order = _get_url_order(framework, results)
        try:
            await framework.csv_writer.write_text_report(results, urls=url_order)
        except Exception:
            pass

    # Google Sheets output (single-device run — one device tab + Summary)
    if bool(CONFIG.get("sheets_enabled", False)) and results:
        from core.sheets_writer import SheetsWriter
        from core.url_context_helpers import env_from_url
        dev_key = CONFIG.get("device_key") or device_label(CONFIG)
        dev_name = CONFIG.get("device_name", "")
        run_meta = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "site": CONFIG.get("active_site", ""),
            "env": env_from_url(CONFIG.get("site_url", "")),
            "device_names": {dev_key: dev_name},
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
