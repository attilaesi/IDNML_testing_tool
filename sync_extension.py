#!/usr/bin/env python3
"""
sync_extension.py
-----------------
Copies test JS files from tests/js/ into extension/js/ wrapped for the
Chrome Extension context.

Wrapping format:
  window.__adTests = window.__adTests || {};
  window.__adTests["<stem>"] = <file_content>;

Parameterised tests that use __PLACEHOLDER__ tokens have their placeholders
replaced with hardcoded values before wrapping.

The tests/js/shared/ directory is copied into extension/js/shared/ unchanged.

Usage:
  python sync_extension.py
"""

import json
import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).parent
JS_SRC = REPO_ROOT / "tests" / "js"
EXT_JS = REPO_ROOT / "extension" / "js"

# Parameterised replacements: stem -> {placeholder: value}
REPLACEMENTS = {
    "pbjs_video_hero_player_placement": {
        "__EXPECTED_PLACEMENT__": "1",
        "__HERO_ADUNIT_CODE__": "hero_player",
    },
    "pbjs_display_permutive_signals_bid": {
        "__REQUIRED_BIDDERS__": json.dumps(["ix", "rubicon", "msft", "pubmatic"]),
    },
}

# Files in tests/js/ to skip (shared/ handled separately; others not needed)
SKIP_FILES = {"taboola_load_time.js"}


def sync():
    # Ensure destination exists
    EXT_JS.mkdir(parents=True, exist_ok=True)

    # Sync shared/ unchanged
    shared_src = JS_SRC / "shared"
    shared_dst = EXT_JS / "shared"
    if shared_src.exists():
        if shared_dst.exists():
            shutil.rmtree(shared_dst)
        shutil.copytree(shared_src, shared_dst)
        print(f"  [shared] Copied {shared_src} -> {shared_dst}")

    # Wrap each .js test file
    wrapped = 0
    skipped = 0

    for js_file in sorted(JS_SRC.glob("*.js")):
        filename = js_file.name
        stem = js_file.stem

        if filename in SKIP_FILES:
            skipped += 1
            continue

        content = js_file.read_text(encoding="utf-8")

        # Apply placeholder replacements if this test is parameterised
        if stem in REPLACEMENTS:
            for placeholder, value in REPLACEMENTS[stem].items():
                content = content.replace(placeholder, value)

        wrapped_content = (
            'window.__adTests = window.__adTests || {};\n'
            f'window.__adTests["{stem}"] = {content};\n'
        )

        dst = EXT_JS / filename
        dst.write_text(wrapped_content, encoding="utf-8")
        print(f"  [wrap]   {filename}")
        wrapped += 1

    print(f"\nDone. Wrapped {wrapped} test files, skipped {skipped}.")


if __name__ == "__main__":
    sync()
