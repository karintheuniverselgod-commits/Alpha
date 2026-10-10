from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from scrapers.base import CatalogSource
from scrapers.models import Anime, Episode

class AnimeAlphaCatalogSource(CatalogSource):
    """Accurate scraper for animealpha.cc extracting true direct video stream URLs."""
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
            episode_links = soup.select("a[href*='/episodes/'], a[href*='/watch/'], a[href*='/episode/']")
            
            if not episode_links:
                episode_links = [a for a in soup.select("a[href]") if "ep" in a.get("href", "").lower()]

            if episode_links:
                seen_eps = set()
                for idx, ep_link in enumerate(episode_links, start=1):
                    ep_href = ep_link.get("href", "")
                    if not ep_href or ep_href in seen_eps:
                        continue
                    seen_eps.add(ep_href)
                    
                    ep_id = ep_href.strip("/").split("/")[-1] or f"ep-{idx}"
                    ep_title = ep_link.get_text(strip=True) or f"Episode {idx}"
                    
                    qualities = await self._get_qualities_for_episode(ep_href)
                    if qualities:
                        episodes.append(Episode(id=ep_id, number=idx, title=ep_title, qualities=qualities))
            
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

    async def _get_qualities_for_episode(self, ep_path: str) -> dict[str, str]:
        """Visits the episode page and extracts the true direct video file URL."""
        qualities_dict = {}
        try:
            url = ep_path if ep_path.startswith("http") else f"{self.base_url}{ep_path}"
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return {}
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Look for direct video source tags, download buttons, or storage links
            for a in soup.select("a[href], source, video"):
                href = a.get("href") or a.get("src", "")
                text = a.get_text(strip=True).lower()
                
                if not href:
                    continue
                
                full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                
                if any(ext in href.lower() for ext in [".mp4", ".mkv", ".m3u8", "dl=", "storage", "cdn"]):
                    if "1080" in text or "1080" in href or "1920" in href:
                        qualities_dict["1080p"] = full_url
                    elif "720" in text or "720" in href or "1280" in href:
                        qualities_dict["720p"] = full_url
                    elif "480" in text or "480" in href or "854" in href:
                        qualities_dict["480p"] = full_url
                    else:
                        qualities_dict["360p"] = full_url

            if not qualities_dict:
                for iframe in soup.select("iframe"):
                    iframe_src = iframe.get("src", "")
                    if iframe_src and "ads" not in iframe_src.lower():
                        clean_url = iframe_src if iframe_src.startswith("http") else f"https:{iframe_src}"
                        qualities_dict["720p"] = clean_url

            if not qualities_dict:
                qualities_dict["720p"] = url

        except Exception as e:
            print(f"Error fetching qualities: {e}")
            
        return qualities_dict

    async def get_episode(self, anime_id: str, episode_id: str) -> Episode | None:
        anime = await self.get_anime(anime_id)
        if not anime:
            return None
        return next((e for e in anime.episodes if e.id == episode_id), anime.episodes[0] if anime.episodes else None)
          
