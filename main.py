# main.py
import asyncio
from core.base_test import TestState

# Try to use CONFIG if it's exported; otherwise build it from TestConfig
try:
    from config.base_config import CONFIG
except ImportError:
    from config.base_config import TestConfig
    CONFIG = TestConfig().get_config()

from core.framework_manager import TestFramework


async def main():
    print("🚀 Ad Testing Framework")
    print(f"Active site: {CONFIG.get('active_site', '')}")
    print(f"Site URL: {CONFIG.get('site_url', '')}")
    print(f"Max pages: {CONFIG.get('max_pages', 10)}")
    print(f"Mobile mode: {CONFIG.get('mobile', False)}")
    print(f"Headless: {CONFIG.get('headless', True)}")
    print("-" * 50)

    framework = TestFramework(CONFIG)
    framework.discover_tests()

    # Run everything
    results = await framework.run_tests()

    # ------------------------------------------------------------------
    # FILTER: remove skipped tests entirely
    # ------------------------------------------------------------------
    executed = [r for r in results if r.state not in (TestState.SKIPPED,)]

    passed = sum(1 for r in executed if r.state == TestState.PASSED)
    failed = sum(1 for r in executed if r.state == TestState.FAILED)
    errors = sum(1 for r in executed if r.state == TestState.ERROR)

    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY (overall)")
    print(f"Total executed tests: {len(executed)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"💥 Errors: {errors}")

    # ------------------------------------------------------------------
    # PER-URL SUMMARY — also excluding skipped tests
    # ------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY BY URL")

    # Group results by URL
    results_by_url = {}
    for r in executed:
        results_by_url.setdefault(r.url, []).append(r)

    for idx, (url, url_results) in enumerate(results_by_url.items(), start=1):
        # Derive pageType if present
        page_type = url_results[0].metadata.get("page_type", "unknown")
        ctx = (url_results[0].metadata or {}).get("context_summary") or {}

        passed_u = sum(1 for r in url_results if r.state == TestState.PASSED)
        failed_u = sum(1 for r in url_results if r.state == TestState.FAILED)
        errors_u = sum(1 for r in url_results if r.state == TestState.ERROR)

        print(f"\n🔹 URL {idx}/{len(results_by_url)}")
        print(f"   {url}   (pageType: {page_type})")
        if ctx:
            print(
                "   🔎 Context: "
                f"publisher={ctx.get('publisher')} env={ctx.get('env')} "
                f"device={ctx.get('device')} geo={ctx.get('geo')} "
                f"gpt_page_type={ctx.get('gpt_page_type')} liveblog={ctx.get('liveblog')} "
                f"db_page_type={ctx.get('db_page_type')} "
                f"displayEvents={ctx.get('displayEvents')} videoEvents={ctx.get('videoEvents')} "
                f"displayBidReq={ctx.get('displayBidReq')} videoBidReq={ctx.get('videoBidReq')}"
            )
        print(f"   Total executed tests: {len(url_results)}")
        print(f"   ✅ Passed:  {passed_u}")
        print(f"   ❌ Failed:  {failed_u}")
        print(f"   💥 Errors:  {errors_u}")

        # Print failed/error test details
        failed_or_err = [
            r for r in url_results
            if r.state in (TestState.FAILED, TestState.ERROR)
        ]

        if failed_or_err:
            print("   🔍 Failed / Error tests:")
            for r in failed_or_err:
                print(f"     • {r.test_name}")
                msgs = r.errors if r.errors else r.warnings
                for entry in msgs:
                    for line in str(entry).splitlines():
                        print("         - " + line)
        print("===============================================================================")

    print()  # final newline


if __name__ == "__main__":
    asyncio.run(main())