# tasks/run_multi_device.py
# Run all ad tests across the canonical four-device suite (desktop, mobile iOS,
# mobile Android, tablet) and print a cross-device comparison summary.
#
# Usage:
#   python -m tasks.run_multi_device [--site SITE] [--test TEST_NAME]
#   python -m tasks.run_multi_device --devices desktop,mobile_ios
#
# Devices run sequentially by default (clean log output).
# Set parallel_devices=True in base_config to run them concurrently.

import argparse
import asyncio
import copy
import time
from typing import List, Optional

from config.base_config import TestConfig
from config.device_config import DEVICE_SUITE
from core.framework_manager import TestFramework
from core.ansi import dim
from tasks.common import print_results, _get_url_order

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
    cfg["print_matrix_summary"] = True  # each device prints its own matrix
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
            print(f"  ⚠️  Unknown test(s): {', '.join(missing)}")
            known = sorted(framework.tests.keys())
            print("  Known tests:\n" + "\n".join(f"    {t}" for t in known))
            return []

    t0 = time.monotonic()
    results = await framework.run_tests(
        test_names=test_names,
        write_csv=False,   # combined CSV written at the end
    )
    elapsed = time.monotonic() - t0

    print_results(results, framework, config, elapsed)
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
    args = parser.parse_args()

    # Build base config (site selection, URLs, etc.)
    base_cfg = TestConfig()
    if args.site:
        base_cfg.active_site = args.site

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
    parallel_devices = bool(sample_config.get("parallel_devices", False))

    site_id = sample_config.get("active_site", "")
    site_url = sample_config.get("site_url", "")

    print("=" * 60)
    print("  MULTI-DEVICE AD TEST RUN")
    print(f"  site    : {site_id}  ({site_url})")
    print(f"  devices : {', '.join(active_suite)}")
    print(f"  mode    : {'parallel' if parallel_devices else 'sequential'}")
    if test_names:
        print(f"  test    : {test_names[0]}")
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

    # Cross-device comparison summary
    if all_results:
        TestFramework.print_device_comparison_matrix(
            all_results,
            device_keys=list(active_suite.keys()),
        )

    # Combined CSV (one file covering all devices)
    # Re-use the csv_writer from a throwaway framework instance
    combined_config = base_cfg.get_config()
    combined_config["output_file"] = combined_config.get("output_file", "output/output.csv").replace(
        ".csv", "_multi_device.csv"
    )
    combined_config["output_pagetype_file"] = combined_config.get(
        "output_pagetype_file", "output/output_by_pagetype.csv"
    ).replace(".csv", "_multi_device.csv")
    combined_fw = TestFramework(combined_config)
    try:
        await combined_fw.csv_writer.write_main(all_results)
        await combined_fw.csv_writer.write_pagetype_summary(all_results)
    except Exception as e:
        print(dim(f"⚠️  CSV write error: {e}"))

    mins, secs = divmod(int(total_elapsed), 60)
    print(f"\n✅ Multi-device run complete  ({mins}m {secs}s total)\n")


if __name__ == "__main__":
    asyncio.run(main())
