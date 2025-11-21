# utils/geo_utils.py
from typing import Dict, Any


async def detect_geo_from_cookies(page, fallback: str = "UK") -> str:
    """
    Inspect Locale and subscriber_origin cookies to decide if we're in
    UK or US (or something else).

    - Locale            = UK / GB / US / ...
    - subscriber_origin = "uk" / "us" / ...

    Returns e.g. "UK", "US", or the fallback if undetectable.
    """
    js = """
        () => {
          const getCookie = (name) => {
            const m = document.cookie.match(
              new RegExp('(?:^|; )' + name + '=([^;]*)')
            );
            return m ? decodeURIComponent(m[1]) : null;
          };
          return {
            locale: getCookie('Locale'),
            subscriber_origin: getCookie('subscriber_origin'),
          };
        }
    """

    try:
        data: Dict[str, Any] = await page.evaluate(js)
    except Exception:
        return fallback

    locale = (data.get("locale") or "").upper()
    origin = (data.get("subscriber_origin") or "").lower()

    # Treat GB as UK
    if locale in ("UK", "GB") or origin in ("uk", "gb"):
        return "UK"
    if locale in ("US", "USA") or origin in ("us", "usa"):
        return "US"

    return fallback