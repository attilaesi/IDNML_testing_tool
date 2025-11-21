import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from typing import List

class SitemapFetcher:
    def __init__(self, config):
        self.config = config
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8",
        }
    
    async def fetch_urls(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        sitemap_url: str = None
    ) -> List[str]:
        """Fetch URLs from sitemap, with basic debugging output."""
        
        async def _get_urls(url: str) -> List[str]:
            try:
                print(f"Fetching sitemap: {url}")
                async with session.get(url, headers=self.headers, timeout=15) as resp:
                    if resp.status != 200:
                        print(f"  ⚠️ Non-200 response for sitemap {url}: {resp.status}")
                        return []
                    text = await resp.text()
                
                soup = BeautifulSoup(text, "xml")
                
                # Handle sitemap index
                if soup.find("sitemapindex"):
                    urls: List[str] = []
                    for loc in soup.find_all("loc"):
                        child_url = loc.text.strip()
                        if not child_url:
                            continue
                        urls += await _get_urls(child_url)
                    print(f"  Found {len(urls)} URLs via sitemapindex {url}")
                    return urls
                
                # Handle urlset
                if soup.find("urlset"):
                    locs = [
                        loc.text.strip()
                        for loc in soup.find_all("loc")
                        if loc.text.strip()
                    ]
                    print(f"  Found {len(locs)} URLs in urlset {url}")
                    return locs
                
                # Fallback regex for malformed XML
                locs = re.findall(r"<loc>([^<]+)</loc>", text)
                print(f"  Found {len(locs)} URLs via regex fallback for {url}")
                return locs
            
            except Exception as e:
                print(f"  ❌ Error fetching sitemap {url}: {e}")
                return []
        
        all_urls: List[str] = []
        
        # Try provided sitemap URL first
        if sitemap_url:
            all_urls = await _get_urls(sitemap_url)
        
        # If that didn't work, try a few common sitemap paths
        if not all_urls:
            for path in ("sitemap.xml", "sitemap_index.xml", "/sitemap_index.xml"):
                candidate = urljoin(base_url, path)
                urls = await _get_urls(candidate)
                if urls:
                    all_urls = urls
                    break
        
        print(f"Total URLs discovered from sitemaps: {len(all_urls)}")
        return all_urls