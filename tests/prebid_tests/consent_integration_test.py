"""
prebid: ConsentIntegrationTest

What this test is meant to test
-------------------------------
Verifies that Prebid's consent module is correctly wired to a CMP for the
current site, using the *modern* consentManagement structure:

    consentManagement: {
        gdpr: { cmpApi: "iab", ... },
        usp:  { cmpApi: "iab", ... },
        gpp:  { cmpApi: "iab", ... }
    }

The test checks that:
  - `pbjs.getConfig()` is available
  - `consentManagement` exists in the config
  - For each configured namespace (gdpr / usp / gpp), `cmpApi` is present.

We no longer expect a top-level `consentManagement.cmpApi` (old Prebid style).

Test conditions
---------------
1. `window.pbjs` must exist.
2. `pbjs.getConfig` must be a function.
3. `pbjs.getConfig().consentManagement` must be present.
4. For each of the consent namespaces that are present
   (`gdpr`, `usp`, `gpp`), `cmpApi` must be non-empty.

What counts as PASS / FAIL / SKIPPED
------------------------------------
* SKIPPED:
    - `window.pbjs` is missing (no Prebid on the page).

* FAILED:
    - `pbjs.getConfig` is missing, or
    - `consentManagement` is missing from the config, or
    - At least one configured namespace (gdpr / usp / gpp) has no `cmpApi`.

* PASSED:
    - At least one consent namespace is configured, and
    - Every configured namespace (gdpr / usp / gpp) has `cmpApi` set.

Notes
-----
We don’t enforce WHICH namespaces must exist (that depends on geo),
only that any namespace which *does* exist is correctly wired to a CMP.
"""

from typing import Any, Dict

from core.base_test import BaseTest, TestResult, TestState


class ConsentIntegrationTest(BaseTest):
    """Check that Prebid consentManagement is correctly configured."""

    async def setup(self, page, url: str) -> bool:
        """
        Setup phase.

        We just verify that Prebid exists; CMP interaction / cookies are
        handled earlier by the framework.
        """
        has_pbjs = await page.evaluate("() => !!window.pbjs")
        if self.config.get("debug_test_trace"):
            print(
                f"[ConsentIntegrationTest] setup: url={url}, "
                f"has_pbjs={has_pbjs}"
            )

        # If there is no Prebid at all, we skip all Prebid tests.
        if not has_pbjs:
            return False
        return True

    async def execute(self, page, url: str) -> TestResult:
        """
        Execute phase.

        We pull a diagnostic object from `pbjs.getConfig()` that captures the
        consentManagement branch and each of the three namespaces:
        gdpr / usp / gpp.
        """
        result = TestResult(self.name)
        result.url = url

        js = """
        () => {
          const w = window;
          const out = {
            hasPbjs: !!w.pbjs,
            hasGetConfig: false,
            consentManagement: null,
            gdpr: null,
            usp: null,
            gpp: null,
            error: null
          };

          if (!w.pbjs || typeof w.pbjs.getConfig !== "function") {
            out.hasGetConfig = !!(w.pbjs && typeof w.pbjs.getConfig === "function");
            return out;
          }

          out.hasGetConfig = true;

          try {
            const cfg = w.pbjs.getConfig() || {};
            const cm = cfg.consentManagement || {};
            out.consentManagement = cm || null;
            out.gdpr = cm.gdpr || null;
            out.usp  = cm.usp  || null;
            out.gpp  = cm.gpp  || null;
          } catch (e) {
            out.error = String(e && e.message ? e.message : e);
          }

          return out;
        }
        """

        diag = await page.evaluate(js)
        result.data = diag or {}

        if self.config.get("debug_test_trace"):
            cm = (diag or {}).get("consentManagement")
            print(
                "[ConsentIntegrationTest] execute diag: "
                f"hasPbjs={diag.get('hasPbjs')}, "
                f"hasGetConfig={diag.get('hasGetConfig')}, "
                f"cm_keys={list(cm.keys()) if isinstance(cm, dict) else None}"
            )

        # State is decided in validate()
        return result

    async def validate(self, result: TestResult) -> TestResult:
        """
        Validation phase.

        We interpret the diagnostic object and decide PASSED / FAILED / SKIPPED.
        """
        diag: Dict[str, Any] = result.data or {}
        has_pbjs = diag.get("hasPbjs", False)
        has_get_config = diag.get("hasGetConfig", False)
        error = diag.get("error")
        cm = diag.get("consentManagement")

        # 1) No Prebid at all -> SKIPPED
        if not has_pbjs:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "window.pbjs not present; cannot inspect consentManagement config."
            )
            return result

        # 2) pbjs present but no getConfig -> FAILED
        if not has_get_config:
            result.state = TestState.FAILED
            result.errors.append("pbjs.getConfig is not available; "
                                 "cannot read consentManagement configuration.")
            return result

        # 3) Exception while reading config -> FAILED
        if error:
            result.state = TestState.FAILED
            result.errors.append(
                f"Error while reading pbjs.getConfig(): {error}"
            )
            return result

        # 4) consentManagement missing -> FAILED
        if not isinstance(cm, dict) or not cm:
            result.state = TestState.FAILED
            result.errors.append(
                "Prebid consentManagement config not present in pbjs.getConfig()."
            )
            return result

        # 5) Check each namespace that actually exists
        namespaces = {
            "gdpr": diag.get("gdpr"),
            "usp": diag.get("usp"),
            "gpp": diag.get("gpp"),
        }

        configured_namespaces = []
        missing_cmpapi = []

        for ns, cfg in namespaces.items():
            if not cfg:
                # Namespace not configured at all – that's fine, geo-dependent.
                continue

            configured_namespaces.append(ns)
            cmp_api = None
            if isinstance(cfg, dict):
                cmp_api = cfg.get("cmpApi")

            if not cmp_api:
                missing_cmpapi.append(ns)

        if not configured_namespaces:
            # consentManagement exists but no known namespaces present
            result.state = TestState.FAILED
            result.errors.append(
                "consentManagement is present in pbjs.getConfig(), but none of the "
                "expected namespaces (gdpr / usp / gpp) are configured."
            )
            return result

        if missing_cmpapi:
            result.state = TestState.FAILED
            result.errors.append(
                "cmpApi is not configured for consent namespaces: "
                + ", ".join(f"consentManagement.{ns}.cmpApi" for ns in missing_cmpapi)
            )
            return result

        # All configured namespaces have cmpApi set -> PASS
        result.state = TestState.PASSED

        # Helpful metadata for CSV / summaries
        result.metadata.setdefault("consent_namespaces", configured_namespaces)

        if self.config.get("debug_test_trace"):
            print(
                "[ConsentIntegrationTest] validate: PASSED; "
                f"namespaces={configured_namespaces}"
            )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        """
        Cleanup phase.

        Currently a no-op, but kept for symmetry / future debugging hooks.
        """
        return