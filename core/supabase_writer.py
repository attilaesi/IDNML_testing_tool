"""
core/supabase_writer.py
Writes per-run test results to Supabase and computes week-over-week regression diffs.
Only called when --real_run is passed at the CLI.
"""

import uuid
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import aiohttp

from core.base_test import TestResult, TestState
from core.supabase_helpers import get_supabase_credentials

TABLE = "test_run_results"

FAILING = {TestState.FAILED, TestState.ERROR}


def new_run_id() -> str:
    return str(uuid.uuid4())


# ── Helpers to extract run-level context from results ────────────────────────

def _ctx(result: TestResult) -> dict:
    return (result.metadata or {}).get("context_summary") or {}


def geo_from_results(results: List[TestResult]) -> str:
    for r in results:
        geo = _ctx(r).get("geo") or (r.metadata or {}).get("locale")
        if geo:
            return geo.upper()
    return "UNKNOWN"


def publisher_from_results(results: List[TestResult]) -> str:
    for r in results:
        pub = _ctx(r).get("publisher")
        if pub:
            return pub
    return "unknown"


def environment_from_results(results: List[TestResult]) -> str:
    for r in results:
        env = _ctx(r).get("env")
        if env:
            return env
    return "unknown"


# ── Result aggregation ───────────────────────────────────────────────────────

def _aggregate(results: List[TestResult], run_id: str, timestamp: str) -> List[Dict]:
    """
    One row per (test_name, device, geo).  Status is worst-case across all URLs
    for that combination; error_summary from the first failing URL.
    """
    buckets: Dict[Tuple, List[TestResult]] = defaultdict(list)
    for r in results:
        ctx = _ctx(r)
        device = r.device or ctx.get("device") or "unknown"
        geo = (ctx.get("geo") or (r.metadata or {}).get("locale") or "unknown").upper()
        publisher = ctx.get("publisher") or "unknown"
        env = ctx.get("env") or "unknown"
        buckets[(r.test_name, device, geo, publisher, env)].append(r)

    rows = []
    for (test_name, device, geo, publisher, env), group in buckets.items():
        states = [r.state for r in group]
        if TestState.ERROR in states:
            status = "ERROR"
        elif TestState.FAILED in states:
            status = "FAIL"
        elif TestState.PASSED in states:
            status = "PASS"
        else:
            status = "SKIP"

        error_summary = None
        for r in group:
            if r.state in FAILING and r.errors:
                error_summary = str(r.errors[0]).strip().splitlines()[0][:500]
                break

        rows.append({
            "run_id":       run_id,
            "timestamp":    timestamp,
            "geo":          geo,
            "device":       device,
            "publisher":    publisher,
            "environment":  env,
            "test_name":    test_name,
            "status":       status,
            "error_summary": error_summary,
        })

    return rows


# ── Writer ───────────────────────────────────────────────────────────────────

class SupabaseResultsWriter:

    def __init__(self, config: dict):
        self.url, self.key = get_supabase_credentials(config)

    @property
    def _api_url(self) -> str:
        return self.url.rstrip("/") + f"/rest/v1/{TABLE}"

    def _headers(self, write: bool = False) -> dict:
        h = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        }
        if write:
            h["Content-Type"] = "application/json"
            h["Prefer"] = "return=minimal"
        return h

    # ── Write ─────────────────────────────────────────────────────────────────

    async def write_results(
        self,
        results: List[TestResult],
        run_id: str,
        timestamp: str,
    ) -> bool:
        if not self.url or not self.key:
            print("⚠️  Supabase not configured — skipping result upload")
            return False

        rows = _aggregate(results, run_id, timestamp)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._api_url,
                    json=rows,
                    headers=self._headers(write=True),
                ) as resp:
                    if resp.ok:
                        print(f"   ✅ Uploaded {len(rows)} results (run {run_id[:8]}…)")
                        return True
                    text = await resp.text()
                    print(f"   ⚠️  Supabase upload failed {resp.status}: {text[:200]}")
                    return False
        except Exception as e:
            print(f"   ⚠️  Supabase upload error: {e}")
            return False

    # ── Regression diff ───────────────────────────────────────────────────────

    async def fetch_regression_diff(
        self,
        run_id: str,
        publisher: str,
        environment: str,
        geo: str,
    ) -> Optional[Dict]:
        """
        Compare the just-uploaded run against the most recent previous run
        for the same publisher / environment / geo.

        Returns a dict with keys:
          no_previous_run      bool
          previous_run_timestamp  str (ISO)
          new_failures         list[{test_name, device, error_summary}]
          known_failures       list[{test_name, device, error_summary}]
          fixed                list[{test_name, device}]
        """
        if not self.url or not self.key:
            return None

        base_filter = {
            "publisher":   f"eq.{publisher}",
            "environment": f"eq.{environment}",
            "geo":         f"eq.{geo}",
        }
        headers = self._headers()

        try:
            async with aiohttp.ClientSession() as session:

                # 1. Current run rows
                async with session.get(
                    self._api_url,
                    params={
                        **base_filter,
                        "run_id": f"eq.{run_id}",
                        "select": "test_name,device,status,error_summary",
                    },
                    headers=headers,
                ) as resp:
                    if not resp.ok:
                        return None
                    current_rows = await resp.json()

                # 2. Most recent previous run_id (one row, just need id + timestamp)
                async with session.get(
                    self._api_url,
                    params={
                        **base_filter,
                        "run_id": f"neq.{run_id}",
                        "select": "run_id,timestamp",
                        "order":  "timestamp.desc",
                        "limit":  "1",
                    },
                    headers=headers,
                ) as resp:
                    if not resp.ok:
                        return None
                    pivot = await resp.json()

                if not pivot:
                    return {"no_previous_run": True}

                prev_run_id = pivot[0]["run_id"]
                prev_timestamp = pivot[0]["timestamp"]

                # 3. Previous run rows
                async with session.get(
                    self._api_url,
                    params={
                        **base_filter,
                        "run_id": f"eq.{prev_run_id}",
                        "select": "test_name,device,status,error_summary",
                    },
                    headers=headers,
                ) as resp:
                    if not resp.ok:
                        return None
                    prev_rows = await resp.json()

        except Exception as e:
            print(f"   ⚠️  Regression fetch error: {e}")
            return None

        def _failing(rows):
            return {
                (r["test_name"], r["device"])
                for r in rows
                if r["status"] in ("FAIL", "ERROR")
            }

        curr_failing = _failing(current_rows)
        prev_failing = _failing(prev_rows)
        curr_map = {(r["test_name"], r["device"]): r for r in current_rows}
        prev_map = {(r["test_name"], r["device"]): r for r in prev_rows}

        def _entry(r):
            return {
                "test_name":     r["test_name"],
                "device":        r["device"],
                "error_summary": r.get("error_summary"),
            }

        return {
            "no_previous_run":        False,
            "previous_run_timestamp": prev_timestamp,
            "geo":                    geo,
            "new_failures":   sorted([_entry(curr_map[k]) for k in curr_failing - prev_failing],
                                     key=lambda x: (x["test_name"], x["device"])),
            "known_failures": sorted([_entry(curr_map[k]) for k in curr_failing & prev_failing],
                                     key=lambda x: (x["test_name"], x["device"])),
            "fixed":          sorted([{"test_name": prev_map[k]["test_name"],
                                       "device":    prev_map[k]["device"]}
                                      for k in prev_failing - curr_failing],
                                     key=lambda x: (x["test_name"], x["device"])),
        }
