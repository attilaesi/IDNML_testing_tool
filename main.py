# main.py
import argparse
import asyncio
import time
from collections import defaultdict
from typing import List, Any, Dict, Tuple

from core.base_test import TestState
from core.ansi import green, red, yellow, dim

# Try to use CONFIG if it's exported; otherwise build it from TestConfig
try:
    from config.base_config import CONFIG
except ImportError:
    from config.base_config import TestConfig

    CONFIG = TestConfig().get_config()

from core.framework_manager import TestFramework


def _short_hint(msg: Any, max_len: int = 28) -> str:
    if msg is None:
        return ""
    s = str(msg).strip().splitlines()[0] if str(msg).strip() else ""
    if not s:
        return ""
    return s[:max_len] + ("…" if len(s) > max_len else "")


def _format_cell(state: TestState, errors, warnings) -> str:
    """Render a compact status label for the matrix cells."""
    if state == TestState.PASSED:
        return "PASS"
    if state == TestState.SKIPPED:
        return "SKIP"
    if state == TestState.ERROR:
        hint = _short_hint(errors[0]) if errors else ""
        return f"ERROR ({hint})" if hint else "ERROR"
    if state == TestState.FAILED:
        msgs = errors if errors else warnings
        hint = _short_hint(msgs[0]) if msgs else ""
        return f"FAIL ({hint})" if hint else "FAIL"
    return str(state)


def _print_matrix_summary(results, url_order: List[str] = None) -> None:
    """Print a test-by-URL matrix + URL key.

    Rows: test names
    Cols: URL1..URLN (in the provided url_order; otherwise first-seen order from results)
    Cells: PASS/FAIL/SKIP/ERROR (FAIL/ERROR may include short hint)
    """

    # URL order (prefer framework-provided order; otherwise first-seen)
    if url_order is None:
        url_order = []
        seen_urls = set()
        for r in results:
            if getattr(r, "url", None) and r.url not in seen_urls:
                seen_urls.add(r.url)
                url_order.append(r.url)

    urls = list(url_order or [])
    url_labels = [f"URL{i}" for i in range(1, len(urls) + 1)]
    url_to_label = {u: lbl for u, lbl in zip(urls, url_labels)}

    # Test name order (sorted for stable scan)
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
        matrix[t][lbl] = _format_cell(
            r.state,
            getattr(r, "errors", None) or [],
            getattr(r, "warnings", None) or [],
        )

    # Prepare rows
    header = ["Test"] + url_labels
    rows = []
    for t in test_names:
        row = [t] + [matrix[t].get(lbl, "-") for lbl in url_labels]
        rows.append(row)

    # Column widths
    widths = [len(h) for h in header]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))

    def fmt_row(cols):
        return " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(cols))

    sep = "-+-".join("-" * w for w in widths)

    print("\n" + "=" * 50)
    print("📊 TEST MATRIX (rows=tests, cols=URLs)")
    print("=" * 50)
    print(fmt_row(header))
    print(sep)
    for row in rows:
        print(fmt_row(row))

    print("\nURL KEY")
    for i, u in enumerate(urls, start=1):
        print(f"URL{i} = {u}")


def _get_url_order(framework: TestFramework, results) -> List[str]:
    # Prefer framework URL order if present
    url_order = list(getattr(framework, "selected_urls", []) or [])
    if url_order:
        return url_order

    # Fallback: first-seen order from results
    seen = set()
    url_order = []
    for r in results:
        if getattr(r, "url", None) and r.url not in seen:
            url_order.append(r.url)
            seen.add(r.url)
    return url_order


def _unique_test_summary(executed_results) -> Dict[str, int]:
    """
    Summarise by UNIQUE test names (not test×URL rows).

    Per-test aggregation rule:
      - ERROR if the test errors on ANY URL
      - FAILED if it fails on ANY URL (and no ERROR)
      - PASSED if it PASSES on ALL URLs where it ran (excluding SKIP)
      - MIXED otherwise (e.g. some PASS, some SKIP only, etc.)
    """
    # group by test_name
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
    """
    Per-URL row-based counts (this *is* test×URL, but it makes sense per URL).
    """
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


async def main():
    parser = argparse.ArgumentParser(description="Ad Testing Framework")
    parser.add_argument(
        "--test",
        metavar="TEST_NAME",
        help="Run only this test (e.g. gpt_gam_bid_keys_test). Omit to run all tests.",
    )
    args = parser.parse_args()

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

    # Run one test or all
    test_names = [args.test] if args.test else None
    _t_start = time.monotonic()
    results = await framework.run_tests(test_names=test_names)
    _elapsed = time.monotonic() - _t_start

    # ------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------
    executed = [r for r in results if r.state not in (TestState.SKIPPED,)]
    url_order = _get_url_order(framework, results)

    # Unique-test summary (fixes the misleading counts)
    uniq = _unique_test_summary(executed)

    parts = [
        f"✅ {green(str(uniq['passed_unique']))} passed",
        f"❌ {red(str(uniq['failed_unique']))} failed",
        f"💥 {red(str(uniq['errors_unique']))} errors",
    ]
    if uniq["mixed_unique"]:
        parts.append(f"🟨 {yellow(str(uniq['mixed_unique']))} mixed")
    summary_line = "  |  ".join(parts)

    mins, secs = divmod(int(_elapsed), 60)
    elapsed_str = f"{mins}m {secs}s" if mins else f"{secs}s"

    print("\n" + "=" * 50)
    print(f"📊 {uniq['total_unique']} tests  ⏱ {elapsed_str}   {summary_line}")

    # Optional: per-URL summary (row-based, useful in practice)
    if bool(CONFIG.get("print_summary_per_url", True)):
        per_url = _per_url_summary(executed, url_order)
        print("\n" + "-" * 50)
        print("📍 Per-URL summary (row-based)")
        for idx, (u, s) in enumerate(per_url, start=1):
            print(
                f"URL{idx}: executed={s['executed_rows']} "
                f"pass={s['passed_rows']} fail={s['failed_rows']} err={s['error_rows']}  |  {u}"
            )

    # ------------------------------------------------------------------
    # MATRIX SUMMARY
    #
    # Your patched framework_manager.py already prints the matrix at the end
    # of the run. This keeps main.py compatible:
    #  - If manager printed it already, we can skip here (default).
    #  - If you want main.py to print it too, set config: print_matrix_in_main=True
    # ------------------------------------------------------------------
    if bool(CONFIG.get("print_matrix_in_main", False)):
        _print_matrix_summary(results, url_order=url_order)

    # ------------------------------------------------------------------
    # FAILED/ERROR DETAILS — grouped by test, listing failing URLs
    # ------------------------------------------------------------------
    if bool(CONFIG.get("print_failed_details", True)):
        failed_or_err_all = [
            r for r in results if r.state in (TestState.FAILED, TestState.ERROR)
        ]
        if failed_or_err_all:
            url_to_label = {u: f"URL{idx+1}" for idx, u in enumerate(url_order)}
            total_urls = len(url_order)

            # Build URL -> page_type from result metadata
            url_to_pagetype: Dict[str, str] = {}
            for r in results:
                u = getattr(r, "url", None)
                if u and u not in url_to_pagetype:
                    pt = (getattr(r, "metadata", None) or {}).get("page_type") or "unknown"
                    url_to_pagetype[u] = pt

            # Group by test name, preserving test order from the matrix
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
                # Sort by URL order
                rs_sorted = sorted(rs, key=lambda r: url_order.index(r.url) if r.url in url_order else 999)
                # Group URLs that share an identical error fingerprint
                from collections import OrderedDict
                fingerprint_groups: "OrderedDict[str, list]" = OrderedDict()
                for r in rs_sorted:
                    msgs = r.errors if r.errors else r.warnings
                    fingerprint = "\n".join(str(m) for m in (msgs or []))
                    if fingerprint not in fingerprint_groups:
                        fingerprint_groups[fingerprint] = []
                    fingerprint_groups[fingerprint].append(r)

                for fingerprint, group_rs in fingerprint_groups.items():
                    if len(group_rs) == 1:
                        r = group_rs[0]
                        label = url_to_label.get(r.url, r.url)
                        page_type = url_to_pagetype.get(r.url, "unknown")
                        print(f"  {label}  [{page_type}]  {dim(r.url)}")
                        layout_ctx = (getattr(r, "metadata", None) or {}).get("layout_context")
                        if layout_ctx:
                            print(f"  {dim('[' + layout_ctx + ']')}")
                    else:
                        labels = ", ".join(
                            f"{url_to_label.get(r.url, r.url)} [{url_to_pagetype.get(r.url, '?')}]"
                            for r in group_rs
                        )
                        print(f"  {labels}")
                        layout_ctx = (getattr(group_rs[0], "metadata", None) or {}).get("layout_context")
                        if layout_ctx:
                            print(f"  {dim('[' + layout_ctx + ']')}")
                    for line in fingerprint.splitlines():
                        print(dim("      - " + line))

    # ------------------------------------------------------------------
    # PASSED DETAILS — grouped by test, listing passing URLs
    # ------------------------------------------------------------------
    if bool(CONFIG.get("print_passed_details", True)):
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

    # ------------------------------------------------------------------
    # OPTIONAL: write text report (only if your CSVWriter has it)
    # ------------------------------------------------------------------
    if bool(CONFIG.get("write_text_report", True)):
        try:
            await framework.csv_writer.write_text_report(results, urls=url_order)
        except Exception:
            # keep silent to avoid breaking runs if writer not updated yet
            pass

    print()  # final newline


if __name__ == "__main__":
    asyncio.run(main())