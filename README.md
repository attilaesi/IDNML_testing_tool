# Ad Testing Framework

A modular, async Playwright-based framework for validating ad implementations across Independent and Standard Media Group sites. Tests cover Prebid.js configuration, GPT key-value targeting, layout/ad-sequence rules, and environment integrity.

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
| `pbjs_hero_player_placement_test` | Hero player ad unit configured correctly |
| `pbjs_price_floors_display_test` | Price floors set for display |
| `pbjs_price_floors_video_test` | Price floors set for video |
| `pbjs_display_pubcid_presence_test` | PubCID module active for display |
| `pbjs_video_pubcid_presence_test` | PubCID module active for video |
| `pbjs_auction_activity_test` | Auction fired and received bids |
| `pbjs_adunit_configuration_test` | Ad unit config is valid |
| `pbjs_consent_integration_test` | Prebid consent integration |
| `pbjs_identity_modules_test` | Identity modules loaded |
| `pbjs_mantis_signals_bid_test` | Mantis signals passed into bids |
| `pbjs_permutive_signals_bid_test` | Permutive signals passed into bids |
| `pbjs_prebid_timeout_config_test` | Bid timeout configured correctly |
| `pbjs_prebid_warnings_test` | No unexpected Prebid warnings |
| `pbjs_prebid_environment_test` | Prebid version and environment checks |

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

# Run via BrowserStack
python -m tasks.run_multi_device --browserstack
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

### Sheet layout

| Tab | Contents |
|---|---|
| **test_run_summary** | Run header · per-device pass-rate table · cross-device comparison matrix with clickable hyperlinks from FAIL/MIXED cells to the relevant device tab |
| **desktop** | Test × URL matrix · failure details · URL key |
| **mobile_ios** | Same layout |
| **mobile_android** | Same layout |
| **tablet** | Same layout |
| **appendix** | Description, conditions, and pass/fail criteria for every test (from module docstrings) |

Colour key: green = PASS · red = FAIL · dark red = ERROR · amber = MIXED · grey = SKIP

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
```

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
```

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
- **CMP** — Consent is handled once per session on the first URL; subsequent pages inherit the accepted consent from the shared browser context.
- **Warmup** — Configurable warmup phase loads N pages before testing starts to prime the browser context and consent state.
- **Parallel mode** — URLs can be tested in parallel using a bounded semaphore (`concurrency` in config). Each parallel worker gets its own page within the shared browser context.
- **Test discovery** — `core/framework/discovery.py` auto-discovers all `BaseTest` subclasses from the `tests/` directory. No registration required; adding a new file is enough.
