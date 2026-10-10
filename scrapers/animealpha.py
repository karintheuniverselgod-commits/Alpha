import logging
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from scrapers.base import CatalogSource
from scrapers.models import Anime, Episode

log = logging.getLogger(__name__)


class AnimeAlphaCatalogSource(CatalogSource):
    """Scrape anime metadata and direct MP4 links from AnimeAlpha pages."""

    def __init__(self, base_url: str = "https://www.animealpha.cc"):
        self.base_url = base_url.rstrip("/")
        self.client = AsyncSession(impersonate="chrome", timeout=15.0)

    async def close(self) -> None:
        await self.client.close()

    @staticmethod
    def _episode_number(text: str, fallback: int) -> int:
        match = re.search(r"\b(?:episode|ep)\s*[-:#.]?\s*(\d+)\b", text, re.IGNORECASE)
        return int(match.group(1)) if match else fallback

    @staticmethod
    def _direct_mp4_url(url: str) -> bool:
        parsed = urlsplit(url)
        return parsed.scheme == "https" and bool(parsed.netloc) and parsed.path.lower().endswith(".mp4")

    @staticmethod
    def _quality_label(url: str, label: str) -> str:
        text = f"{url} {label}".lower()
        for quality, markers in (
            ("1080p", ("1080", "1920")),
            ("720p", ("720", "1280")),
            ("480p", ("480", "854")),
            ("360p", ("360", "640")),
        ):
            if any(marker in text for marker in markers):
                return quality
        return "360p"

    async def search_anime(self, query: str) -> list[Anime]:
        try:
            search_url = f"{self.base_url}/search"
            for parameter in ("q", "keyword"):
                response = await self.client.get(search_url, params={parameter: query})
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                results = []
                seen = set()

                for a_tag in soup.select("a[href]"):
                    href = a_tag.get("href", "").strip()
                    full_url = urljoin(str(response.url), href)
                    path_parts = [part for part in urlsplit(full_url).path.split("/") if part]
                    if len(path_parts) < 2 or path_parts[-2] != "anime":
                        continue

                    anime_id = path_parts[-1]
                    if not anime_id or anime_id in seen:
                        continue
                    seen.add(anime_id)

                    title_elem = a_tag.select_one(".title, h2, h3, h4, strong")
                    if title_elem:
                        title = title_elem.get_text(" ", strip=True)
                    else:
                        title = a_tag.get("title", "").strip()
                    if not title:
                        image = a_tag.select_one("img[alt]")
                        title = image.get("alt", "").strip() if image else ""
                    if not title:
                        title = a_tag.get_text(" ", strip=True)
                    if not title:
                        title = anime_id.replace("-", " ").title()

                    results.append(Anime(id=anime_id, title=title))

                if results:
                    return results[:20]

            return []
        except Exception:
            log.exception("Error searching AnimeAlpha")
            return []

    async def get_anime(self, anime_id: str) -> Anime | None:
        try:
            anime_url = f"{self.base_url}/anime/{anime_id}"
            response = await self.client.get(anime_url)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            title_elem = soup.select_one("main h1, h1, .anime-title")
            title = title_elem.get_text(" ", strip=True) if title_elem else anime_id.replace("-", " ").title()

            synopsis_elem = soup.select_one(".synopsis, .description, p")
            synopsis = synopsis_elem.get_text(" ", strip=True) if synopsis_elem else ""

            episodes = []
            episode_links = soup.select("a[href*='/episodes/'], a[href*='/watch/'], a[href*='/episode/']")

            seen_eps = set()
            for idx, ep_link in enumerate(episode_links, start=1):
                ep_href = ep_link.get("href", "").strip()
                if not ep_href:
                    continue

                ep_url = urljoin(str(response.url or anime_url), ep_href)
                if ep_url in seen_eps:
                    continue
                seen_eps.add(ep_url)

                ep_id = urlsplit(ep_url).path.rstrip("/").split("/")[-1]
                if not ep_id:
                    continue
                ep_title = ep_link.get_text(" ", strip=True) or f"Episode {idx}"
                number = self._episode_number(f"{ep_title} {ep_url}", idx)

                qualities = await self._get_qualities_for_episode(ep_url)
                if qualities:
                    episodes.append(Episode(
                        id=ep_id,
                        number=number,
                        title=ep_title,
                        qualities=qualities,
                    ))

            # Do not fabricate an episode pointing at the anime page. A page URL
            # returns HTML, not a downloadable video.
            return Anime(id=anime_id, title=title, synopsis=synopsis, episodes=episodes)
        except Exception:
            log.exception("Error getting AnimeAlpha anime %s", anime_id)
            return None

    async def _get_qualities_for_episode(self, ep_path: str) -> dict[str, str]:
        """Return only HTTPS MP4 file URLs supported by the current downloader."""
        qualities = {}
        try:
            url = urljoin(f"{self.base_url}/", ep_path)
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return {}

            soup = BeautifulSoup(resp.text, "html.parser")
            for element in soup.select("a[href], source[src], video[src]"):
                candidate = (element.get("href") or element.get("src") or "").strip()
                if not candidate:
                    continue

                media_url = urljoin(str(resp.url or url), candidate)
                if not self._direct_mp4_url(media_url):
                    continue

                label = " ".join((
                    element.get_text(" ", strip=True),
                    element.get("title", ""),
                    element.get("label", ""),
                ))
                quality = self._quality_label(media_url, label)
                qualities.setdefault(quality, media_url)

            # Player iframes and .m3u8 manifests are intentionally not returned:
            # neither is an MP4 file, and saving either as .mp4 creates a tiny
            # invalid "video" instead of a real download.
            return qualities
        except Exception:
            log.exception("Error fetching AnimeAlpha episode sources: %s", ep_path)
            return {}

    async def get_episode(self, anime_id: str, episode_id: str) -> Episode | None:
        anime = await self.get_anime(anime_id)
        if not anime:
            return None
        return next((episode for episode in anime.episodes if episode.id == episode_id), None)
          
