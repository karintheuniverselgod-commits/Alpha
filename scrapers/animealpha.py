from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from scrapers.base import CatalogSource
from scrapers.models import Anime, Episode

class AnimeAlphaCatalogSource(CatalogSource):
    """Accurate scraper for animealpha.cc supporting multi-quality buttons and direct media extraction."""
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
            
            # Find all episode or watch links on the anime page
            episode_links = soup.select("a[href*='/watch/'], a[href*='/episode/'], .episodes-list a, .list-eps a")
            if not episode_links:
                episode_links = [a for a in soup.select("a[href]") if "ep" in a.get("href", "").lower()]

            if episode_links:
                for idx, ep_link in enumerate(episode_links, start=1):
                    ep_href = ep_link.get("href", "")
                    ep_id = ep_href.strip("/").split("/")[-1] or f"ep-{idx}"
                    ep_title = ep_link.get_text(strip=True) or f"Episode {idx}"
                    
                    qualities = await self._get_qualities_for_episode(ep_href)
                    if qualities:
                        episodes.append(Episode(id=ep_id, number=idx, title=ep_title, qualities=qualities))

            # Fallback if no individual episode pages were matched
            if not episodes:
                # Look for direct quality/download options on the main page
                qualities = {}
                for a in soup.select("a[href]"):
                    href = a.get("href", "")
                    text = a.get_text(strip=True).lower()
                    full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                    
                    if "1080" in text or "1080p" in text:
                        qualities["1080p"] = full_url
                    elif "720" in text or "720p" in text:
                        qualities["720p"] = full_url
                    elif "480" in text or "480p" in text:
                        qualities["480p"] = full_url
                    elif "360" in text or "360p" in text:
                        qualities["360p"] = full_url

                if not qualities:
                    qualities["720p"] = f"{self.base_url}/anime/{anime_id}"

                episodes.append(Episode(id=f"{anime_id}-1", number=1, title="Episode 1", qualities=qualities))

            return Anime(id=anime_id, title=title, synopsis=synopsis, episodes=episodes)
        except Exception as e:
            print(f"Error getting anime {anime_id}: {e}")
            return None

    async def _get_qualities_for_episode(self, ep_path: str) -> dict[str, str]:
        """Extracts available qualities (360p, 480p, 720p, 1080p) from the episode watch page."""
        qualities_dict = {}
        try:
            url = ep_path if ep_path.startswith("http") else f"{self.base_url}{ep_path}"
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return {}
            
            ep_soup = BeautifulSoup(resp.text, "html.parser")
            
            # Search for quality buttons, links, or video source tags on the watch page
            for elem in ep_soup.select("a[href], source, video"):
                href = elem.get("href") or elem.get("src", "")
                text = elem.get_text(strip=True).lower()
                
                if not href:
                    continue
                
                full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                
                if "1080" in text or "1080p" in text or "1920" in href:
                    qualities_dict["1080p"] = full_url
                elif "720" in text or "720p" in text or "1280" in href:
                    qualities_dict["720p"] = full_url
                elif "480" in text or "480p" in text or "854" in href:
                    qualities_dict["480p"] = full_url
                elif "360" in text or "360p" in text or "640" in href:
                    qualities_dict["360p"] = full_url

            # If no specific quality labels found, fallback to any download/stream link on the page
            if not qualities_dict:
                for a in ep_soup.select("a[href*='download'], a[href*='stream'], a[href*='file']"):
                    href = a.get("href", "")
                    full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                    qualities_dict["720p"] = full_url
                    break

            if not qualities_dict:
                qualities_dict["720p"] = url

        except Exception as e:
            print(f"Error fetching episode qualities: {e}")
            
        return qualities_dict

    async def get_episode(self, anime_id: str, episode_id: str) -> Episode | None:
        anime = await self.get_anime(anime_id)
        if not anime:
            return None
        return next((e for e in anime.episodes if e.id == episode_id), anime.episodes[0] if anime.episodes else None)
        
