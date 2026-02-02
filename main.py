# main.py
import asyncio
from collections import defaultdict
from typing import List, Dict, Any

from core.base_test import TestState

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


async def main():
    print("🚀 Ad Testing Framework")
    print(f"Active site: {CONFIG.get('active_site', '')}")
    print(f"Site URL: {CONFIG.get('site_url', '')}")
    print(f"Max pages: {CONFIG.get('max_pages', 10)}")
    print(f"Mobile mode: {CONFIG.get('mobile', False)}")
    print(f"Headless: {CONFIG.get('headless', True)}")
    print("-" * 50)

    framework = TestFramework(CONFIG)
    framework.discover_tests()

    # Run everything
    results = await framework.run_tests()

    # ------------------------------------------------------------------
    # SUMMARY (exclude skipped from counts)
    # ------------------------------------------------------------------
    executed = [r for r in results if r.state not in (TestState.SKIPPED,)]

    passed = sum(1 for r in executed if r.state == TestState.PASSED)
    failed = sum(1 for r in executed if r.state == TestState.FAILED)
    errors = sum(1 for r in executed if r.state == TestState.ERROR)

    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY (overall)")
    print(f"Total executed tests: {len(executed)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"💥 Errors: {errors}")

    # ------------------------------------------------------------------
    # MATRIX SUMMARY
    #
    # Your patched framework_manager.py already prints the matrix at the end
    # of the run. This keeps main.py compatible:
    #  - If manager printed it already, we can skip here (default).
    #  - If you want main.py to print it too, set config: print_matrix_in_main=True
    # ------------------------------------------------------------------
    if bool(CONFIG.get("print_matrix_in_main", False)):
        url_order = getattr(framework, "selected_urls", None)
        _print_matrix_summary(results, url_order=url_order)

    # ------------------------------------------------------------------
    # FAILED/ERROR DETAILS (optional, compact)
    # ------------------------------------------------------------------
    if bool(CONFIG.get("print_failed_details", True)):
        failed_or_err_all = [
            r for r in results if r.state in (TestState.FAILED, TestState.ERROR)
        ]
        if failed_or_err_all:
            # Prefer framework URL order if present
            url_order = list(getattr(framework, "selected_urls", []) or [])
            if not url_order:
                seen = set()
                for r in results:
                    if getattr(r, "url", None) and r.url not in seen:
                        url_order.append(r.url)
                        seen.add(r.url)

            url_to_label = {u: f"U{idx+1}" for idx, u in enumerate(url_order)}
            grouped = defaultdict(list)
            for r in failed_or_err_all:
                grouped[r.url].append(r)

            print("\n" + "-" * 50)
            print("🔍 Failed / Error details")
            for u in url_order:
                if u not in grouped:
                    continue
                print(f"\n{url_to_label[u]}: {u}")
                for r in grouped[u]:
                    print(f"  • {r.test_name} ({r.state.value})")
                    msgs = r.errors if r.errors else r.warnings
                    for entry in (msgs or []):
                        for line in str(entry).splitlines():
                            print("      - " + line)

    print()  # final newline


if __name__ == "__main__":
    asyncio.run(main())