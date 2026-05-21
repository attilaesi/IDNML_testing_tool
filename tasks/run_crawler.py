# tasks/run_crawler.py
# Entry point: fetch URLs from a remote sitemap, run ad tests against them.
# Usage:
#   python -m tasks.run_crawler
#   python -m tasks.run_crawler --max-urls 20
#   python -m tasks.run_crawler --test gpt_gam_bid_keys_test
#   python -m tasks.run_crawler --tests gpt_gam_bid_keys_test,layout_ad_sequence_test
#   python -m tasks.run_crawler --sitemap https://www.independent.co.uk/sitemaps/sitemap-recent.xml

import argparse
import asyncio
import time
import urllib.request
import xml.etree.ElementTree as ET

try:
    from config.base_config import CONFIG
except ImportError:
    from config.base_config import TestConfig
    CONFIG = TestConfig().get_config()

from core.framework_manager import TestFramework
from tasks.common import print_results, _get_url_order

DEFAULT_SITEMAP = "https://www.independent.co.uk/sitemaps/sitemap-recent.xml"
DEFAULT_MAX_URLS = 10


def _fetch_sitemap_urls(sitemap_url: str) -> list[str]:
    """Download a sitemap XML and return all <loc> URLs."""
    print(f"🌐 Fetching sitemap: {sitemap_url}")
    req = urllib.request.Request(
        sitemap_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AdTestCrawler/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    # Sitemap namespace varies — strip it for robust matching
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    urls = []
    for url_el in root.findall(f"{ns}url"):
        loc = url_el.find(f"{ns}loc")
        if loc is not None and loc.text:
            urls.append(loc.text.strip())

    print(f"   Found {len(urls)} URLs in sitemap")
    return urls


async def main():
    parser = argparse.ArgumentParser(description="Ad Testing Framework — Sitemap Crawler")
    parser.add_argument(
        "--sitemap",
        default=DEFAULT_SITEMAP,
        metavar="URL",
        help=f"Sitemap XML URL to crawl (default: {DEFAULT_SITEMAP})",
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=DEFAULT_MAX_URLS,
        metavar="N",
        help=f"Maximum number of URLs to test (default: {DEFAULT_MAX_URLS})",
    )
    parser.add_argument(
        "--test",
        metavar="TEST_NAME",
        help="Run only this single test (e.g. gpt_gam_bid_keys_test).",
    )
    parser.add_argument(
        "--tests",
        metavar="TEST1,TEST2",
        help="Comma-separated list of tests to run (e.g. gpt_gam_bid_keys_test,layout_ad_sequence_test).",
    )
    args = parser.parse_args()

    # Resolve test names
    if args.test and args.tests:
        print("❌ Use --test OR --tests, not both.")
        return
    if args.test:
        test_names = [args.test]
    elif args.tests:
        test_names = [t.strip() for t in args.tests.split(",") if t.strip()]
    else:
        test_names = None  # all tests

    # Fetch URLs from sitemap
    try:
        sitemap_urls = _fetch_sitemap_urls(args.sitemap)
    except Exception as e:
        print(f"❌ Failed to fetch sitemap: {e}")
        return

    if not sitemap_urls:
        print("❌ No URLs found in sitemap.")
        return

    selected_urls = sitemap_urls[: args.max_urls]
    print(f"   Testing {len(selected_urls)} of {len(sitemap_urls)} URLs (--max-urls {args.max_urls})")

    # Build config: override URL list with sitemap URLs.
    # Keep active_site so page-type detection and cookie logic still work correctly.
    config = dict(CONFIG)
    config["urls"] = selected_urls

    print("\n🚀 Ad Testing Framework — Crawler mode")
    print(f"Active site: {config.get('active_site', '')}")
    print(f"Sitemap:     {args.sitemap}")
    print(f"Max URLs:    {args.max_urls}")
    from core.device_helpers import device_label
    print(f"Device:      {device_label(config)} (viewport {config.get('viewport', {})})")
    print(f"Headless:    {config.get('headless', True)}")
    if test_names:
        label = test_names[0] if len(test_names) == 1 else ", ".join(test_names)
        print(f"🎯 Tests:    {label}")
    print("-" * 50)

    framework = TestFramework(config)
    framework.discover_tests()

    # Validate requested test names
    if test_names:
        unknown = [t for t in test_names if t not in framework.tests]
        if unknown:
            known = sorted(framework.tests.keys())
            print(f"❌ Unknown test(s): {', '.join(unknown)}\nKnown tests:\n" + "\n".join(f"  {t}" for t in known))
            return

    _t_start = time.monotonic()
    results = await framework.run_tests(test_names=test_names)
    _elapsed = time.monotonic() - _t_start

    print_results(results, framework, config, _elapsed)

    if bool(config.get("write_text_report", True)):
        url_order = _get_url_order(framework, results)
        try:
            await framework.csv_writer.write_text_report(results, urls=url_order)
        except Exception:
            pass

    print()


if __name__ == "__main__":
    asyncio.run(main())
