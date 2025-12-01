# core/framework/csv_writer.py

import csv
from pathlib import Path
from typing import List, Dict, Tuple

from core.base_test import TestResult


class CSVWriter:
    def __init__(self, config: Dict):
        self.config = config

    # ---------- Main test × URL CSV ----------

    async def write_main(self, results: List[TestResult]):
        if not results:
            return

        # Use configured path, defaulting inside output/
        output_file = self.config.get("output_file", "output/output.csv")
        output_path = Path(output_file)

        # Ensure parent directory exists
        if output_path.parent:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Unique URLs (columns)
        urls: List[str] = []
        for r in results:
            if getattr(r, "url", None) and r.url not in urls:
                urls.append(r.url)

        # URL -> page_type
        url_page_type: Dict[str, str] = {}
        for r in results:
            url = getattr(r, "url", None)
            if not url:
                continue
            meta = getattr(r, "metadata", None)
            if isinstance(meta, dict):
                pt = meta.get("page_type")
                if pt and url not in url_page_type:
                    url_page_type[url] = str(pt)

        # Unique test names
        test_names: List[str] = []
        for r in results:
            if r.test_name not in test_names:
                test_names.append(r.test_name)

        # Index results by (test_name, url)
        result_map: Dict[Tuple[str, str], TestResult] = {}
        for r in results:
            url = getattr(r, "url", None)
            if url:
                result_map[(r.test_name, url)] = r

        # Header
        header_labels: List[str] = []
        for url in urls:
            pt = url_page_type.get(url)
            header_labels.append(f"{url} ({pt})" if pt else url)

        cols = ["TestName"] + header_labels

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()

            for test_name in test_names:
                row: Dict[str, str] = {"TestName": test_name}
                for url, col_name in zip(urls, header_labels):
                    res = result_map.get((test_name, url))
                    if not res:
                        row[col_name] = ""
                        continue
                    status = res.state.value if hasattr(res, "state") else "UNKNOWN"
                    if res.errors:
                        detail = "; ".join(res.errors)
                        row[col_name] = f"{status}\n{detail}"
                    else:
                        row[col_name] = status
                writer.writerow(row)

        print(f"📄 Results written to: {output_path}")

    # ---------- Page-type summary CSV ----------

    async def write_pagetype_summary(self, results: List[TestResult]):
        if not results:
            return

        # Use configured path, defaulting inside output/
        output_file = self.config.get(
            "output_pagetype_file", "output/output_by_pagetype.csv"
        )
        output_path = Path(output_file)

        # Ensure parent directory exists
        if output_path.parent:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        page_types: List[str] = []
        pt_urls: Dict[str, set[str]] = {}

        for r in results:
            url = getattr(r, "url", None)
            meta = getattr(r, "metadata", None)
            pt = None
            if isinstance(meta, dict):
                pt = meta.get("page_type")
            if not pt:
                pt = "unknown"
            pt = str(pt)
            if pt not in page_types:
                page_types.append(pt)
            if url:
                pt_urls.setdefault(pt, set()).add(url)

        if "unknown" in page_types and len(page_types) > 1:
            # Move 'unknown' to the end if there's at least one known type
            page_types = [p for p in page_types if p != "unknown"] + ["unknown"]

        test_names: List[str] = []
        for r in results:
            if r.test_name not in test_names:
                test_names.append(r.test_name)

        grouped: Dict[Tuple[str, str], List[TestResult]] = {}
        for r in results:
            meta = getattr(r, "metadata", None)
            pt = None
            if isinstance(meta, dict):
                pt = meta.get("page_type")
            if not pt:
                pt = "unknown"
            pt = str(pt)
            key = (r.test_name, pt)
            grouped.setdefault(key, []).append(r)

        def summarise(cell_results: List[TestResult]) -> str:
            if not cell_results:
                return ""
            error_res = next(
                (cr for cr in cell_results if cr.state.name == "ERROR"), None
            )
            if error_res:
                msg = "; ".join(error_res.errors) if error_res.errors else ""
                return f"ERROR\n{msg}" if msg else "ERROR"
            fail_res = next(
                (cr for cr in cell_results if cr.state.name == "FAILED"), None
            )
            if fail_res:
                msg = "; ".join(fail_res.errors) if fail_res.errors else ""
                return f"FAILED\n{msg}" if msg else "FAILED"
            passed = any(cr.state.name == "PASSED" for cr in cell_results)
            if passed:
                return "PASSED"
            any_state = (
                cell_results[0].state.value
                if hasattr(cell_results[0], "state")
                else "UNKNOWN"
            )
            return any_state

        cols = ["TestName"] + page_types

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()

            for test_name in test_names:
                row: Dict[str, str] = {"TestName": test_name}
                for pt in page_types:
                    cell_results = grouped.get((test_name, pt), [])
                    row[pt] = summarise(cell_results)
                writer.writerow(row)

            writer.writerow({})
            writer.writerow({"TestName": "Page types (page_type -> URLs):"})
            for pt in page_types:
                urls_for_pt = sorted(pt_urls.get(pt, []))
                if not urls_for_pt:
                    continue
                joined = "; ".join(urls_for_pt)
                writer.writerow({"TestName": f"{pt}: {joined}"})

        print(f"📄 Page-type summary written to: {output_path}")