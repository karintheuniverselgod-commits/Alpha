import httpx
from bs4 import BeautifulSoup
from scrapers.base import CatalogSource
from scrapers.models import Anime, Episode

class AnimeAlphaCatalogSource(CatalogSource):
    """Live scraper for animealpha.cc extracting actual download links and streams."""
    def __init__(self, base_url: str = "https://www.animealpha.cc"):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{self.base_url}/"
        }
        self.client = httpx.AsyncClient(
            headers=self.headers,
            follow_redirects=True,
            timeout=15.0
        )

    async def search_anime(self, query: str) -> list[Anime]:
        try:
            response = await self.client.get(f"{self.base_url}/search", params={"keyword": query})
            if response.status_code != 200 or "blocked" in str(response.url):
                response = await self.client.get(f"{self.base_url}/search", params={"q": query})
            
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
            episode_links = soup.select("a[href*='/watch/'], a[href*='/episode/'], .episodes-list a, .list-eps a")
            
            if not episode_links:
                episode_links = [a for a in soup.select("a[href]") if "ep" in a.get("href", "").lower()]

            if episode_links:
                for idx, ep_link in enumerate(episode_links, start=1):
                    ep_href = ep_link.get("href", "")
                    ep_id = ep_href.strip("/").split("/")[-1] or f"ep-{idx}"
                    ep_title = ep_link.get_text(strip=True) or f"Episode {idx}"
                    
                    qualities = await self._get_qualities_for_episode(ep_href)
                    episodes.append(Episode(id=ep_id, number=idx, title=ep_title, qualities=qualities))
            else:
                qualities = await self._get_qualities_for_episode(f"/anime/{anime_id}")
                if not qualities:
                    qualities = {"720p": f"{self.base_url}/anime/{anime_id}"}
                episodes.append(Episode(id=f"{anime_id}-1", number=1, title="Episode 1", qualities=qualities))
            
            return Anime(id=anime_id, title=title, synopsis=synopsis, episodes=episodes)
        except Exception as e:
            print(f"Error getting anime {anime_id} from animealpha: {e}")
            return None

    async def _get_qualities_for_episode(self, ep_path: str) -> dict[str, str]:
        """Extracts valid download/stream links from the episode page."""
        qualities_dict = {}
        try:
            url = ep_path if ep_path.startswith("http") else f"{self.base_url}{ep_path}"
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return {}
            
            ep_soup = BeautifulSoup(resp.text, "html.parser")
            
            # Look for any download buttons, quality links, or stream sources
            for a in ep_soup.select("a[href]"):
                href = a.get("href", "")
                text = a.get_text(strip=True).lower()
                
                # Check for download links or resolution identifiers
                if any(q in text or q in href for q in ["360", "480", "720", "1080", "download", "stream"]):
                    full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                    if "1080" in text or "1080" in href:
                        qualities_dict["1080p"] = full_url
                    elif "720" in text or "720" in href:
                        qualities_dict["720p"] = full_url
                    elif "480" in text or "480" in href:
                        qualities_dict["480p"] = full_url
                    elif "360" in text or "360" in href:
                        qualities_dict["360p"] = full_url

            # If specific quality tags aren't explicitly text-labeled, grab general watch/download links
            if not qualities_dict:
                for a in ep_soup.select("a[href*='download'], a[href*='stream'], a[href*='file']"):
                    href = a.get("href", "")
                    full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                    qualities_dict["720p"] = full_url
                    break

            # Absolute fallback to the episode URL itself if nothing else matches
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
        
