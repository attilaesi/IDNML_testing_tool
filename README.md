# Ad Testing Framework

A modular, async Playwright-based framework for validating ad implementations across Independent and Standard Media Group sites. Tests cover Prebid.js configuration, GPT key-value targeting, layout/ad-sequence rules, and environment integrity.

---

## Quick Start

```bash
pip install -r requirements.txt
playwright install chromium

# Run all tests against the active site profile
python -m tasks.run_tests

# Run a single test
python -m tasks.run_tests --test pbjs_display_bidder_presence_test

# Override the site profile
python -m tasks.run_tests --site independent_uat
```

---

## Project Structure

```
config/
  base_config.py        — Master config: site, device, timeouts, feature flags
  device_config.py      — Playwright device profile selector (ACTIVE_DEVICE)
  site_urls.py          — URL sets per site profile
  site_test_plans.py    — Per-publisher test exclusion rules

core/
  framework_manager.py  — Main orchestrator: crawl, run tests, output matrix
  browser_manager.py    — Playwright context creation (device profile, auth, Prebid hooks)
  base_test.py          — BaseTest / TestResult / TestState base classes
  device_helpers.py     — Viewport-based device type detection (mobile vs desktop)
  cmp_handler.py        — Consent banner dismissal
  readiness_waiter.py   — Wait for Prebid + GPT to be ready on page
  supabase_helpers.py   — Supabase credential resolution for bidder config queries
  url_context_helpers.py— Publisher/env/page-type detection from URL

tasks/
  run_tests.py          — CLI entry point: discover and run all ad tests
  run_crawler.py        — Sitemap-based URL crawler entry point
  common.py             — Shared output/summary helpers

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
| `pbjs_pubcid_presence_display_test` | PubCID module active for display |
| `pbjs_pubcid_presence_video_test` | PubCID module active for video |
| `pbjs_auction_activity_test` | Auction fired and received bids |
| `pbjs_adunit_configuration_test` | Ad unit config is valid |
| `pbjs_consent_integration_test` | Prebid consent integration |
| `pbjs_identity_modules_test` | Identity modules loaded |
| `pbjs_mantis_signals_bid_test` | Mantis signals passed into bids |
| `pbjs_permutive_signals_bid_test` | Permutive signals passed into bids |
| `pbjs_timeout_config_test` | Bid timeout configured correctly |
| `pbjs_warnings_test` | No unexpected Prebid warnings |
| `pbjs_environment_test` | Prebid version and environment checks |

### Layout tests
| Test | What it checks |
|---|---|
| `layout_ad_sequence_test` | Ad slots appear in the expected order in the DOM |
| `taboola_load_time_test` | Taboola widget loads within the acceptable time budget |

---

## Output

- **Terminal matrix** — pass/fail grid (tests × URLs) printed after each run, with ANSI colour coding
- **CSV** — `output/output.csv` (per test × URL), `output/output_by_pagetype.csv` (aggregated by page type)
- **Text report** — `output/` directory

---

## Site Test Plans

`config/site_test_plans.py` maps each publisher to a set of test exclusion rules:
- `exclude` — tests never run on this publisher
- `exclude_by_page_type` — tests excluded for specific page types (e.g. video, article)

Tests in the `ENVIRONMENT` category are always exempt from site plan exclusions.

---

## Google Sheets Output

After each run, the framework can create a new timestamped Google Spreadsheet containing colour-coded results. The spreadsheet URL is printed at the end of the run and the sheet is shared directly to your Google account.

### Sheet layout

| Tab | Contents |
|---|---|
| **Summary** | Run header · per-device pass-rate table · cross-device comparison matrix with clickable hyperlinks from FAIL/MIXED cells to the exact row in the relevant device tab |
| **desktop** | Test × URL matrix · failure details · URL key |
| **mobile_ios** | Same layout |
| **mobile_android** | Same layout |
| **tablet** | Same layout |

Colour key: green = PASS · red = FAIL · dark red = ERROR · amber = MIXED · grey = SKIP/SKIP

### Google Cloud setup (one-time)

**1. Create a Google Cloud project**
- Go to [console.cloud.google.com](https://console.cloud.google.com)
- Create a new project (or select an existing one)

**2. Enable APIs**
- In the project, go to **APIs & Services → Library**
- Search for and enable **Google Sheets API**
- Search for and enable **Google Drive API**

**3. Create a service account**
- Go to **APIs & Services → Credentials → Create Credentials → Service Account**
- Give it a name (e.g. `ad-testing-bot`)
- No roles are needed at the project level — click through to finish
- On the service account detail page, go to **Keys → Add Key → Create new key → JSON**
- Download the JSON file and store it somewhere safe (e.g. `~/.config/ad-testing-sa.json`)

**4. Configure the env var**

```bash
# Add to your shell profile (~/.zshrc or ~/.bash_profile):
export GOOGLE_SERVICE_ACCOUNT_JSON="/path/to/your/service-account-key.json"

# Or, for CI pipelines, set it to the JSON content directly:
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account", ...}'
```

**5. Enable Sheets output in config**

```python
# config/base_config.py
self.sheets_config = {
    "sheets_enabled": True,
    "sheets_share_email": "you@independent.co.uk",  # your Google account
}
```

Or set `SHEETS_SHARE_EMAIL` as an env var instead.

When the run completes, the new spreadsheet is created in the service account's Drive and shared with your email — it will appear in **"Shared with me"** in Google Drive.

### Running with Sheets output

```bash
# Single-device run
python -m tasks.run_tests

# Multi-device run
python -m tasks.run_multi_device
```

Both runners check `sheets_enabled` and write a sheet if it is `True`. Each run creates a new spreadsheet (nothing is overwritten).

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

Cell values:
- `PASS` — all URLs passed on that device
- `FAIL (N/M)` — N out of M URLs failed or errored
- `SKIP` — all URLs skipped
- `MIXED` — mix of pass and skip (no failures)
- `-` — no results recorded

### Parallel device mode

By default, devices run **sequentially** for clean, readable log output. To run all four devices concurrently (faster, but logs interleave), add to `base_config.py`:

```python
self.test_config["parallel_devices"] = True
```

### CSV output

Multi-device runs write to separate files so single-device runs are not overwritten:
- `output/output_multi_device.csv`
- `output/output_by_pagetype_multi_device.csv`

---

## Architecture Notes

- **Device detection** — Playwright's built-in device profiles set viewport, UA, touch, and `is_mobile`. `core/device_helpers.py` derives `mobile`/`desktop` from viewport aspect ratio (portrait = mobile).
- **Prebid event capture** — A `context.add_init_script` hook fires before every page script and attaches `pbjs.onEvent` listeners, splitting events into `display` and `video` streams (`__pbjsBidEventsDisplay` / `__pbjsBidEventsVideo`).
- **Basic auth** — Pre-prod credentials are passed via Playwright `http_credentials`, not via URL injection (which breaks `History.replaceState` and `fetch` on some pages).
- **CMP** — Consent is handled once per session on the first URL; subsequent pages inherit the accepted consent from the shared browser context.
- **Warmup** — Configurable warmup phase loads N pages before testing starts to prime the browser context and consent state.
- **Parallel mode** — URLs can be tested in parallel using a bounded semaphore (`concurrency` in config). Each parallel worker gets its own page within the shared browser context.
