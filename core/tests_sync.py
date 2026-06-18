"""
core/tests_sync.py

Parses every test file's module-level docstring and upserts to the
Supabase `tests` reference table.

Run via:  python run.py --sync-tests
Or directly: python -m core.tests_sync
"""

import ast
import asyncio
import re
import sys
from pathlib import Path
from typing import Optional

import aiohttp

from core.supabase_helpers import get_supabase_credentials

TABLE = "tests"

CATEGORY_MAP = {
    "gpt_tests":         "GPT",
    "prebid_tests":      "Prebid",
    "ima_tests":         "IMA",
    "layout_tests":      "Layout",
    "environment_tests": "Environment",
}


# ── Docstring parser ─────────────────────────────────────────────────────────

def _sections(doc: str) -> dict:
    """Split docstring into named sections by header / dashes pattern."""
    parts = {}
    current = "__preamble__"
    lines = doc.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if next line is all dashes → this line is a section header
        if i + 1 < len(lines) and re.match(r"^-{3,}\s*$", lines[i + 1]):
            current = line.strip()
            i += 2
        else:
            parts.setdefault(current, []).append(line)
            i += 1
    return {k: "\n".join(v).strip() for k, v in parts.items()}


def _find_section(sections: dict, *candidates) -> Optional[str]:
    for key in sections:
        for c in candidates:
            if c.lower() in key.lower():
                return sections[key]
    return None


def _parse_outcome_block(text: str, marker: str) -> Optional[str]:
    """
    Extract text from a named outcome subsection.
    Handles both inline:  '- PASSED: text'
    and block:            '* PASSED:\\n    - text line'
    """
    if not text:
        return None

    our = marker.lower()
    all_markers = {"passed", "failed", "skipped", "pass", "fail", "skip"}

    collecting = False
    result: list[str] = []

    for line in text.splitlines():
        s = line.strip()
        sl = s.lower()

        is_ours = (
            sl.startswith(f"* {our}:") or
            sl.startswith(f"- {our}:") or
            sl == f"* {our}" or
            sl == f"- {our}"
        )
        is_other = not is_ours and any(
            sl.startswith(f"* {m}") or sl.startswith(f"- {m}:")
            for m in all_markers if m != our
        )

        if is_ours:
            collecting = True
            if ":" in s:
                rest = s.split(":", 1)[1].strip()
                if rest:
                    result.append(rest)
        elif is_other:
            collecting = False
        elif collecting and s:
            result.append(s[2:].strip() if s.startswith("- ") else s)

    clean = [r for r in result if r]
    return " | ".join(clean) if clean else None


def parse_docstring(doc: str) -> dict:
    sections = _sections(doc)
    description = _find_section(sections, "what this test checks", "what this test is meant")
    conditions  = _find_section(sections, "test conditions")
    outcomes    = _find_section(sections, "pass / fail / skip", "pass/fail/skip")
    return {
        "description": description,
        "conditions":  conditions,
        "pass_when":   _parse_outcome_block(outcomes, "PASSED"),
        "fail_when":   _parse_outcome_block(outcomes, "FAILED"),
        "skip_when":   _parse_outcome_block(outcomes, "SKIPPED"),
    }


# ── Test file discovery ───────────────────────────────────────────────────────

def collect_test_metadata() -> list:
    tests_dir = Path(__file__).parent.parent / "tests"
    rows = []

    for f in sorted(tests_dir.rglob("*_test.py")):
        # derive category from folder name
        category = "Unknown"
        for folder, cat in CATEGORY_MAP.items():
            if folder in f.parts:
                category = cat
                break

        src = f.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue

        doc = ast.get_docstring(tree) or ""
        parsed = parse_docstring(doc)

        # derive test_name from class name (same logic as BaseTest.name)
        test_name = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                snake = re.sub(r'(?<!^)(?=[A-Z])', '_', node.name).lower()
                if snake.endswith('_test'):
                    snake = snake[:-5]
                test_name = snake
                break
        if not test_name:
            test_name = f.stem[:-5] if f.stem.endswith('_test') else f.stem

        rows.append({
            "test_name":   test_name,
            "category":    category,
            **parsed,
        })

    return rows


# ── Supabase upsert ───────────────────────────────────────────────────────────

async def sync_to_supabase(config: dict) -> None:
    url, key = get_supabase_credentials(config)
    if not url or not key:
        print("⚠️  Supabase not configured — cannot sync tests table.")
        return

    api_url = url.rstrip("/") + f"/rest/v1/{TABLE}"
    headers = {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }

    rows = collect_test_metadata()
    print(f"   Syncing {len(rows)} tests to Supabase `{TABLE}` table…")

    async with aiohttp.ClientSession() as session:
        async with session.post(api_url, json=rows, headers=headers) as resp:
            if resp.ok:
                print(f"   ✅ Synced {len(rows)} tests.")
            else:
                text = await resp.text()
                print(f"   ⚠️  Sync failed {resp.status}: {text[:300]}")


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Allow: python -m core.tests_sync
    # Reads credentials from env vars SUPABASE_URL / SUPABASE_KEY
    import os
    config = {
        "supabase_url": os.environ.get("SUPABASE_URL", ""),
        "supabase_key": os.environ.get("SUPABASE_KEY", ""),
    }
    asyncio.run(sync_to_supabase(config))
