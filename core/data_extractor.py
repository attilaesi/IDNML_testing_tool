import asyncio
from pathlib import Path
from typing import Dict, Any
from utils.helpers import flatten_value

_JS_BASIC = (Path(__file__).parent.parent / "tests" / "js" / "shared" / "data_extractor_basic.js").read_text()

class DataExtractor:
    """Common data extraction functionality from original script"""
    
    @staticmethod
    def flatten(val):
        """Flatten helper that proxies to utils.helpers.flatten_value"""
        return flatten_value(val)

    
    @staticmethod
    async def extract_basic_data(page, url: str) -> Dict[str, Any]:
        """Extract basic page data - keeps original functionality"""
        result: Dict[str, Any] = {
            "url": url,
            "slot_names": "",
            "slot_count": 0,
            "paragraphs": 0,
            "images": 0,
            "category1": "",
            "category2": "",
            "pageType": "",
            "liveblog": "",
            "error": None
        }
        
        try:

            
            js_result = await page.evaluate(_JS_BASIC)
            
            # Map results using original logic
            result["paragraphs"] = js_result["paragraphs"]
            result["images"] = js_result["images"]
            result["slot_count"] = js_result["ad_slots"]
            result["slot_names"] = DataExtractor.flatten(js_result["slots"])
            
            targeting = js_result["targeting"]
            for key in ("category1", "category2", "pageType", "liveblog"):
                result[key] = DataExtractor.flatten(targeting.get(key, []))
                
        except Exception as e:
            result["error"] = str(e)
        
        return result