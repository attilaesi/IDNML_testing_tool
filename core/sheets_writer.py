# core/sheets_writer.py
"""
Write ad test results to a new timestamped Google Spreadsheet.

Sheet structure
───────────────
  Tab "regression"       — New vs known failures vs fixed (--real_run only).
  Tab "test_run_summary" — Run header, per-device pass-rate counts, cross-device
                           comparison matrix.  FAIL/MIXED cells are hyperlinks that
                           jump directly to the relevant row in the device tab.
  Tab "desktop"          — Test × URL matrix, failure details, URL key.
  Tab "mobile_ios"       — Same layout.
  Tab "mobile_android"   — Same layout.
  Tab "tablet"           — Same layout.
  Tab "appendix"         — Description + conditions for every test (from module docstrings).
                           Test names in every other tab link here.

Authentication
──────────────
  OAuth mode (recommended): set sheets_oauth_credentials in base_config to a
  Desktop App OAuth client secret JSON.  First run opens a browser; after that
  fully headless via cached refresh token.

  Service account fallback: set GOOGLE_SERVICE_ACCOUNT_JSON env var.
"""

import asyncio
import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from core.base_test import TestResult, TestState


# ── Colour palette (RGB 0-1 floats) ──────────────────────────────────────────
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


# ── Docstring helpers (for Appendix tab) ─────────────────────────────────────

def _split_docstring(doc: str) -> Dict[str, str]:
    """Parse a structured test module docstring into labelled sections."""
    import re as _re
    if not doc:
        return {"label": "", "description": "", "conditions": "", "outcomes": ""}
    lines = doc.splitlines()
    label = lines[0].strip()
    sections: Dict[str, str] = {
        "label": label, "description": "", "conditions": "", "outcomes": "",
    }
    SECTION_KEYS = {
        "what this test is meant to test": "description",
        "what this test checks": "description",
        "test conditions": "conditions",
        "what counts as pass": "outcomes",
    }
    current_key: Optional[str] = None
    buf: List[str] = []
    i = 1
    while i < len(lines):
        line = lines[i]
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if _re.match(r"^-{3,}$", next_line):
            if current_key and buf:
                sections[current_key] = "\n".join(buf).strip()
                buf = []
            for pattern, key in SECTION_KEYS.items():
                if pattern in line.strip().lower():
                    current_key = key
                    i += 2
                    break
            else:
                i += 1
            continue
        if current_key is not None:
            buf.append(line)
        i += 1
    if current_key and buf:
        sections[current_key] = "\n".join(buf).strip()
    return sections


def _collect_test_docs() -> Dict[str, Dict[str, str]]:
    """Return {snake_test_name: parsed_docstring_sections} for every test file."""
    import ast as _ast
    from pathlib import Path
    from core.base_test import _to_snake
    tests_root = Path(__file__).resolve().parent.parent / "tests"
    out: Dict[str, Dict[str, str]] = {}
    for py_file in sorted(tests_root.rglob("*.py")):
        if py_file.name.startswith("_"):
            continue
        if "test" not in py_file.name.lower():
            continue
        try:
            src = py_file.read_text(encoding="utf-8")
            tree = _ast.parse(src)
            module_doc = _ast.get_docstring(tree)
            for node in _ast.walk(tree):
                if isinstance(node, _ast.ClassDef):
                    snake = _to_snake(node.name)
                    if snake:
                        out[snake] = _split_docstring(module_doc)
                    break
        except Exception:
            pass
    return out


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
        """Return (gspread_client, credentials) tuple.

        OAuth mode (preferred): set SHEETS_OAUTH_CREDENTIALS to the path of the
        OAuth client secret JSON (Desktop App type). Opens a browser on first run,
        then caches a refresh token at ~/.config/gspread/ads-testing-token.json.
        Files are created as the authenticated user — no service account quota issues.

        Service account mode (fallback): set GOOGLE_SERVICE_ACCOUNT_JSON.
        """
        import gspread

        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        oauth_client_file = (
            self.config.get("sheets_oauth_credentials")
            or os.getenv("SHEETS_OAUTH_CREDENTIALS")
        )

        if oauth_client_file:
            oauth_client_file = os.path.expanduser(oauth_client_file)
        if oauth_client_file and os.path.isfile(oauth_client_file):
            # ── OAuth user credentials ────────────────────────────────────────
            from google.oauth2.credentials import Credentials as UserCredentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            import google.auth.transport.requests

            token_file = os.path.expanduser("~/.config/gspread/ads-testing-token.json")
            os.makedirs(os.path.dirname(token_file), exist_ok=True)

            creds = None
            if os.path.isfile(token_file):
                creds = UserCredentials.from_authorized_user_file(token_file, SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(google.auth.transport.requests.Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(oauth_client_file, SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(token_file, "w") as f:
                    f.write(creds.to_json())

            return gspread.Client(auth=creds), creds

        # ── Service account fallback ──────────────────────────────────────────
        from google.oauth2.service_account import Credentials as SACredentials

        sa_json = (
            self.config.get("sheets_service_account_json")
            or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        )
        if not sa_json:
            raise EnvironmentError(
                "Set SHEETS_OAUTH_CREDENTIALS (recommended) or "
                "GOOGLE_SERVICE_ACCOUNT_JSON — see README → Google Sheets Setup."
            )
        if os.path.isfile(sa_json):
            creds = SACredentials.from_service_account_file(sa_json, scopes=SCOPES)
        else:
            creds = SACredentials.from_service_account_info(json.loads(sa_json), scopes=SCOPES)
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
                if not resp.ok:
                    print(f"⚠️  Drive API error {resp.status_code}: {resp.text}")
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

        # ── Collect test docs and pre-compute Appendix row map ────────────────
        test_docs = _collect_test_docs()
        all_test_names_sorted = sorted({r.test_name for r in all_results if r.test_name})
        # Row 1 = banner, Row 2 = headers, Row 3+ = data
        appendix_row_map: Dict[str, int] = {
            name: idx + 3 for idx, name in enumerate(all_test_names_sorted)
        }

        # Create Appendix worksheet early so we have its GID for hyperlinks
        try:
            appendix_ws = spreadsheet.add_worksheet(
                title="appendix", rows=len(all_test_names_sorted) + 10, cols=4
            )
            appendix_gid: int = appendix_ws.id
        except Exception as e:
            print(f"   ⚠️  Could not pre-create Appendix tab: {e}")
            appendix_ws = None
            appendix_gid = 0

        # Write per-device tabs first — need their GIDs for summary hyperlinks
        device_tab_info: Dict[str, Tuple[int, Dict[str, int]]] = {}

        for i, dk in enumerate(device_keys):
            dev_results = [r for r in all_results if getattr(r, "device", "") == dk]
            if i == 0:
                ws = spreadsheet.sheet1
                ws.update_title(dk)
            else:
                ws = spreadsheet.add_worksheet(title=dk, rows=400, cols=40)
            try:
                test_row_map = self._write_device_tab(
                    ws, dev_results, dk, run_meta,
                    appendix_gid=appendix_gid,
                    appendix_row_map=appendix_row_map,
                )
                device_tab_info[dk] = (ws.id, test_row_map)
                print(f"   ✅ {dk}")
            except Exception as e:
                print(f"   ⚠️  Error writing tab '{dk}': {e}")
                device_tab_info[dk] = (getattr(ws, "id", 0), {})

        # Write test_run_summary tab
        try:
            summary_ws = spreadsheet.add_worksheet(title="test_run_summary", rows=300, cols=20)
            self._write_summary_tab(
                summary_ws, all_results, device_keys, device_tab_info, run_meta,
                appendix_gid=appendix_gid,
                appendix_row_map=appendix_row_map,
            )
            print("   ✅ test_run_summary")
        except Exception as e:
            print(f"   ⚠️  Error writing test_run_summary tab: {e}")

        # Write Regression tab (--real_run only)
        regression = run_meta.get("regression")
        regression_ws = None
        if regression is not None:
            try:
                regression_ws = spreadsheet.add_worksheet(title="regression", rows=200, cols=6)
                self._write_regression_tab(
                    regression_ws, regression,
                    appendix_gid=appendix_gid,
                    appendix_row_map=appendix_row_map,
                )
                print("   ✅ Regression")
            except Exception as e:
                print(f"   ⚠️  Error writing Regression tab: {e}")

        # Write Appendix data
        if appendix_ws is not None:
            try:
                self._write_appendix_tab(appendix_ws, all_test_names_sorted, test_docs)
                print("   ✅ Appendix")
            except Exception as e:
                print(f"   ⚠️  Error writing Appendix tab: {e}")

        # Reorder: test_run_summary first, then devices, Regression, Appendix last
        try:
            ws_by_title = {w.title: w for w in spreadsheet.worksheets()}
            ordered = (
                ([ws_by_title["regression"]] if "regression" in ws_by_title else [])
                + ([ws_by_title["test_run_summary"]] if "test_run_summary" in ws_by_title else [])
                + [ws_by_title[dk] for dk in device_keys if dk in ws_by_title]
                + ([ws_by_title["appendix"]] if "appendix" in ws_by_title else [])
            )
            if ordered:
                spreadsheet.reorder_worksheets(ordered)
        except Exception:
            pass

        print(f"\n📊 Report: {url}")
        return url

    # ── Column width helper ───────────────────────────────────────────────────

    def _set_column_widths(self, ws, col_widths: Dict[int, int]) -> None:
        """Set pixel widths for columns. col_widths keys are 0-based column indices."""
        requests = [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": ws.id,
                        "dimension": "COLUMNS",
                        "startIndex": col_idx,
                        "endIndex": col_idx + 1,
                    },
                    "properties": {"pixelSize": px},
                    "fields": "pixelSize",
                }
            }
            for col_idx, px in col_widths.items()
        ]
        if requests:
            ws.spreadsheet.batch_update({"requests": requests})

    # ── Per-device tab ────────────────────────────────────────────────────────

    def _write_device_tab(
        self,
        ws,
        results: List[TestResult],
        device_key: str,
        run_meta: dict,
        appendix_gid: int = 0,
        appendix_row_map: Optional[Dict[str, int]] = None,
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

        def _test_name_cell(test_name: str) -> str:
            if appendix_gid and appendix_row_map and test_name in appendix_row_map:
                arow = appendix_row_map[test_name]
                return f'=HYPERLINK("#gid={appendix_gid}&range=A{arow}","{test_name}")'
            return test_name

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
            textFormat=TextFormat(bold=True, foregroundColor=_c("white")),
            horizontalAlignment="CENTER",
        ))
        MATRIX_HEADER_ROW = r

        # ── Matrix data rows ──────────────────────────────────────────────────
        MATRIX_DATA_START = row()
        test_name_to_row: Dict[str, int] = {}

        for test_name in test_names:
            r = row()
            test_name_to_row[test_name] = r

            row_data: List = [_test_name_cell(test_name)]
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

        fmt(1, 1, row() - 1, total_cols, CellFormat(verticalAlignment="TOP"))

        col_widths = {0: 220}
        for i in range(n_url_cols):
            col_widths[1 + i] = 100
        col_widths[1 + n_url_cols] = 130
        self._set_column_widths(ws, col_widths)

        return test_name_to_row

    # ── Summary tab ───────────────────────────────────────────────────────────

    def _write_summary_tab(
        self,
        ws,
        all_results: List[TestResult],
        device_keys: List[str],
        device_tab_info: Dict[str, Tuple[int, Dict[str, int]]],
        run_meta: dict,
        appendix_gid: int = 0,
        appendix_row_map: Optional[Dict[str, int]] = None,
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

        def _test_name_cell(test_name: str) -> str:
            if appendix_gid and appendix_row_map and test_name in appendix_row_map:
                arow = appendix_row_map[test_name]
                return f'=HYPERLINK("#gid={appendix_gid}&range=A{arow}","{test_name}")'
            return test_name

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
            textFormat=TextFormat(bold=True, foregroundColor=_c("white")),
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
            row_data: List = [_test_name_cell(test_name)]

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

        fmt(1, 1, row() - 1, total_cols, CellFormat(verticalAlignment="TOP"))

        # Col 0: test name, col 1: playwright profile, cols 2-5: counts, rest: device cols
        col_widths = {0: 220, 1: 170, 2: 70, 3: 70, 4: 70, 5: 70}
        for i in range(n_dev):
            col_widths.setdefault(1 + i, 130)
        self._set_column_widths(ws, col_widths)

    # ── Regression tab ────────────────────────────────────────────────────────

    def _write_regression_tab(
        self,
        ws,
        regression: dict,
        appendix_gid: int = 0,
        appendix_row_map: Optional[Dict[str, int]] = None,
    ) -> None:
        from gspread_formatting import (
            CellFormat, Color, TextFormat,
            format_cell_ranges, set_frozen,
        )

        def _c(key: str) -> Color:
            return Color(*_PALETTE[key])

        def _test_name_cell(test_name: str) -> str:
            if appendix_gid and appendix_row_map and test_name in appendix_row_map:
                arow = appendix_row_map[test_name]
                return f'=HYPERLINK("#gid={appendix_gid}&range=A{arow}","{test_name}")'
            return test_name

        data: List[List] = []
        fmts: List[Tuple] = []

        def row() -> int:
            return len(data) + 1

        def fmt(r1, c1, r2, c2, f: CellFormat) -> None:
            fmts.append((_rng(r1, c1, r2, c2), f))

        REG_COLS = 4   # Test | Device | Geo | Error detail

        # Banner
        r = row()
        data.append(["REGRESSION STATUS"])
        fmt(r, 1, r, REG_COLS, CellFormat(
            backgroundColor=_c("header_dk"),
            textFormat=TextFormat(bold=True, foregroundColor=_c("white"), fontSize=12),
        ))

        if regression.get("no_previous_run"):
            r = row()
            data.append(["First real run — no previous run to compare against."])
            fmt(r, 1, r, REG_COLS, CellFormat(
                backgroundColor=_c("header_md"),
                textFormat=TextFormat(foregroundColor=_c("white")),
            ))
            ws.update("A1", data, value_input_option="USER_ENTERED")
            if fmts:
                format_cell_ranges(ws, fmts)
            return

        prev_ts = regression.get("previous_run_timestamp", "")
        geo = regression.get("geo", "")
        try:
            from datetime import datetime as _dt
            prev_ts = _dt.fromisoformat(prev_ts.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

        r = row()
        data.append([f"Compared against: {prev_ts}   geo: {geo}"])
        fmt(r, 1, r, REG_COLS, CellFormat(
            backgroundColor=_c("header_md"),
            textFormat=TextFormat(foregroundColor=_c("white"), fontSize=10),
        ))

        def _subsection(label: str, rows: List[dict], color_key: str, include_error: bool) -> None:
            data.append([])
            r = row()
            data.append([f"{label}  ({len(rows)})"])
            fmt(r, 1, r, REG_COLS, CellFormat(
                backgroundColor=_c(color_key),
                textFormat=TextFormat(bold=True),
            ))

            if not rows:
                data.append(["—"])
                return

            r = row()
            hdrs = ["Test", "Device", "Detail"] if include_error else ["Test", "Device"]
            data.append(hdrs)
            fmt(r, 1, r, len(hdrs), CellFormat(
                textFormat=TextFormat(bold=True),
                backgroundColor=_c("dash"),
            ))

            for entry in rows:
                if include_error:
                    data.append([
                        _test_name_cell(entry.get("test_name", "")),
                        entry.get("device", ""),
                        entry.get("error_summary") or "",
                    ])
                else:
                    data.append([
                        _test_name_cell(entry.get("test_name", "")),
                        entry.get("device", ""),
                    ])

        new_f = regression.get("new_failures", [])
        known = regression.get("known_failures", [])
        fixed = regression.get("fixed", [])

        _subsection("NEW FAILURES",   new_f, "fail",  include_error=True)
        _subsection("KNOWN FAILURES", known, "mixed", include_error=True)
        _subsection("FIXED",          fixed, "pass",  include_error=False)

        total_rows = row() - 1
        fmt(1, 1, total_rows, REG_COLS, CellFormat(wrapStrategy="WRAP", verticalAlignment="TOP"))

        ws.update("A1", data, value_input_option="USER_ENTERED")
        if fmts:
            format_cell_ranges(ws, fmts)
        set_frozen(ws, rows=1, cols=0)

        self._set_column_widths(ws, {0: 220, 1: 130, 2: 350})

    # ── Appendix tab ──────────────────────────────────────────────────────────

    def _write_appendix_tab(
        self,
        ws,
        all_test_names: List[str],
        test_docs: Dict[str, Dict[str, str]],
    ) -> None:
        """Write one row per test with description, conditions, and pass/fail outcomes."""
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

        # ── Row 1: banner ─────────────────────────────────────────────────────
        r = row()
        data.append(["TEST APPENDIX"])
        fmt(r, 1, r, 4, CellFormat(
            backgroundColor=_c("header_dk"),
            textFormat=TextFormat(bold=True, foregroundColor=_c("white"), fontSize=14),
        ))

        # ── Row 2: column headers ─────────────────────────────────────────────
        r = row()
        data.append(["Test Name", "What it tests", "Conditions", "Pass / Fail / Skip"])
        fmt(r, 1, r, 4, CellFormat(
            backgroundColor=_c("header_md"),
            textFormat=TextFormat(bold=True, foregroundColor=_c("white")),
        ))
        HEADER_ROW = r

        # ── One row per test ──────────────────────────────────────────────────
        for test_name in all_test_names:
            r = row()
            doc = test_docs.get(test_name, {})
            desc = doc.get("description", "")
            cond = doc.get("conditions", "")
            outcomes = doc.get("outcomes", "")
            data.append([test_name, desc, cond, outcomes])
            fmt(r, 1, r, 1, CellFormat(textFormat=TextFormat(bold=True)))
            if not desc and not cond and not outcomes:
                fmt(r, 2, r, 4, CellFormat(backgroundColor=_c("skip")))

        # Wrap all text, top-align
        total_rows = row() - 1
        fmt(1, 1, total_rows, 4, CellFormat(wrapStrategy="WRAP", verticalAlignment="TOP"))

        ws.update("A1", data, value_input_option="USER_ENTERED")
        if fmts:
            format_cell_ranges(ws, fmts)
        set_frozen(ws, rows=HEADER_ROW, cols=1)

        self._set_column_widths(ws, {0: 220, 1: 300, 2: 300, 3: 350})
