# tasks/run_multi_device.py
# Run all ad tests across the canonical four-device suite (desktop, mobile iOS,
# mobile Android, tablet) and print a cross-device comparison summary.
#
# Usage:
#   python -m tasks.run_multi_device [--site SITE] [--test TEST_NAME]
#   python -m tasks.run_multi_device --devices desktop,mobile_ios
#
# Devices run sequentially by default (clean log output).
# Set device_concurrency > 1 in base_config to run devices concurrently.

import argparse
import asyncio
import copy
import time
from datetime import datetime
from typing import List, Optional

from config.base_config import TestConfig
from config.device_config import DEVICE_SUITE
from core.framework_manager import TestFramework
from core.ansi import dim
from core.url_context_helpers import env_from_url
from tasks.common import print_runner_banner, print_failure_details, _get_url_order

VALID_SITES = [
    "independent", "independent_uat", "independent_staging",
    "standard", "standard_uat", "standard_staging", "standard_dev_master",
]


def _make_device_config(base_cfg: TestConfig, device_key: str, device_name: str) -> dict:
    """
    Return a config dict tuned for a specific device.
    Overrides device_name; disables matrix printing (we print it ourselves per device).
    """
    cfg = base_cfg.get_config()
    cfg["device_name"] = device_name
    cfg["device_key"] = device_key     # used by framework to tag results correctly
    cfg["print_matrix_summary"] = False  # only the final cross-device matrix is printed
    return cfg


def _device_banner(device_key: str, device_name: str) -> None:
    line = f"  DEVICE: {device_key.upper()}  ({device_name})  "
    border = "=" * max(60, len(line) + 4)
    print(f"\n{border}")
    print(f"{'':>2}{line}")
    print(border)


async def _run_one_device(
    device_key: str,
    device_name: str,
    base_cfg: TestConfig,
    test_names: Optional[List[str]],
    quiet_banner: bool = False,
) -> List:
    """Run the full test suite for a single device and return its results."""
    config = _make_device_config(base_cfg, device_key, device_name)

    if not quiet_banner:
        _device_banner(device_key, device_name)

    framework = TestFramework(config)
    framework.discover_tests()

    if test_names:
        missing = [t for t in test_names if t not in framework.tests]
        if missing:
            print(f"[TESTS] Unknown test(s): {', '.join(missing)}")
            known = sorted(framework.tests.keys())
            print("  Known tests:\n" + "\n".join(f"    {t}" for t in known))
            return []

    results = await framework.run_tests(
        test_names=test_names,
    )
    return results


async def main():
    parser = argparse.ArgumentParser(description="Multi-device ad test runner")
    parser.add_argument(
        "--site",
        metavar="SITE_PROFILE",
        choices=VALID_SITES,
        help=f"Site profile. One of: {', '.join(VALID_SITES)}",
    )
    parser.add_argument(
        "--test",
        metavar="TEST_NAME",
        help="Run only this test on all devices.",
    )
    parser.add_argument(
        "--devices",
        metavar="DEVICE_KEYS",
        help=(
            "Comma-separated subset of devices to run. "
            f"Available: {', '.join(DEVICE_SUITE)}. "
            "Omit to run all four."
        ),
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

    # Build base config (site selection, URLs, etc.)
    base_cfg = TestConfig()
    if args.site:
        base_cfg.active_site = args.site
    if args.browserstack:
        base_cfg.browserstack_config["browserstack_enabled"] = True
    if args.geo:
        base_cfg.geo = args.geo.lower()
        if not args.browserstack:
            print(f"WARNING: --geo {args.geo} has no effect on browser location without --browserstack. CMP handling will still run.")
    if args.no_headless:
        base_cfg.browser_config["headless"] = False

    # Resolve which devices to run
    if args.devices:
        requested = [d.strip() for d in args.devices.split(",") if d.strip()]
        unknown = [d for d in requested if d not in DEVICE_SUITE]
        if unknown:
            print(f"❌ Unknown device key(s): {', '.join(unknown)}")
            print(f"   Available: {', '.join(DEVICE_SUITE)}")
            return
        active_suite = {k: DEVICE_SUITE[k] for k in requested}
    else:
        active_suite = dict(DEVICE_SUITE)

    test_names = [args.test] if args.test else None

    # Resolve parallel mode from config
    sample_config = base_cfg.get_config()
    parallel_devices = int(sample_config.get("device_concurrency", 1) or 1) > 1

    site_id = sample_config.get("active_site", "")
    site_url = sample_config.get("site_url", "")

    print_runner_banner(sample_config, label="MULTI-DEVICE AD TEST RUN")
    print(f"  devices : {', '.join(active_suite)}")
    print(f"  mode    : {'parallel' if parallel_devices else 'sequential'}")
    if test_names:
        print(f"  filter  : {test_names[0]}")
    print("=" * 60)

    all_results = []
    total_start = time.monotonic()

    if parallel_devices:
        # Run all devices concurrently; output will interleave but is prefixed per device
        tasks = [
            asyncio.create_task(
                _run_one_device(dk, dn, base_cfg, test_names, quiet_banner=False)
            )
            for dk, dn in active_suite.items()
        ]
        device_result_lists = await asyncio.gather(*tasks)
        for results in device_result_lists:
            all_results.extend(results)
    else:
        for device_key, device_name in active_suite.items():
            results = await _run_one_device(device_key, device_name, base_cfg, test_names)
            all_results.extend(results)

    total_elapsed = time.monotonic() - total_start

    # Cross-device comparison summary + combined failure details
    if all_results:
        device_keys = list(active_suite.keys())
        TestFramework.print_device_comparison_matrix(all_results, device_keys=device_keys)

        seen_urls: set = set()
        url_order = []
        for r in all_results:
            if r.url and r.url not in seen_urls:
                url_order.append(r.url)
                seen_urls.add(r.url)
        print_failure_details(all_results, url_order=url_order, device_keys=device_keys)

    # Supabase upload + regression diff (--regression only)
    combined_config = base_cfg.get_config()
    regression = None
    if args.regression and all_results:
        from core.supabase_writer import (
            SupabaseResultsWriter, new_run_id,
            geo_from_results, publisher_from_results, environment_from_results,
        )
        ts_iso = datetime.utcnow().isoformat() + "Z"
        run_id = new_run_id()
        geo = geo_from_results(all_results)
        publisher = publisher_from_results(all_results)
        environment = environment_from_results(all_results)
        print("\n📤 Uploading results to Supabase…")
        sw = SupabaseResultsWriter(combined_config)
        await sw.write_results(all_results, run_id, ts_iso)
        print("📊 Fetching regression diff…")
        regression = await sw.fetch_regression_diff(run_id, publisher, environment, geo)

    # Google Sheets output
    if bool(combined_config.get("sheets_enabled", False)) and all_results and not args.nosheet:
        from core.sheets_writer import SheetsWriter
        from core.supabase_writer import geo_from_results as _geo_from_results
        _geo = (combined_config.get("geo") or "").upper() or _geo_from_results(all_results)
        run_meta = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "site": combined_config.get("active_site", ""),
            "env": env_from_url(combined_config.get("site_url", "")),
            "geo": _geo,
            "runner": "BrowserStack" if args.browserstack else "Local Playwright",
            "device_names": dict(active_suite),
            "regression": regression,
        }
        writer = SheetsWriter(combined_config)
        sheet_url = await writer.write_report(
            all_results=all_results,
            device_keys=list(active_suite.keys()),
            run_meta=run_meta,
        )
        if sheet_url:
            print(f"\n📊 Google Sheet: {sheet_url}")

    mins, secs = divmod(int(total_elapsed), 60)
    print(f"\n✅ Multi-device run complete  ({mins}m {secs}s total)\n")


if __name__ == "__main__":
    asyncio.run(main())
