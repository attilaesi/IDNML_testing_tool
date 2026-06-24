# Ad Testing Framework

A modular, async Playwright-based framework for validating ad implementations across Independent and Standard Media Group sites. Tests cover Prebid.js configuration, GPT key-value targeting, IMA video ad targeting, layout/ad-sequence rules, and environment integrity.

Also includes a **Chrome extension** (Ad Inspector) that runs the same tests live in any browser tab.

---

## Installation

### Prerequisites

- Python 3.10 or later
- pip
- Google Chrome (for the extension)

### 1. Clone the repo

```bash
git clone <repo-url>
cd IDNML_testing_tool
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browsers

```bash
playwright install chromium
```

### 5. Create env.local

Create a file named `env.local` in the repo root. All variables are optional depending on which features you use:

```bash
# Supabase — required for --regression flag
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_ANON_KEY="your-anon-key"

# BrowserStack — required for --browserstack flag
BROWSERSTACK_USERNAME="your_username"
BROWSERSTACK_ACCESS_KEY="your_access_key"
```

The file is loaded automatically at startup. You do **not** need to source it manually.

### 6. Verify the setup

```bash
python -m tasks.run_tests --site independent_uat --test gpt_page_type_test
```

You should see a test matrix printed to the terminal.

---

## Chrome Extension (Ad Inspector)

The extension runs all tests live in any browser tab as you browse, without needing Playwright or Python.

### Install

1. Open Chrome and go to `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked** and select the `extension/` folder from this repo
4. The Ad Inspector icon will appear in your toolbar

### Usage

- Navigate to any Independent or Standard Media page
- The extension auto-runs tests on page load and shows a badge with the fail count
- Click the icon to see full pass/fail results per test, with expandable data panels
- Use **Re-run** to re-run tests on the current page (useful after video player loads)
- Use **Copy JSON** to copy the full result payload to the clipboard

### Keeping extension JS in sync

Test logic lives in `tests/js/`. After editing any JS test file, run:

```bash
python sync_extension.py
```

This wraps the bare functions for the extension context and copies them to `extension/js/`.

---

## Quick Start

```bash
pip install -r requirements.txt
playwright install chromium

# Source environment variables (credentials, etc.)
set -a && source env.local && set +a

# Run all tests against the active site profile
python -m tasks.run_tests

# Run a single test
python -m tasks.run_tests --test pbjs_display_bidder_presence_test

# Override the site profile
python -m tasks.run_tests --site independent_uat

# Upload results to Supabase + include regression diff in the sheet
python -m tasks.run_tests --regression

# Run via BrowserStack Automate (requires Automate plan + credentials in env.local)
python -m tasks.run_tests --browserstack

# Run from a specific geo (sets BrowserStack geoLocation + tags Supabase rows)
python -m tasks.run_tests --browserstack --geo uk
python -m tasks.run_tests --browserstack --geo us
```

---

## Project Structure

```
config/
  base_config.py        — Master config: site, device, timeouts, feature flags, BrowserStack
  device_config.py      — Playwright device profile selector (ACTIVE_DEVICE + DEVICE_SUITE)
  site_urls.py          — URL sets per site profile
  site_test_plans.py    — Per-publisher test exclusion rules

core/
  framework_manager.py  — Main orchestrator: crawl, run tests, output matrix
  browser_manager.py    — Browser launch / BrowserStack connect, context, Prebid hooks
  base_test.py          — BaseTest / TestResult / TestState base classes
  device_helpers.py     — Viewport-based device type detection (mobile vs desktop)
  cmp_handler.py        — Consent banner dismissal
  readiness_waiter.py   — Wait for Prebid + GPT to be ready on page
  data_extractor.py     — Shared JS extraction helpers used across tests
  supabase_helpers.py   — Supabase credential resolution for bidder config queries
  supabase_writer.py    — Writes run results to Supabase for regression tracking
  sheets_writer.py      — Creates timestamped Google Spreadsheet after each run
  url_context_helpers.py— Publisher/env/page-type detection from URL
  framework/
    discovery.py        — Auto-discovers test classes from the tests/ directory

tasks/
  run_tests.py          — CLI entry point: discover and run all ad tests (single device)
  run_multi_device.py   — Run all tests across the four-device suite
  run_crawler.py        — Sitemap-based URL crawler entry point
  common.py             — Shared output/summary helpers (banner, print_results)

tests/
  environment_tests/    — Site environment integrity checks
  gpt_tests/            — Google Publisher Tag key-value targeting tests
  prebid_tests/         — Prebid.js auction, bidder, and signal tests
  layout_tests/         — Ad slot layout, sequence, and Taboola load tests
```

---

## Configuration

### Switching sites

Edit `config/base_config.py` and set `self.active_site`:

| Value | Environment |
|---|---|
| `"independent"` | Production |
| `"independent_uat"` | UAT / pre-prod |
| `"independent_staging"` | Staging |
| `"standard"` | Standard Media production |
| `"standard_uat"` | Standard Media UAT |
| `"standard_dev_master"` | Standard Media dev master |

### Switching device

Edit `config/device_config.py` and set `ACTIVE_DEVICE` to any Playwright device name from the commented list (Desktop Chrome, iPhone 15 Pro, iPad Pro 11, Pixel 7, etc.).

### Feature branch testing

```python
# base_config.py
self.indy_feat_branch = "https://indy-2739-chore-my-branch.independent.co.uk"
```

This swaps the UAT domain for the feature branch URL across all configured test pages.

### Light ad rules

```python
self.light_ad_rules = True   # force feat__use_light_ad_rules=true
self.light_ad_rules = False  # force feat__use_light_ad_rules=false
self.light_ad_rules = None   # leave unset (page default)
```

### Geo

Geo is driven from the CLI at runtime and should not normally be hardcoded in config. Pass `--geo uk` or `--geo us` when running:

```bash
python -m tasks.run_tests --geo uk
python -m tasks.run_multi_device --geo us
```

What geo controls end-to-end:

| System | Effect |
|---|---|
| BrowserStack | Sets `browserstack.geoLocation` so the session IP matches the geo (`uk` → GB, `us` → US) |
| CMP handler | Skipped entirely for US (no consent banner shown in the US) |
| Video tests | All `VideoOnlyTest` subclasses return **N/A** for US geo (different video player; no Prebid video auction in the US) |
| Readiness waiter | Does not wait for hero_player auction on video pages when geo is US |
| `context_summary.geo` | Explicitly set from config rather than inferred from the page Locale cookie |
| Supabase rows | Every result row is tagged with the geo; regression diffs are scoped per geo (UK runs only compare against previous UK runs) |
| Google Sheet | Geo shown in the sheet title and the summary tab run metadata row |

You can set a default in `base_config.py` if needed:

```python
self.geo = "uk"   # "uk" | "us" | None (None = infer from Locale cookie)
```

---

## Tests

### Environment tests
| Test | What it checks |
|---|---|
| `env_is_mobile_or_tablet_test` | `is_mobile_or_tablet` cookie matches viewport on all environments |

### GPT tests (Google Publisher Tag)
| Test | What it checks |
|---|---|
| `gpt_page_type_test` | `pageType` key-value present and valid |
| `gpt_article_id_test` | Article ID key-value present on article pages |
| `gpt_category1_test` / `gpt_category2_test` | Category targeting keys |
| `gpt_mantis_test` / `gpt_mantis_context_test` | Mantis contextual signals |
| `gpt_permutive_composite_test` | Permutive audience composite key |
| `gpt_consent_tcf_test` | TCF consent string present |
| `gpt_cmp_active_test` | CMP active flag |
| `gpt_gdpr_key_test` | GDPR targeting key |
| `gpt_gam_bid_keys_test` | GAM bid price keys set by Prebid |
| `gpt_autorefresh_test` | Auto-refresh slot targeting |
| `gpt_commercial_test` | Commercial targeting key |
| `gpt_reg_gate_test` | Registration gate targeting key |
| `gpt_referrer_test` | Referrer targeting key |
| `gpt_liveblog_test` | Liveblog targeting key on liveblog pages |
| `gpt_longread_test` | Long-read targeting key |
| `gpt_testgroup_test` | Test-group targeting key |
| `gpt_topictags_test` | Topic tag targeting keys |
| `gpt_content_sources_test` | Content source targeting key |
| `gpt_anonymised_key_test` | Anonymised user targeting key |
| `gpt_slot_dump_probe_test` | Probe that dumps all slot targeting for debugging |
| `gpt_untested_keys_test` | Flags any GAM keys not covered by other tests |

### Prebid tests
| Test | What it checks |
|---|---|
| `pbjs_display_bidder_presence_test` | Expected display bidders present and active |
| `pbjs_video_bidder_presence_test` | Expected video bidders present and active |
| `pbjs_video_hero_player_placement_test` | Hero player ad unit configured correctly |
| `pbjs_display_price_floors_test` | Price floors set for display |
| `pbjs_video_price_floors_test` | Price floors set for video |
| `pbjs_display_pubcid_presence_test` | PubCID module active for display |
| `pbjs_video_pubcid_presence_test` | PubCID module active for video |
| `pbjs_display_auction_activity_test` | Display auction fired and received bids |
| `pbjs_adunit_configuration_test` | Ad unit config is valid |
| `pbjs_consent_integration_test` | Prebid consent integration |
| `pbjs_identity_modules_test` | Identity modules loaded |
| `pbjs_display_mantis_signals_bid_test` | Mantis signals passed into display bids |
| `pbjs_display_permutive_signals_bid_test` | Permutive signals passed into display bids |
| `pbjs_timeout_config_test` | Bid timeout configured correctly |
| `pbjs_warnings_test` | No unexpected Prebid warnings |
| `pbjs_environment_test` | Prebid version and environment checks |

### IMA tests (video ad targeting)

These run on video pages only and validate the `cust_params` targeting keys sent in the IMA VAST request to GAM. All tests skip automatically on non-video pages.

| Test | Key | Rule |
|---|---|---|
| `ima_page_type_test` | `pageType` | Must be present and non-empty |
| `ima_category1_test` | `category1` | Must be present and non-empty |
| `ima_category2_test` | `category2` | Must be present and non-empty |
| `ima_mantis_test` | `mantis` | Must be present and non-empty |
| `ima_mantis_context_test` | `mantis_context` | Must be present and non-empty |
| `ima_permutive_test` | `permutive` | Must be present and non-empty |
| `ima_topictags_test` | `topictags` | Must be present and non-empty |
| `ima_liveblog_test` | `liveblog` | Must be present and must be `y` or `n` |
| `ima_longread_test` | `longread` | Must be present and must be `y` or `n` |
| `ima_video_id_test` | `VideoID` | Must be present and non-empty |
| `ima_adpos_test` | `adpos` | Must be present and non-empty |

```bash
python -m tasks.run_tests --tests ima
```

### Layout tests
| Test | What it checks |
|---|---|
| `layout_ad_sequence_test` | Ad slots appear in the expected order in the DOM |
| `taboola_load_time_test` | Taboola widget loads within the acceptable time budget |

---

## Output

- **Terminal** — pass/fail counts, per-URL breakdown, failure details with error messages, and a run banner clearly showing whether you're running locally or via BrowserStack
- **Google Sheets** — timestamped spreadsheet created after every run (see below)
- **Supabase** — results uploaded for week-over-week regression tracking when `--regression` is passed

---

## Multi-Device Testing

Run all tests across a canonical four-device suite in one command:

```bash
python -m tasks.run_multi_device
```

### Device suite

| Key | Playwright profile | Viewport | Represents |
|---|---|---|---|
| `desktop` | Desktop Chrome | 1280×720 | Standard desktop / newsroom benchmark |
| `mobile_ios` | iPhone 15 Pro | 393×659 | Modern iOS (~27% UK mobile share) |
| `mobile_android` | Pixel 7 | 412×839 | Modern Android flagship |
| `tablet` | iPad Pro 11 | 834×1194 | Dominant tablet form factor |

Devices are defined in `config/device_config.py` (`DEVICE_SUITE`). Edit there to swap any device.

### CLI options

```bash
# Run all four devices (default)
python -m tasks.run_multi_device

# Override site
python -m tasks.run_multi_device --site independent_staging

# Run a subset of devices
python -m tasks.run_multi_device --devices desktop,mobile_ios

# Run a specific test across all devices
python -m tasks.run_multi_device --test pbjs_display_bidder_presence_test

# Upload results + regression diff
python -m tasks.run_multi_device --regression

# Run via BrowserStack from a specific geo
python -m tasks.run_multi_device --browserstack --geo uk
python -m tasks.run_multi_device --browserstack --geo us
```

### Output format

1. **Per-device matrix** — the standard test × URL grid is printed after each device completes, prefixed with a device banner.
2. **Cross-device summary** — a compact table printed once at the end:

```
=================================================================
📊 CROSS-DEVICE SUMMARY (rows=tests, cols=devices)
-----------------------------------------------------------------
| Test                          | desktop | mobile_ios | tablet |
| pbjs_display_bidder_presence  | PASS    | PASS       | PASS   |
| gpt_page_type_test            | PASS    | FAIL (1/5) | PASS   |
| env_is_mobile_or_tablet_test  | PASS    | PASS       | PASS   |
-----------------------------------------------------------------
```

### Parallel device mode

By default, devices run **sequentially** for clean, readable log output. To run all four devices concurrently (faster, but logs interleave), add to `base_config.py`:

```python
self.test_config["parallel_devices"] = True
```

---

## Google Sheets Output

After each run, the framework creates a new timestamped Google Spreadsheet with colour-coded results. The URL is printed at the end of the run and the sheet is shared to your configured Google account.

The sheet title includes the site and geo so you can tell runs apart at a glance:
`Ad Tests — 2026-06-03 14:32  [independent_uat]  [UK]`

### Sheet layout

| Tab | Contents |
|---|---|
| **test_run_summary** | Run header (site · env · geo · timestamp) · per-device pass-rate table · cross-device comparison matrix with clickable hyperlinks from FAIL/MIXED cells to the relevant device tab |
| **desktop** | Test × URL matrix · failure details · URL key |
| **mobile_ios** | Same layout |
| **mobile_android** | Same layout |
| **tablet** | Same layout |
| **regression** | New failures · known failures · fixed tests vs. the previous run for the same geo (only present when `--regression` is passed) |
| **appendix** | Description, conditions, and pass/fail criteria for every test (from module docstrings) |

Colour key: green = PASS · red = FAIL · dark red = ERROR · amber = MIXED · grey = SKIP · light grey = N/A (test not applicable to this page type or geo)

### Authentication (OAuth — recommended)

Sheets auth uses your personal Google account via OAuth. On first run it opens a browser to authenticate; after that it runs fully headlessly using a cached refresh token.

**One-time setup:**

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create or select a project
2. Enable **Google Sheets API** and **Google Drive API** under APIs & Services → Library
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Download the JSON file and save it as `~/.config/adunit-oauth-client.json`
4. Under **OAuth consent screen**, set publishing status to **Production** (prevents the refresh token expiring every 7 days)
5. Configure in `base_config.py`:

```python
self.sheets_config = {
    "sheets_enabled": True,
    "sheets_share_email": "you@independent.co.uk",
    "sheets_drive_folder_id": "your-drive-folder-id",
    "sheets_oauth_credentials": "~/.config/adunit-oauth-client.json",
}
```

Run any test task — a browser window will open for the first-time Google sign-in. Subsequent runs are fully headless.

---

## BrowserStack Automate

The framework can run against BrowserStack's cloud browsers instead of local Playwright, giving you real browser engines, session video recordings, network waterfalls, and console logs for every page.

> **Requires a BrowserStack Automate plan.** Live-only plans will not work.

### Setup

Add your BrowserStack credentials to `env.local`:

```
BROWSERSTACK_USERNAME="your_username"
BROWSERSTACK_ACCESS_KEY="your_access_key"
```

Find both values by clicking the key icon (🔑) in the BrowserStack Automate dashboard.

Source the file before running:

```bash
set -a && source env.local && set +a
```

### Running

```bash
# Single device
python -m tasks.run_tests --browserstack

# All four devices
python -m tasks.run_multi_device --browserstack

# With geo — sets BrowserStack IP location and tags all results accordingly
python -m tasks.run_multi_device --browserstack --geo uk
python -m tasks.run_multi_device --browserstack --geo us
```

### Geo and BrowserStack

Without `--geo`, BrowserStack sessions run from a US IP by default. Always pass `--geo` explicitly to ensure the session IP, Supabase tagging, and regression scoping are all consistent.

The `--geo uk` flag sets `browserstack.geoLocation: GB` in the session capabilities; `--geo us` sets `US`. No VPN configuration is needed — BrowserStack handles geo at the infrastructure level.

### Session timeout protection

Each URL worker in parallel mode has a hard timeout derived from your `timeout` and `prebid_ready_timeout` config values (default ~170s per URL). If a BrowserStack session drops mid-run (e.g. session quota exceeded), the worker exits cleanly rather than hanging the entire gather indefinitely.

### Device mapping

| Playwright profile | BrowserStack target |
|---|---|
| `Desktop Chrome` | Chrome (latest) on Windows 11 |
| `Desktop Edge` | Edge (latest) on Windows 11 |
| `Desktop Firefox` | Firefox (latest) on Windows 11 |
| `Desktop Safari` | WebKit on macOS Sonoma |
| `iPhone *` / `iPad *` | WebKit on macOS Sonoma (same engine as iOS Safari) |
| `Pixel 7` / other Android | Chrome (latest) on Windows 11 |

Playwright's device profile (viewport, user agent, touch) is applied on top of the BrowserStack session — so mobile emulation behaves identically to a local run, but executes on BrowserStack infrastructure with full session recording.

### Viewing results

After a run, go to **BrowserStack Automate → Build Runs** → click the **IDNML** build → click any session. Each session has:

- **Video** — full recording of the browser from page load to close
- **Network** — request waterfall (filter by domain to find pbjs/GPT calls)
- **Console** — every `console.log/warn/error` the page emitted
- **Logs** — Playwright command log

---

## Supabase / Regression Tracking

Pass `--regression` to any task to upload results to Supabase and include a week-over-week regression diff in the Google Sheet.

```bash
python -m tasks.run_tests --regression
python -m tasks.run_multi_device --regression

# Geo-specific regression — UK and US runs are tracked and compared independently
python -m tasks.run_multi_device --browserstack --geo uk --regression
python -m tasks.run_multi_device --browserstack --geo us --regression
```

Each result row in Supabase is tagged with `geo`, `device`, `publisher`, and `environment`. Regression diffs are scoped to the same combination — a UK run only compares against the previous UK run, and a US run only against the previous US run. Running both geos on the same cadence gives you independent regression histories per geo.

Supabase credentials are read from `env.local`:

```
NEXT_PUBLIC_SUPABASE_URL="https://your-project.supabase.co"
NEXT_PUBLIC_SUPABASE_ANON_KEY="your-anon-key"
```

---

## Architecture Notes

- **Browser targeting** — `BrowserManager` checks for `browserstack_enabled` in config and connects to BrowserStack via CDP (`browser_type.connect()`) if set; otherwise launches Chromium locally. All context creation, Prebid hooks, and test logic are identical in both modes.
- **Device detection** — Playwright's built-in device profiles set viewport, UA, touch, and `is_mobile`. `core/device_helpers.py` derives `mobile`/`desktop` from viewport aspect ratio (portrait = mobile).
- **Prebid event capture** — A `context.add_init_script` hook fires before every page script and attaches `pbjs.onEvent` listeners, splitting events into `display` and `video` streams (`window.__pbjsBidEventsDisplay` / `window.__pbjsBidEventsVideo`).
- **Basic auth** — Pre-prod credentials are passed via Playwright `http_credentials`, not via URL injection (which breaks `History.replaceState` and `fetch` on some pages).
- **CMP** — Consent is handled once per session on the first URL; subsequent pages inherit the accepted consent from the shared browser context. Skipped entirely for US geo (no consent banner shown in the US).
- **Geo** — Passed via `--geo uk|us`. Controls the BrowserStack IP location, skips CMP and video Prebid tests for US, stamps every Supabase result row, and scopes regression diffs per geo. When set, takes precedence over the page's `Locale` cookie for `context_summary.geo`.
- **Video tests** — All `VideoOnlyTest` subclasses (e.g. `pbjs_video_bidder_presence_test`) return **N/A** for US geo and on non-video pages. The US uses a different video player with no Prebid auction for `hero_player`. The readiness waiter also skips waiting for the hero auction on video pages in US geo.
- **N/A vs SKIP vs ERROR** — `N/A` means the test is structurally not applicable to this page type or geo (e.g. article-ID test on an index page, video test on US geo). `SKIP` means the test could not run due to a missing infrastructure dependency (e.g. Supabase not configured). `ERROR` means the test's prerequisite chain broke at runtime (e.g. JW Player didn't load, Prebid auction didn't fire) — this always indicates a real problem. `FAIL` is reserved for tests that completed their prerequisite chain but whose final assertion failed (e.g. wrong bidder set, missing signal). Only `N/A` is expected and excluded from failure counts.
- **Warmup** — Configurable warmup phase loads N pages before testing starts to prime the browser context and consent state.
- **Parallel mode** — URLs can be tested in parallel using a bounded semaphore (`concurrency` in config). Each parallel worker gets its own page within the shared browser context. Each worker has a hard timeout (nav + readiness + 120s buffer) so a stale or dropped BrowserStack session cannot hang the run indefinitely.
- **Test discovery** — `core/framework/discovery.py` auto-discovers all `BaseTest` subclasses from the `tests/` directory. No registration required; adding a new file is enough.
