import logging
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from scrapers.base import CatalogSource
from scrapers.models import Anime, Episode

log = logging.getLogger(__name__)

# "Episode 12", "EP 12", "Ep.12", "Episode: 12", etc.
EPISODE_NUMBER_RE = re.compile(r"(?:episode|ep)\s*[-:#.]?\s*0*(\d+)", re.IGNORECASE)
# AnimeAlpha episode pages: /episodes/<anime-slug>/<number>/<quality-label>
# e.g. /episodes/firefly-wedding/1/640%20x%20360  -> number 1
EPISODE_PAGE_RE = re.compile(r"/episodes/[^/?#]+/(\d+)(?:/|$)")
# Direct download endpoints on the episode page carry signed tokens:
# /download/<slug>/<number>/<filename>.mkv?token=...
DOWNLOAD_PATH_RE = re.compile(r"/download/[^?#]+\.(mp4|mkv)", re.IGNORECASE)


class AnimeAlphaCatalogSource(CatalogSource):
    """Scrape anime metadata and direct media links from AnimeAlpha pages."""

    def __init__(self, base_url: str = "https://www.animealpha.cc"):
        self.base_url = base_url.rstrip("/")
        self.client = AsyncSession(impersonate="chrome", timeout=15.0)

    async def close(self) -> None:
        await self.client.close()

    @staticmethod
    def _episode_number_from_url(url: str) -> int | None:
        match = EPISODE_PAGE_RE.search(urlsplit(url).path)
        return int(match.group(1)) if match else None

    @staticmethod
    def _episode_number(text: str, fallback: int) -> int:
        match = EPISODE_NUMBER_RE.search(text)
        return int(match.group(1)) if match else fallback

    @staticmethod
    def _direct_media_url(url: str) -> bool:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and bool(parsed.netloc)
            and DOWNLOAD_PATH_RE.search(parsed.path) is not None
        )

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

    async def _latest_episode_from_home(self, anime_id: str) -> int | None:
        """Use the site's Latest Episodes cards when the anime page omits its list."""
        try:
            home_url = f"{self.base_url}/"
            response = await self.client.get(home_url)
            log.info("home page: status=%s bytes=%s", response.status_code, len(response.text))
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            anime_path = f"/anime/{anime_id}"
            for link in soup.select("a[href]"):
                link_url = urljoin(str(response.url or home_url), link.get("href", ""))
                if urlsplit(link_url).path.rstrip("/") != anime_path:
                    continue

                # The episode label often sits beside the anime link in the
                # enclosing Latest Episodes card, not inside the link itself.
                for container in link.parents:
                    if getattr(container, "name", None) in {"html", "body", "[document]"}:
                        continue
                    card_text = container.get_text(" ", strip=True)
                    numbers = [int(value) for value in EPISODE_NUMBER_RE.findall(card_text)]
                    if not numbers:
                        continue

                    anime_links = {
                        urlsplit(urljoin(str(response.url or home_url), item.get("href", ""))).path.rstrip("/")
                        for item in container.select("a[href]")
                        if "/anime/" in item.get("href", "")
                    }
                    if anime_links and anime_links.issubset({anime_path}):
                        return max(numbers)
                    # Parents only grow from here; once a card that contains
                    # the episode number also contains other anime links, no
                    # larger ancestor will pass the subset check either.
                    break

            return None
        except Exception:
            log.exception("Error checking AnimeAlpha latest episodes for %s", anime_id)
            return None

    async def search_anime(self, query: str) -> list[Anime]:
        try:
            search_url = f"{self.base_url}/search"
            for parameter in ("q", "keyword"):
                response = await self.client.get(search_url, params={parameter: query})
                if response.status_code != 200:
                    log.info("search %s=%r: status=%s bytes=%s",
                             parameter, query, response.status_code, len(response.text))
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
            log.info("anime page %s: status=%s bytes=%s",
                     anime_id, response.status_code, len(response.text))
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            title_elem = soup.select_one("main h1, h1, .anime-title")
            title = title_elem.get_text(" ", strip=True) if title_elem else anime_id.replace("-", " ").title()

            synopsis_elem = soup.select_one(".synopsis, .description, p")
            synopsis = synopsis_elem.get_text(" ", strip=True) if synopsis_elem else ""

            # Collect per-quality episode pages: /episodes/<slug>/<n>/<quality>
            quality_pages: dict[int, dict[str, str]] = {}
            for a_tag in soup.select("a[href]"):
                href = a_tag.get("href", "").strip()
                if "/episodes/" not in href:
                    continue
                page_url = urljoin(str(response.url or anime_url), href)
                number = self._episode_number_from_url(page_url)
                if number is None:
                    continue
                label = a_tag.get_text(" ", strip=True)  # e.g. "640 x 360"
                by_quality = quality_pages.setdefault(number, {})
                quality = self._quality_label(page_url, label)
                by_quality.setdefault(quality, page_url)

            page_cache: dict[str, dict[str, str]] = {}

            async def download_links_for(page_url: str) -> dict[str, str]:
                if page_url not in page_cache:
                    page_cache[page_url] = await self._get_download_links(page_url)
                return page_cache[page_url]

            episodes = []
            for number in sorted(quality_pages):
                qualities: dict[str, str] = {}
                for quality, page_url in sorted(quality_pages[number].items()):
                    for q, media_url in (await download_links_for(page_url)).items():
                        qualities.setdefault(q, media_url)

                episodes.append(Episode(
                    id=f"episode-{number}",
                    number=number,
                    title=f"Episode {number:02d}",
                    qualities=qualities,
                ))

            if not episodes:
                latest_number = await self._latest_episode_from_home(anime_id)
                if latest_number is not None:
                    # This is a published-episode listing only. The homepage
                    # card has no direct video URL, so leave qualities empty.
                    episodes.append(Episode(
                        id=f"{anime_id}-episode-{latest_number}",
                        number=latest_number,
                        title=f"Episode {latest_number:02d}",
                        qualities={},
                    ))

            return Anime(id=anime_id, title=title, synopsis=synopsis, episodes=episodes)
        except Exception:
            log.exception("Error getting AnimeAlpha anime %s", anime_id)
            return None

    async def _get_download_links(self, page_url: str) -> dict[str, str]:
        """Fetch one /episodes/<slug>/<n>/<quality> page and extract the
        signed /download/... media link(s) from it."""
        qualities: dict[str, str] = {}
        try:
            resp = await self.client.get(page_url)
            log.info("episode page %s: status=%s bytes=%s",
                     page_url, resp.status_code, len(resp.text))
            if resp.status_code != 200:
                return {}

            soup = BeautifulSoup(resp.text, "html.parser")
            for element in soup.select("a[href]"):
                href = (element.get("href") or "").strip()
                if not href:
                    continue
                media_url = urljoin(str(resp.url or page_url), href)
                if not self._direct_media_url(media_url):
                    continue
                label = " ".join((
                    element.get_text(" ", strip=True),
                    element.get("title", ""),
                ))
                quality = self._quality_label(media_url, label)
                qualities.setdefault(quality, media_url)

            return qualities
        except Exception:
            log.exception("Error fetching AnimeAlpha episode sources: %s", page_url)
            return {}

    async def get_episode(self, anime_id: str, episode_id: str) -> Episode | None:
        anime = await self.get_anime(anime_id)
        if not anime:
            return None
        return next((episode for episode in anime.episodes if episode.id == episode_id), None)
