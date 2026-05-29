# tasks/common.py
# Shared output / summary helpers used by run_tests.py and future task scripts.

import os
import time
from collections import defaultdict
from typing import List, Dict, Tuple

from core.base_test import TestState
from core.ansi import green, red, yellow, dim
from core.framework_manager import TestFramework


def print_runner_banner(config: dict, label: str = "AD TEST RUN") -> None:
    """Print a clear header showing execution target (local Playwright vs BrowserStack)."""
    width = 60
    print("=" * width)
    print(f"  {label}")
    print(f"  site    : {config.get('active_site', '')}  ({config.get('site_url', '')})")
    print(f"  device  : {config.get('device_name', 'Desktop Chrome')}")
    print(f"  pages   : {config.get('max_pages', 10)}")

    if config.get("browserstack_enabled"):
        bs_user = os.getenv("BROWSERSTACK_USERNAME", "")
        session = config.get("bs_session_name", "Ad Test")
        build   = config.get("bs_build_name", "IDNML")
        print(f"  runner  : BROWSERSTACK  {bs_user} | build={build} | session={session}")
    else:
        headless = config.get("headless", True)
        print(f"  runner  : local Playwright  (headless={headless})")

    print("=" * width)



def _get_url_order(framework: TestFramework, results) -> List[str]:
    url_order = list(getattr(framework, "selected_urls", []) or [])
    if url_order:
        return url_order
    seen = set()
    url_order = []
    for r in results:
        if getattr(r, "url", None) and r.url not in seen:
            url_order.append(r.url)
            seen.add(r.url)
    return url_order


def _unique_test_summary(executed_results) -> Dict[str, int]:
    """Summarise by unique test names (not test×URL rows)."""
    by_test: Dict[str, List] = defaultdict(list)
    for r in executed_results:
        by_test[r.test_name].append(r)

    total_unique = len(by_test)
    passed_unique = 0
    failed_unique = 0
    errors_unique = 0
    mixed_unique = 0

    for test_name, rs in by_test.items():
        if any(r.state == TestState.ERROR for r in rs):
            errors_unique += 1
            continue
        if any(r.state == TestState.FAILED for r in rs):
            failed_unique += 1
            continue
        if rs and all(r.state == TestState.PASSED for r in rs):
            passed_unique += 1
            continue
        mixed_unique += 1

    return {
        "total_unique": total_unique,
        "passed_unique": passed_unique,
        "failed_unique": failed_unique,
        "errors_unique": errors_unique,
        "mixed_unique": mixed_unique,
    }


def _per_url_summary(executed_results, url_order: List[str]) -> List[Tuple[str, Dict[str, int]]]:
    """Per-URL row-based counts."""
    by_url: Dict[str, List] = defaultdict(list)
    for r in executed_results:
        if getattr(r, "url", None):
            by_url[r.url].append(r)

    out = []
    for u in url_order:
        rs = by_url.get(u, [])
        out.append(
            (
                u,
                {
                    "executed_rows": len(rs),
                    "passed_rows": sum(1 for r in rs if r.state == TestState.PASSED),
                    "failed_rows": sum(1 for r in rs if r.state == TestState.FAILED),
                    "error_rows": sum(1 for r in rs if r.state == TestState.ERROR),
                },
            )
        )
    return out


def print_results(results, framework: TestFramework, config: dict, elapsed: float) -> None:
    """Print the full results summary: counts, per-URL, matrix, failure details, pass details."""
    executed = [r for r in results if r.state not in (TestState.SKIPPED,)]
    url_order = _get_url_order(framework, results)

    uniq = _unique_test_summary(executed)

    parts = [
        f"✅ {green(str(uniq['passed_unique']))} passed",
        f"❌ {red(str(uniq['failed_unique']))} failed",
        f"💥 {red(str(uniq['errors_unique']))} errors",
    ]
    if uniq["mixed_unique"]:
        parts.append(f"🟨 {yellow(str(uniq['mixed_unique']))} mixed")
    summary_line = "  |  ".join(parts)

    mins, secs = divmod(int(elapsed), 60)
    elapsed_str = f"{mins}m {secs}s" if mins else f"{secs}s"

    print("\n" + "=" * 50)
    print(f"📊 {uniq['total_unique']} tests  ⏱ {elapsed_str}   {summary_line}")

    if bool(config.get("print_summary_per_url", True)):
        per_url = _per_url_summary(executed, url_order)
        print("\n" + "-" * 50)
        print("📍 Per-URL summary (row-based)")
        for idx, (u, s) in enumerate(per_url, start=1):
            print(
                f"URL{idx}: executed={s['executed_rows']} "
                f"pass={s['passed_rows']} fail={s['failed_rows']} err={s['error_rows']}"
            )

    # Failed / Error details
    if bool(config.get("print_failed_details", True)):
        failed_or_err_all = [
            r for r in results if r.state in (TestState.FAILED, TestState.ERROR)
        ]
        if failed_or_err_all:
            from collections import OrderedDict

            url_to_label = {u: f"URL{idx+1}" for idx, u in enumerate(url_order)}
            total_urls = len(url_order)

            url_to_pagetype: Dict[str, str] = {}
            for r in results:
                u = getattr(r, "url", None)
                if u and u not in url_to_pagetype:
                    pt = (getattr(r, "metadata", None) or {}).get("page_type") or "unknown"
                    url_to_pagetype[u] = pt

            by_test: Dict[str, List] = defaultdict(list)
            for r in failed_or_err_all:
                by_test[r.test_name].append(r)

            print("\n" + "-" * 50)
            print("🔍 Failed / Error details")
            for test_name in sorted(by_test):
                rs = by_test[test_name]
                fail_count = len(rs)
                has_error = any(r.state == TestState.ERROR for r in rs)
                state_label = red("ERROR") if has_error else red("FAIL")
                print(f"\n• {test_name}  {state_label}  {red(f'({fail_count}/{total_urls} URLs)')}")
                rs_sorted = sorted(rs, key=lambda r: url_order.index(r.url) if r.url in url_order else 999)
                fingerprint_groups: "OrderedDict[str, list]" = OrderedDict()
                for r in rs_sorted:
                    msgs = r.errors if r.errors else r.warnings
                    fingerprint = "\n".join(str(m) for m in (msgs or []))
                    if fingerprint not in fingerprint_groups:
                        fingerprint_groups[fingerprint] = []
                    fingerprint_groups[fingerprint].append(r)

                for fingerprint, group_rs in fingerprint_groups.items():
                    def _url_label(r):
                        page_type = url_to_pagetype.get(r.url, "unknown")
                        tag = (getattr(r, "metadata", None) or {}).get("layout_tag")
                        prefix = f"[{page_type}"
                        if tag:
                            prefix += f", {tag}"
                        prefix += "]"
                        return f"  {prefix} {r.url}"

                    for r in group_rs:
                        print(_url_label(r))
                    for line in fingerprint.splitlines():
                        print(dim("      - " + line))

    # Passed details
    if bool(config.get("print_passed_details", True)):
        passed_all = [r for r in results if r.state == TestState.PASSED]
        if passed_all:
            total_urls = len(url_order)

            by_test_p: Dict[str, List] = defaultdict(list)
            for r in passed_all:
                by_test_p[r.test_name].append(r)

            print("\n" + "-" * 50)
            print("✅ Passing test details")
            for test_name in sorted(by_test_p):
                rs = by_test_p[test_name]
                pass_count = len(rs)
                print(f"\n• {test_name}  {green('PASS')}  {green(f'({pass_count}/{total_urls} URLs)')}")

    # Taboola load time summary table (only when that test was run)
    taboola_results = [r for r in results if getattr(r, "test_name", "") == "taboola_load_time_test"
                       and r.state == TestState.PASSED]
    if taboola_results:
        print("\n" + "-" * 50)
        print("📡 Taboola Load Time Summary  (deltas = time after loader.js ready)")
        col_url  = max(len(r.url) for r in taboola_results)
        col_url  = min(col_url, 80)
        placements = [
            ("mid_article_ii",  "mid-article-ii"),
            ("carousel",        "carousel"),
            ("mid_article_iii", "mid-article-iii"),
        ]
        w = 14
        header = f"{'URL':<{col_url}}  {'Loader start':>12}  {'Loader ready':>12}" + "".join(
            f"  {name:>{w}}" for _, name in placements
        )
        print("\n" + header)
        print("-" * len(header))
        for r in taboola_results:
            meta           = getattr(r, "metadata", {}) or {}
            t_script_start = meta.get("t_script_start_ms")
            t_script       = meta.get("t_script_ms")
            start_str = f"{t_script_start}ms" if t_script_start is not None else "n/a"
            ready_str = f"{t_script}ms"        if t_script       is not None else "n/a"
            url_clip  = r.url[:col_url]
            row = f"{url_clip:<{col_url}}  {start_str:>12}  {ready_str:>12}"
            for key, _ in placements:
                delta = meta.get(f"delta_{key}_ms")
                val   = f"+{delta}ms" if delta is not None else "NOT LOADED"
                row  += f"  {val:>{w}}"
            print(row)
