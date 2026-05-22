# core/sheets_writer.py
"""
Write ad test results to a new timestamped Google Spreadsheet.

Sheet structure
───────────────
  Tab "Summary"         — Run header, per-device pass-rate counts, cross-device
                          comparison matrix.  FAIL/MIXED cells are hyperlinks that
                          jump directly to the relevant row in the device tab.
  Tab "desktop"         — Test × URL matrix, failure details, URL key.
  Tab "mobile_ios"      — Same layout.
  Tab "mobile_android"  — Same layout.
  Tab "tablet"          — Same layout.

Authentication
──────────────
  Set env var GOOGLE_SERVICE_ACCOUNT_JSON to either:
    • path to a service account JSON key file, OR
    • the JSON content itself (useful in CI pipelines)

  Optionally set SHEETS_SHARE_EMAIL (or config["sheets_share_email"]) to
  share the new spreadsheet with your personal Google account automatically.

  See README → Google Sheets Setup for step-by-step instructions.
"""

import asyncio
import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from core.base_test import TestResult, TestState


# ── Colour palette (RGB 0-1 floats) ──────────────────────────────────────────
#   #B7E1CD  pastel green  → PASS
#   #F4C7C3  pastel red    → FAIL
#   #E06666  strong red    → ERROR
#   #F3F3F3  light grey    → SKIP / dash
#   #FCE8B2  amber         → MIXED
#   #1F3864  navy          → primary headers
#   #445FA0  mid blue      → secondary headers
_PALETTE: Dict[str, Tuple[float, float, float]] = {
    "pass":       (0.718, 0.882, 0.804),
    "fail":       (0.957, 0.780, 0.765),
    "error":      (0.878, 0.400, 0.400),
    "skip":       (0.953, 0.953, 0.953),
    "mixed":      (0.988, 0.910, 0.698),
    "header_dk":  (0.122, 0.220, 0.392),
    "header_md":  (0.267, 0.400, 0.600),
    "white":      (1.0,   1.0,   1.0),
    "dash":       (0.850, 0.850, 0.850),
}


# ── A1 notation helpers ───────────────────────────────────────────────────────

def _a1(row: int, col: int) -> str:
    letters = ""
    c = col
    while c > 0:
        c -= 1
        letters = chr(65 + c % 26) + letters
        c //= 26
    return f"{letters}{row}"


def _rng(r1: int, c1: int, r2: int, c2: int) -> str:
    return f"{_a1(r1, c1)}:{_a1(r2, c2)}"


# ── Data helpers ──────────────────────────────────────────────────────────────

def _stable_urls(results: List[TestResult]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for r in results:
        u = getattr(r, "url", None)
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _url_page_types(results: List[TestResult]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for r in results:
        u = getattr(r, "url", None)
        if not u or u in out:
            continue
        meta = getattr(r, "metadata", None) or {}
        pt = str(meta.get("page_type") or "").strip().lower() if isinstance(meta, dict) else ""
        out[u] = pt or "unknown"
    return out


def _agg_cell(states: List[TestState]) -> str:
    if not states:
        return "-"
    total = len(states)
    n_fail = sum(1 for s in states if s in (TestState.FAILED, TestState.ERROR))
    n_skip = sum(1 for s in states if s == TestState.SKIPPED)
    n_pass = sum(1 for s in states if s == TestState.PASSED)
    if n_fail:
        return f"FAIL ({n_fail}/{total})" if n_fail < total else "FAIL"
    if n_skip == total:
        return "SKIP"
    if n_pass == total:
        return "PASS"
    return "MIXED"


def _state_ck(state: TestState) -> str:
    if state == TestState.PASSED:
        return "pass"
    if state == TestState.FAILED:
        return "fail"
    if state == TestState.ERROR:
        return "error"
    if state == TestState.SKIPPED:
        return "skip"
    return "skip"


def _agg_ck(cell: str) -> str:
    t = cell.upper().strip()
    if t == "PASS":
        return "pass"
    if t.startswith("FAIL"):
        return "fail"
    if t == "ERROR":
        return "error"
    if t == "SKIP":
        return "skip"
    if t == "MIXED":
        return "mixed"
    return "dash"


# ── Writer ────────────────────────────────────────────────────────────────────

class SheetsWriter:
    """
    Creates a new Google Spreadsheet for every run and writes formatted results.
    All gspread calls are synchronous; the public async API runs them in a thread pool.
    """

    def __init__(self, config: dict):
        self.config = config

    # ── Public async entry point ──────────────────────────────────────────────

    async def write_report(
        self,
        all_results: List[TestResult],
        device_keys: List[str],
        run_meta: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Create a new spreadsheet and write all results.
        Returns the spreadsheet URL, or None on failure.
        """
        meta = dict(run_meta or {})
        meta.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M"))
        return await asyncio.to_thread(
            self._write_sync, all_results, device_keys, meta
        )

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _build_client(self):
        """Return (gspread_client, credentials) tuple."""
        try:
            import gspread
            from google.oauth2.service_account import Credentials as SACredentials
        except ImportError:
            raise ImportError(
                "gspread not installed.  Run: pip install gspread gspread-formatting"
            )
        sa_json = (
            self.config.get("sheets_service_account_json")
            or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        )
        if not sa_json:
            raise EnvironmentError(
                "GOOGLE_SERVICE_ACCOUNT_JSON env var not set — "
                "see README → Google Sheets Setup."
            )
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        if os.path.isfile(sa_json):
            creds = SACredentials.from_service_account_file(sa_json, scopes=scopes)
        else:
            creds = SACredentials.from_service_account_info(json.loads(sa_json), scopes=scopes)
        return gspread.Client(auth=creds), creds

    # ── Sync orchestrator ─────────────────────────────────────────────────────

    def _write_sync(
        self,
        all_results: List[TestResult],
        device_keys: List[str],
        run_meta: dict,
    ) -> Optional[str]:
        try:
            from gspread_formatting import (  # noqa: F401
                CellFormat, Color, TextFormat,
                format_cell_ranges, set_frozen,
            )
        except ImportError:
            print("⚠️  gspread-formatting not installed.  Run: pip install gspread-formatting")
            return None

        try:
            client, creds = self._build_client()
        except Exception as e:
            print(f"⚠️  Google Sheets auth failed: {e}")
            return None

        ts = run_meta.get("timestamp", "")
        site = run_meta.get("site", "")
        title = f"Ad Tests — {ts}" + (f"  [{site}]" if site else "")

        try:
            folder_id = (
                self.config.get("sheets_drive_folder_id")
                or os.getenv("SHEETS_DRIVE_FOLDER_ID")
            )
            if folder_id:
                # Create directly in the user's Drive folder so it uses the
                # user's storage quota rather than the service account's.
                from google.auth.transport.requests import AuthorizedSession
                session = AuthorizedSession(creds)
                resp = session.post(
                    "https://www.googleapis.com/drive/v3/files",
                    json={
                        "name": title,
                        "mimeType": "application/vnd.google-apps.spreadsheet",
                        "parents": [folder_id],
                    },
                    params={"fields": "id"},
                )
                resp.raise_for_status()
                spreadsheet = client.open_by_key(resp.json()["id"])
            else:
                spreadsheet = client.create(title)
        except Exception as e:
            print(f"⚠️  Failed to create Google Sheet: {e}")
            return None

        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
        print(f"\n📊 Creating Google Sheet: {title}")

        share_email = (
            self.config.get("sheets_share_email")
            or os.getenv("SHEETS_SHARE_EMAIL")
        )
        if share_email:
            try:
                spreadsheet.share(share_email, perm_type="user", role="writer")
                print(f"   Shared with: {share_email}")
            except Exception as e:
                print(f"   ⚠️  Share failed: {e}")

        # Write per-device tabs first — need their GIDs for summary hyperlinks
        device_tab_info: Dict[str, Tuple[int, Dict[str, int]]] = {}
        # key → (worksheet_gid, {test_name: row_number})

        for i, dk in enumerate(device_keys):
            dev_results = [r for r in all_results if getattr(r, "device", "") == dk]
            if i == 0:
                ws = spreadsheet.sheet1
                ws.update_title(dk)
            else:
                ws = spreadsheet.add_worksheet(title=dk, rows=400, cols=40)
            try:
                test_row_map = self._write_device_tab(ws, dev_results, dk, run_meta)
                device_tab_info[dk] = (ws.id, test_row_map)
                print(f"   ✅ {dk}")
            except Exception as e:
                print(f"   ⚠️  Error writing tab '{dk}': {e}")
                device_tab_info[dk] = (getattr(ws, "id", 0), {})

        # Write Summary tab (last, so we have all GIDs)
        try:
            summary_ws = spreadsheet.add_worksheet(title="Summary", rows=300, cols=20)
            self._write_summary_tab(
                summary_ws, all_results, device_keys, device_tab_info, run_meta
            )
            print("   ✅ Summary")
        except Exception as e:
            print(f"   ⚠️  Error writing Summary tab: {e}")

        # Move Summary to position 0
        try:
            ws_by_title = {w.title: w for w in spreadsheet.worksheets()}
            ordered = (
                ([ws_by_title["Summary"]] if "Summary" in ws_by_title else [])
                + [ws_by_title[dk] for dk in device_keys if dk in ws_by_title]
            )
            if ordered:
                spreadsheet.reorder_worksheets(ordered)
        except Exception:
            pass

        print(f"\n📊 Report: {url}")
        return url

    # ── Per-device tab ────────────────────────────────────────────────────────

    def _write_device_tab(
        self,
        ws,
        results: List[TestResult],
        device_key: str,
        run_meta: dict,
    ) -> Dict[str, int]:
        """
        Write test matrix, failure details, and URL key for one device.
        Returns {test_name: row_number} for cross-sheet hyperlinks in Summary.
        """
        from gspread_formatting import (
            CellFormat, Color, TextFormat,
            format_cell_ranges, set_frozen,
        )

        def _c(key: str) -> Color:
            return Color(*_PALETTE[key])

        data: List[List] = []
        fmts: List[Tuple] = []

        def row() -> int:
            return len(data) + 1

        def fmt(r1, c1, r2, c2, f: CellFormat) -> None:
            fmts.append((_rng(r1, c1, r2, c2), f))

        urls = _stable_urls(results)
        page_types = _url_page_types(results)
        test_names = sorted({r.test_name for r in results if r.test_name})
        result_map: Dict[Tuple[str, str], TestResult] = {}
        for r in results:
            if r.url:
                result_map[(r.test_name, r.url)] = r

        n_url_cols = len(urls)
        total_cols = 1 + n_url_cols + 1  # Test | U1..Un | Overall

        playwright_name = run_meta.get("device_names", {}).get(device_key, "")
        device_display = device_key.replace("_", " ").upper()
        site = run_meta.get("site", "")
        ts = run_meta.get("timestamp", "")

        # ── Row 1: device banner ──────────────────────────────────────────────
        r = row()
        title = f"DEVICE: {device_display}" + (f"  ({playwright_name})" if playwright_name else "")
        data.append([title])
        fmt(r, 1, r, total_cols, CellFormat(
            backgroundColor=_c("header_dk"),
            textFormat=TextFormat(bold=True, foregroundColor=_c("white"), fontSize=12),
        ))

        # ── Row 2: run metadata ───────────────────────────────────────────────
        r = row()
        data.append([f"Site: {site}   Run: {ts}"])
        fmt(r, 1, r, total_cols, CellFormat(
            backgroundColor=_c("header_md"),
            textFormat=TextFormat(foregroundColor=_c("white"), fontSize=10),
        ))

        data.append([])  # blank

        # ── Row 4: section label ──────────────────────────────────────────────
        r = row()
        data.append(["TEST MATRIX"])
        fmt(r, 1, r, total_cols, CellFormat(
            textFormat=TextFormat(bold=True, fontSize=11),
        ))

        # ── Row 5: column headers ─────────────────────────────────────────────
        u_labels = [f"U{i} ({page_types.get(u, '?')})" for i, u in enumerate(urls, start=1)]
        r = row()
        data.append(["Test"] + u_labels + ["Overall"])
        fmt(r, 1, r, total_cols, CellFormat(
            backgroundColor=_c("header_dk"),
            textFormat=TextFormat(bold=True, foregroundColor=_c("white"), horizontalAlignment="CENTER"),
            horizontalAlignment="CENTER",
        ))
        MATRIX_HEADER_ROW = r

        # ── Matrix data rows ──────────────────────────────────────────────────
        MATRIX_DATA_START = row()
        test_name_to_row: Dict[str, int] = {}

        for test_name in test_names:
            r = row()
            test_name_to_row[test_name] = r

            row_data: List = [test_name]
            row_states: List[Optional[TestState]] = []

            for u in urls:
                res = result_map.get((test_name, u))
                if res is None:
                    row_states.append(None)
                    row_data.append("-")
                elif res.state == TestState.PASSED:
                    row_states.append(res.state)
                    row_data.append("PASS")
                elif res.state == TestState.FAILED:
                    row_states.append(res.state)
                    row_data.append("FAIL")
                elif res.state == TestState.ERROR:
                    row_states.append(res.state)
                    row_data.append("ERROR")
                elif res.state == TestState.SKIPPED:
                    row_states.append(res.state)
                    row_data.append("SKIP")
                else:
                    row_states.append(res.state)
                    row_data.append(str(res.state.value).upper())

            non_none = [s for s in row_states if s is not None]
            overall = _agg_cell(non_none)
            row_data.append(overall)
            data.append(row_data)

            # Colour individual URL cells
            for ci, state in enumerate(row_states):
                if state is not None:
                    col = 2 + ci
                    fmt(r, col, r, col, CellFormat(
                        backgroundColor=_c(_state_ck(state)),
                        horizontalAlignment="CENTER",
                    ))

            # Colour + bold overall cell
            ov_col = 1 + n_url_cols + 1
            fmt(r, ov_col, r, ov_col, CellFormat(
                backgroundColor=_c(_agg_ck(overall)),
                textFormat=TextFormat(bold=True),
                horizontalAlignment="CENTER",
            ))

        matrix_end_row = row() - 1

        # ── Failure details section ───────────────────────────────────────────
        failing = [r_ for r_ in results if r_.state in (TestState.FAILED, TestState.ERROR)]
        url_label = {u: f"U{i}" for i, u in enumerate(urls, start=1)}

        data.append([])
        data.append([])

        r = row()
        data.append(["FAILURE DETAILS"])
        fmt(r, 1, r, 4, CellFormat(textFormat=TextFormat(bold=True, fontSize=11)))

        r = row()
        data.append(["Test", "URL#", "State", "Detail"])
        fmt(r, 1, r, 4, CellFormat(
            backgroundColor=_c("header_dk"),
            textFormat=TextFormat(bold=True, foregroundColor=_c("white")),
        ))

        by_url: Dict[str, List[TestResult]] = defaultdict(list)
        for r_ in failing:
            by_url[r_.url].append(r_)

        if failing:
            for u in urls:
                group = sorted(by_url.get(u, []), key=lambda x: x.test_name or "")
                for r_ in group:
                    msgs = r_.errors if r_.errors else (r_.warnings or [])
                    state_str = "ERROR" if r_.state == TestState.ERROR else "FAIL"
                    state_ck = "error" if state_str == "ERROR" else "fail"
                    if not msgs:
                        cur = row()
                        data.append([r_.test_name, url_label.get(u, u), state_str, ""])
                        fmt(cur, 3, cur, 3, CellFormat(backgroundColor=_c(state_ck)))
                    else:
                        first = True
                        for msg in msgs:
                            for line in (str(msg).splitlines() or [""]):
                                cur = row()
                                if first:
                                    data.append([r_.test_name, url_label.get(u, u), state_str, line])
                                    fmt(cur, 3, cur, 3, CellFormat(backgroundColor=_c(state_ck)))
                                    first = False
                                else:
                                    data.append(["", "", "", line])
        else:
            data.append(["No failures — all tests passed."])

        # ── URL key section ───────────────────────────────────────────────────
        data.append([])
        data.append([])

        r = row()
        data.append(["URL KEY"])
        fmt(r, 1, r, 3, CellFormat(textFormat=TextFormat(bold=True, fontSize=11)))

        r = row()
        data.append(["U#", "Page Type", "URL"])
        fmt(r, 1, r, 3, CellFormat(
            backgroundColor=_c("header_dk"),
            textFormat=TextFormat(bold=True, foregroundColor=_c("white")),
        ))

        for i, u in enumerate(urls, start=1):
            data.append([f"U{i}", page_types.get(u, "unknown"), u])

        # ── Batch write ───────────────────────────────────────────────────────
        ws.update("A1", data, value_input_option="USER_ENTERED")
        if fmts:
            format_cell_ranges(ws, fmts)
        set_frozen(ws, rows=MATRIX_HEADER_ROW, cols=1)

        return test_name_to_row

    # ── Summary tab ───────────────────────────────────────────────────────────

    def _write_summary_tab(
        self,
        ws,
        all_results: List[TestResult],
        device_keys: List[str],
        device_tab_info: Dict[str, Tuple[int, Dict[str, int]]],
        run_meta: dict,
    ) -> None:
        from gspread_formatting import (
            CellFormat, Color, TextFormat,
            format_cell_ranges, set_frozen,
        )

        def _c(key: str) -> Color:
            return Color(*_PALETTE[key])

        data: List[List] = []
        fmts: List[Tuple] = []

        def row() -> int:
            return len(data) + 1

        def fmt(r1, c1, r2, c2, f: CellFormat) -> None:
            fmts.append((_rng(r1, c1, r2, c2), f))

        n_dev = len(device_keys)
        total_cols = 1 + n_dev

        site = run_meta.get("site", "")
        ts = run_meta.get("timestamp", "")
        env = run_meta.get("env", "")

        # ── Row 1: title banner ───────────────────────────────────────────────
        r = row()
        data.append(["AD TEST RUN REPORT"])
        fmt(r, 1, r, total_cols, CellFormat(
            backgroundColor=_c("header_dk"),
            textFormat=TextFormat(bold=True, foregroundColor=_c("white"), fontSize=14),
        ))

        # ── Row 2: run metadata ───────────────────────────────────────────────
        r = row()
        parts = [x for x in [
            f"Site: {site}" if site else "",
            f"Env: {env}" if env else "",
            f"Run: {ts}" if ts else "",
        ] if x]
        data.append(["   ".join(parts)])
        fmt(r, 1, r, total_cols, CellFormat(
            backgroundColor=_c("header_md"),
            textFormat=TextFormat(foregroundColor=_c("white"), fontSize=10),
        ))

        data.append([])  # blank

        # ── Device pass-rate summary ──────────────────────────────────────────
        r = row()
        data.append(["DEVICE PASS RATES"])
        fmt(r, 1, r, 6, CellFormat(textFormat=TextFormat(bold=True, fontSize=11)))

        r = row()
        data.append(["Device", "Playwright Profile", "Tests", "PASS", "FAIL", "SKIP"])
        fmt(r, 1, r, 6, CellFormat(
            backgroundColor=_c("header_dk"),
            textFormat=TextFormat(bold=True, foregroundColor=_c("white")),
        ))

        device_names = run_meta.get("device_names", {})
        for dk in device_keys:
            dev_res = [x for x in all_results if getattr(x, "device", "") == dk]
            t_names = sorted({x.test_name for x in dev_res if x.test_name})
            n_pass = sum(1 for t in t_names if all(
                x.state == TestState.PASSED for x in dev_res if x.test_name == t
            ))
            n_fail = sum(1 for t in t_names if any(
                x.state in (TestState.FAILED, TestState.ERROR)
                for x in dev_res if x.test_name == t
            ))
            n_skip = sum(1 for t in t_names if all(
                x.state == TestState.SKIPPED for x in dev_res if x.test_name == t
            ))
            r = row()
            data.append([dk, device_names.get(dk, ""), len(t_names), n_pass, n_fail, n_skip])
            if n_fail:
                fmt(r, 5, r, 5, CellFormat(backgroundColor=_c("fail")))
            if n_pass:
                fmt(r, 4, r, 4, CellFormat(backgroundColor=_c("pass")))

        data.append([])
        data.append([])

        # ── Cross-device comparison matrix ────────────────────────────────────
        r = row()
        data.append(["CROSS-DEVICE SUMMARY"])
        fmt(r, 1, r, total_cols, CellFormat(textFormat=TextFormat(bold=True, fontSize=11)))

        r = row()
        data.append(["Test"] + device_keys)
        fmt(r, 1, r, total_cols, CellFormat(
            backgroundColor=_c("header_dk"),
            textFormat=TextFormat(bold=True, foregroundColor=_c("white"), horizontalAlignment="CENTER"),
            horizontalAlignment="CENTER",
        ))
        MATRIX_HEADER_ROW = r

        # Aggregate (test, device) → states
        buckets: Dict[Tuple[str, str], List[TestState]] = defaultdict(list)
        for x in all_results:
            buckets[(x.test_name, getattr(x, "device", ""))].append(x.state)

        all_test_names = sorted({x.test_name for x in all_results if x.test_name})

        for test_name in all_test_names:
            r = row()
            row_data: List = [test_name]

            for ci, dk in enumerate(device_keys):
                states = buckets.get((test_name, dk), [])
                cell_text = _agg_cell(states)
                ck = _agg_ck(cell_text)
                col = 2 + ci

                # Hyperlink for non-passing cells → jump to the test row in the device tab
                gid, test_row_map = device_tab_info.get(dk, (0, {}))
                target_row = test_row_map.get(test_name)
                if target_row and cell_text not in ("PASS", "SKIP", "-") and gid:
                    formula = f'=HYPERLINK("#gid={gid}&range=A{target_row}","{cell_text}")'
                    row_data.append(formula)
                else:
                    row_data.append(cell_text)

                fmt(r, col, r, col, CellFormat(
                    backgroundColor=_c(ck),
                    horizontalAlignment="CENTER",
                ))

            data.append(row_data)

        # ── Batch write ───────────────────────────────────────────────────────
        ws.update("A1", data, value_input_option="USER_ENTERED")
        if fmts:
            format_cell_ranges(ws, fmts)
        set_frozen(ws, rows=MATRIX_HEADER_ROW, cols=1)
