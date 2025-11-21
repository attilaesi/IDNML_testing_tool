import asyncio
from typing import Dict, Any
from utils.helpers import flatten_value

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

            
            js_result = await page.evaluate(
                """
                () => {
                    const out = {
                        paragraphs: 0,
                        images: 0,
                        ad_slots: 0,
                        slots: [],
                        targeting: {}
                    };
                    
                    try { 
                        out.paragraphs = document.querySelectorAll('#main p').length; 
                    } catch {}
                    
                    try { 
                        out.images = document.querySelectorAll('#main img').length; 
                    } catch {}
                    
                    try {
                        const pub = googletag.pubads();
                        ['category1','category2','pageType','liveblog'].forEach(k => {
                            const v = pub.getTargeting(k);
                            if (v?.length) out.targeting[k] = v;
                        });
                        
                        const slots = pub.getSlots();
                        out.ad_slots = slots.length;
                        out.slots = slots.map(s => s.getAdUnitPath().split('/').pop());
                    } catch (e) {
                        // googletag not available or no slots
                    }
                    
                    return out;
                }
                """
            )
            
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