from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from scrapers.base import CatalogSource
from scrapers.models import Anime, Episode

class AnimeAlphaCatalogSource(CatalogSource):
    """Accurate scraper for animealpha.cc resolving download landing pages to direct video streams."""
    def __init__(self, base_url: str = "https://www.animealpha.cc"):
        self.base_url = base_url.rstrip("/")
        self.client = AsyncSession(impersonate="chrome", timeout=15.0)

    async def search_anime(self, query: str) -> list[Anime]:
        try:
            response = await self.client.get(f"{self.base_url}/search", params={"q": query})
            if response.status_code != 200:
                response = await self.client.get(f"{self.base_url}/search", params={"keyword": query})
            
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            seen = set()
            
            for a_tag in soup.select("a[href*='/anime/']"):
                href = a_tag.get("href", "")
                if "/anime/" not in href:
                    continue
                anime_id = href.strip("/").split("/")[-1]
                if anime_id in seen or not anime_id:
                    continue
                seen.add(anime_id)
                
                title = a_tag.get_text(strip=True)
                if not title or len(title) < 2:
                    title_elem = a_tag.select_one(".title, h3, h4, strong")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                if not title:
                    title = anime_id.replace("-", " ").title()
                
                if query.casefold() in title.casefold() or len(results) < 5:
                    results.append(Anime(id=anime_id, title=title))
            
            return results[:20]
        except Exception as e:
            print(f"Error searching animealpha: {e}")
            return []

    async def _resolve_direct_link(self, landing_url: str) -> str:
        """Visits the animealpha download landing page and extracts the actual media file link."""
        try:
            resp = await self.client.get(landing_url)
            if resp.status_code != 200:
                return landing_url
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Look for direct video files or CDN links inside the landing page
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if any(ext in href.lower() for ext in [".mp4", ".mkv", ".m3u8", "cdn", "storage", "dl="]):
                    return href if href.startswith("http") else f"{self.base_url}{href}"
            
            # Check for embedded video source tags
            source = soup.select_one("video source, source")
            if source:
                src = source.get("src", "")
                if src:
                    return src if src.startswith("http") else f"{self.base_url}{src}"
            
            return landing_url
        except Exception:
            return landing_url

    async def get_anime(self, anime_id: str) -> Anime | None:
        try:
            response = await self.client.get(f"{self.base_url}/anime/{anime_id}")
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            title_elem = soup.select_one("h1, .anime-title, title")
            title = title_elem.get_text(strip=True) if title_elem else anime_id.replace("-", " ").title()
            
            synopsis_elem = soup.select_one(".synopsis, .description, p")
            synopsis = synopsis_elem.get_text(strip=True) if synopsis_elem else ""
            
            episodes = []
            links = soup.select("a[href]")
            ep_map = {}
            
            # Collect download landing links
            raw_qualities = {}
            for a in links:
                href = a.get("href", "")
                text = a.get_text(strip=True)
                
                if "/download/" in href or "download" in href.lower():
                    full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                    
                    q_name = None
                    if "1080" in text or "1920" in href or "1080p" in text:
                        q_name = "1080p"
                    elif "720" in text or "1280" in href or "720p" in text:
                        q_name = "720p"
                    elif "480" in text or "854" in href or "480p" in text:
                        q_name = "480p"
                    elif "360" in text or "640" in href or "360p" in text:
                        q_name = "360p"
                    
                    if q_name:
                        ep_num = 1
                        for part in href.split("/"):
                            if part.isdigit():
                                ep_num = int(part)
                                break
                        
                        if ep_num not in ep_map:
                            ep_map[ep_num] = {}
                        ep_map[ep_num][q_name] = full_url

            # Resolve landing pages to direct media links
            for ep_num, q_dict in sorted(ep_map.items()):
                resolved_qualities = {}
                for q_name, landing_url in q_dict.items():
                    direct_url = await self._resolve_direct_link(landing_url)
                    resolved_qualities[q_name] = direct_url
                
                episodes.append(Episode(
                    id=f"ep-{ep_num}",
                    number=ep_num,
                    title=f"Episode {ep_num}",
                    qualities=resolved_qualities
                ))

            if not episodes:
                episodes.append(Episode(
                    id=f"{anime_id}-1",
                    number=1,
                    title="Episode 1",
                    qualities={"720p": f"{self.base_url}/anime/{anime_id}"}
                ))

            return Anime(id=anime_id, title=title, synopsis=synopsis, episodes=episodes)
        except Exception as e:
            print(f"Error getting anime {anime_id}: {e}")
            return None

    async def get_episode(self, anime_id: str, episode_id: str) -> Episode | None:
        anime = await self.get_anime(anime_id)
        if not anime:
            return None
        return next((e for e in anime.episodes if e.id == episode_id), anime.episodes[0] if anime.episodes else None)
        
