"""
Generate a Google Sheet from Supabase test results.

Usage:
  python -m tasks.generate_sheet_from_db --run_id <uuid>
  python -m tasks.generate_sheet_from_db --run_id <uuid> --compare_run_id <uuid>

Prints the spreadsheet URL to stdout on success, exits non-zero on failure.
When --compare_run_id is provided, the sheet includes a regression tab comparing
the two runs (run_id = current / "A", compare_run_id = baseline / "B").
"""

import argparse
import asyncio
import sys
from datetime import datetime

import aiohttp

from config.base_config import TestConfig
from core.base_test import TestResult, TestState
from core.sheets_writer import SheetsWriter
from core.supabase_helpers import get_supabase_credentials

TABLE = "test_run_results"

_STATUS_TO_STATE = {
    "PASS":  TestState.PASSED,
    "FAIL":  TestState.FAILED,
    "ERROR": TestState.ERROR,
    "SKIP":  TestState.SKIPPED,
    "N/A":   TestState.NOT_APPLICABLE,
}

_DEVICE_ORDER = ["desktop", "mobile_ios", "mobile_android", "tablet"]


def _rows_to_results(rows: list) -> list:
    results = []
    for row in rows:
        r = TestResult(row["test_name"])
        r.state = _STATUS_TO_STATE.get(row.get("status", ""), TestState.SKIPPED)
        r.device = row.get("device", "unknown")
        r.errors = [row["error_summary"]] if row.get("error_summary") else []
        r.metadata = {
            "context_summary": {
                "db_page_type": row.get("page_type") or "unknown",
                "geo":          row.get("geo", ""),
                "publisher":    row.get("publisher", ""),
                "env":          row.get("environment", ""),
                "device":       row.get("device", ""),
            }
        }
        results.append(r)
    return results


def _regression_diff(current_rows: list, prev_rows: list, prev_run_id: str, prev_timestamp: str) -> dict:
    def _failing(rows):
        return {(r["test_name"], r["device"]) for r in rows if r.get("status") in ("FAIL", "ERROR")}

    curr_failing = _failing(current_rows)
    prev_failing = _failing(prev_rows)
    curr_map = {(r["test_name"], r["device"]): r for r in current_rows}
    prev_map = {(r["test_name"], r["device"]): r for r in prev_rows}
    newly_added = set(curr_map) - set(prev_map)

    def _entry(r):
        return {"test_name": r["test_name"], "device": r["device"], "error_summary": r.get("error_summary")}

    def _entry_new(r):
        return {"test_name": r["test_name"], "device": r["device"],
                "status": r.get("status", ""), "error_summary": r.get("error_summary")}

    return {
        "no_previous_run":        False,
        "previous_run_timestamp": prev_timestamp,
        "previous_run_id":        prev_run_id,
        "using_baseline":         False,
        "geo":                    (current_rows[0].get("geo") if current_rows else ""),
        "newly_added":    sorted([_entry_new(curr_map[k]) for k in newly_added],
                                 key=lambda x: (x["test_name"], x["device"])),
        "new_failures":   sorted([_entry(curr_map[k]) for k in (curr_failing - prev_failing) - newly_added],
                                 key=lambda x: (x["test_name"], x["device"])),
        "known_failures": sorted([_entry(curr_map[k]) for k in curr_failing & prev_failing],
                                 key=lambda x: (x["test_name"], x["device"])),
        "fixed":          sorted([{"test_name": prev_map[k]["test_name"], "device": prev_map[k]["device"]}
                                  for k in prev_failing - curr_failing],
                                 key=lambda x: (x["test_name"], x["device"])),
    }


async def _fetch_rows(session, api_url: str, headers: dict, run_id: str) -> list:
    async with session.get(
        api_url,
        params={"run_id": f"eq.{run_id}", "select": "*"},
        headers=headers,
    ) as resp:
        if not resp.ok:
            text = await resp.text()
            print(f"ERROR: Supabase fetch failed {resp.status}: {text[:200]}", file=sys.stderr)
            sys.exit(1)
        return await resp.json()


async def main():
    parser = argparse.ArgumentParser(description="Generate a Google Sheet from Supabase test results.")
    parser.add_argument("--run_id", required=True, help="Primary run UUID (shown as run A in comparison)")
    parser.add_argument("--compare_run_id", default=None,
                        help="Optional baseline run UUID (shown as run B); enables regression tab")
    args = parser.parse_args()

    config = TestConfig().get_config()
    url, key = get_supabase_credentials(config)

    if not url or not key:
        print("ERROR: Supabase credentials not configured in base_config.py", file=sys.stderr)
        sys.exit(1)

    api_url = url.rstrip("/") + f"/rest/v1/{TABLE}"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    async with aiohttp.ClientSession() as session:
        current_rows = await _fetch_rows(session, api_url, headers, args.run_id)

        compare_rows = []
        if args.compare_run_id:
            compare_rows = await _fetch_rows(session, api_url, headers, args.compare_run_id)

    if not current_rows:
        print(f"ERROR: No rows found for run {args.run_id}", file=sys.stderr)
        sys.exit(1)

    meta = current_rows[0]
    ts_raw = meta.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_raw).strftime("%Y-%m-%d %H:%M")
    except Exception:
        ts = ts_raw[:16].replace("T", " ")

    all_results = _rows_to_results(current_rows)
    device_keys = sorted(
        set(r["device"] for r in current_rows),
        key=lambda d: (_DEVICE_ORDER.index(d) if d in _DEVICE_ORDER else 99),
    )

    regression = None
    if compare_rows:
        cmp_meta = compare_rows[0]
        regression = _regression_diff(
            current_rows, compare_rows,
            prev_run_id=args.compare_run_id,
            prev_timestamp=cmp_meta.get("timestamp", ""),
        )

    run_meta = {
        "timestamp":    ts,
        "site":         meta.get("publisher", ""),
        "env":          meta.get("environment", ""),
        "geo":          meta.get("geo", ""),
        "runner":       "Historical",
        "device_names": {dk: dk.replace("_", " ").title() for dk in device_keys},
        "regression":   regression,
    }

    writer = SheetsWriter(config)
    sheet_url = await writer.write_report(
        all_results=all_results,
        device_keys=device_keys,
        run_meta=run_meta,
    )

    if sheet_url:
        print(sheet_url)
    else:
        print("ERROR: Sheet generation failed — check OAuth credentials and Drive folder config", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
