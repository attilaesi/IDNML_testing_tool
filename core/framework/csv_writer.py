# core/framework/csv_writer.py

import csv
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from core.base_test import TestResult, TestState


class CSVWriter:
    """
    Generates ONE clean, Google-Sheets-friendly CSV report:

    A) Compact Results Matrix (uniform 5-char status cells: PASS/FAIL/SKIP/ERROR/MIXED)
    B) Unique Test Summary
    C) Failure Details (full reasons outside grid)
    D) URL Map (U# → page type → URL)

    No legacy reports.
    """

    def __init__(self, config: Dict):
        self.config = config
        self._report_written = False

    async def write_main(self, results: List[TestResult]):
        await self.write_report(results)

    async def write_pagetype_summary(self, results: List[TestResult]):
        return

    async def write_text_report(self, results: List[TestResult], urls: Optional[List[str]] = None):
        return

    async def write_report(self, results: List[TestResult], urls: Optional[List[str]] = None):
        if not results or self._report_written:
            return
        self._report_written = True

        output_file = self.config.get("output_report_csv", "output/output_report.csv")
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # -------------------------
        # URLs in stable order
        # -------------------------
        if not urls:
            seen = set()
            urls = []
            for r in results:
                u = getattr(r, "url", None)
                if u and u not in seen:
                    seen.add(u)
                    urls.append(u)

        url_to_u = {u: f"U{i}" for i, u in enumerate(urls, start=1)}

        # page type per URL (video/display/unknown)
        url_page_type: Dict[str, str] = {}
        for r in results:
            u = getattr(r, "url", None)
            if not u or u in url_page_type:
                continue
            meta = getattr(r, "metadata", None) or {}
            pt = ""
            if isinstance(meta, dict):
                pt = str(meta.get("page_type") or "").strip().lower()

            if pt == "video":
                url_page_type[u] = "video"
            elif pt:
                url_page_type[u] = "display"
            else:
                url_page_type[u] = "unknown"

        # tests (stable)
        test_names = sorted({r.test_name for r in results if getattr(r, "test_name", None)})

        # result index
        result_map: Dict[Tuple[str, str], TestResult] = {}
        for r in results:
            if getattr(r, "url", None):
                result_map[(r.test_name, r.url)] = r

        # -------------------------
        # Uniform 5-char cell tokens
        # -------------------------
        def cell_token(state: TestState) -> str:
            # 5-char tokens (Sheets-friendly and visually uniform)
            if state == TestState.PASSED:
                return "PASS "   # 5
            if state == TestState.FAILED:
                return "FAIL "   # 5
            if state == TestState.SKIPPED:
                return "SKIP "   # 5
            if state == TestState.ERROR:
                return "ERROR"   # 5
            return ""

        # -------------------------
        # Unique per-test aggregation
        # -------------------------
        executed_results = [r for r in results if r.state != TestState.SKIPPED]
        executed_tests = sorted({r.test_name for r in executed_results})

        per_test_state: Dict[str, str] = {}
        for t in executed_tests:
            rs = [r for r in executed_results if r.test_name == t]
            if any(r.state == TestState.ERROR for r in rs):
                per_test_state[t] = "ERROR"
            elif any(r.state == TestState.FAILED for r in rs):
                per_test_state[t] = "FAIL "  # keep 5-char style
            elif rs and all(r.state == TestState.PASSED for r in rs):
                per_test_state[t] = "PASS "
            else:
                per_test_state[t] = "MIXED"

        total_tests = len(executed_tests)
        passed_unique = sum(1 for s in per_test_state.values() if s.strip() == "PASS")
        failed_unique = sum(1 for s in per_test_state.values() if s.strip() == "FAIL")
        error_unique = sum(1 for s in per_test_state.values() if s.strip() == "ERROR")
        mixed_unique = sum(1 for s in per_test_state.values() if s.strip() == "MIXED")

        # -------------------------
        # Failure details list
        # -------------------------
        failing_results = [r for r in results if r.state in (TestState.FAILED, TestState.ERROR)]

        # -------------------------
        # Section separators (strong in Sheets)
        # -------------------------
        def blank_rows(w, n=1):
            for _ in range(n):
                w.writerow([])

        def section_header(w, title: str):
            blank_rows(w, 2)
            w.writerow(["================================================================"])
            w.writerow([title])
            w.writerow(["================================================================"])
            blank_rows(w, 1)

        # -------------------------
        # Write CSV
        # -------------------------
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)

            # ===============================
            # SECTION A — MATRIX
            # ===============================
            w.writerow(["RESULTS MATRIX (rows=tests, cols=URLs)"])
            blank_rows(w, 1)

            u_cols = [url_to_u[u] for u in urls]
            w.writerow(["Test"] + u_cols + ["Overall"])

            for t in test_names:
                row = [t]
                for u in urls:
                    res = result_map.get((t, u))
                    row.append(cell_token(res.state) if res else "")
                row.append(per_test_state.get(t, ""))  # already 5-char style
                w.writerow(row)

            # ===============================
            # SECTION B — SUMMARY
            # ===============================
            section_header(w, "TEST SUMMARY (unique tests; not test×URL)")
            w.writerow(["Metric", "Value"])
            w.writerow(["Total URLs", len(urls)])
            w.writerow(["Total tests executed (unique, excluding SKIP)", total_tests])
            w.writerow(["Passed (unique)", passed_unique])
            w.writerow(["Failed (unique)", failed_unique])
            w.writerow(["Errors (unique)", error_unique])
            if mixed_unique:
                w.writerow(["Mixed (unique)", mixed_unique])

            # ===============================
            # SECTION C — FAILURE DETAILS
            # ===============================
            section_header(w, "FAILURE DETAILS (full reasons outside the grid)")
            w.writerow(["U#", "Test", "State", "Reason"])

            # Keep URL order; then stable test order
            by_url: Dict[str, List[TestResult]] = {}
            for r in failing_results:
                by_url.setdefault(r.url, []).append(r)

            for u in urls:
                group = by_url.get(u, [])
                if not group:
                    continue
                group_sorted = sorted(group, key=lambda r: str(r.test_name or ""))
                for r in group_sorted:
                    state_val = "ERROR" if r.state == TestState.ERROR else "FAIL "
                    msgs = r.errors if r.errors else (r.warnings or [])
                    if not msgs:
                        w.writerow([url_to_u.get(u, ""), r.test_name, state_val, ""])
                        continue

                    first = True
                    for entry in msgs:
                        lines = str(entry).splitlines() or [""]
                        for line in lines:
                            if first:
                                w.writerow([url_to_u.get(u, ""), r.test_name, state_val, line])
                                first = False
                            else:
                                w.writerow(["", "", "", line])

            # ===============================
            # SECTION D — URL MAP
            # ===============================
            section_header(w, "URL MAP (U# → page type → URL)")
            w.writerow(["U#", "PageType", "URL"])
            for u in urls:
                w.writerow([url_to_u[u], url_page_type.get(u, "unknown"), u])

        print(f"📄 Report written to: {output_path}")