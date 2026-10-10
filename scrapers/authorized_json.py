import json
import logging
from pathlib import Path

from scrapers.base import CatalogSource
from scrapers.models import Anime, Episode

log = logging.getLogger(__name__)


class AuthorizedJsonCatalogSource(CatalogSource):
    """Serve anime/episode data from a local JSON file of authorized URLs.

    Expected JSON shape:

        {
          "anime": [
            {
              "id": "firefly-wedding",
              "title": "Firefly Wedding",
              "synopsis": "optional",
              "episodes": [
                {
                  "id": "episode-1",
                  "number": 1,
                  "title": "Episode 01",
                  "qualities": {
                    "360p": "https://cdn.example.com/firefly-wedding/01-360.mp4",
                    "720p": "https://cdn.example.com/firefly-wedding/01-720.mp4"
                  }
                }
              ]
            }
          ]
        }
    """

    def __init__(self, json_path: str | Path = "data/authorized.json"):
        self.json_path = Path(json_path)
        self._anime: list[Anime] | None = None

    async def close(self) -> None:
        return None

    def _load(self) -> list[Anime]:
        if self._anime is not None:
            return self._anime

        anime_list = []
        try:
            if not self.json_path.exists():
                log.warning("Authorized JSON not found: %s", self.json_path)
                self._anime = []
                return self._anime

            data = json.loads(self.json_path.read_text(encoding="utf-8"))
            for entry in data.get("anime", []):
                episodes = [
                    Episode(
                        id=str(ep.get("id") or f"episode-{ep.get('number', i)}"),
                        number=int(ep.get("number", i)),
                        title=ep.get("title") or f"Episode {int(ep.get('number', i)):02d}",
                        qualities=dict(ep.get("qualities", {})),
                    )
                    for i, ep in enumerate(entry.get("episodes", []), start=1)
                ]
                episodes.sort(key=lambda ep: ep.number)
                anime_list.append(Anime(
                    id=str(entry["id"]),
                    title=str(entry.get("title") or entry["id"]),
                    synopsis=str(entry.get("synopsis", "")),
                    episodes=episodes,
                ))
        except Exception:
            log.exception("Error loading authorized JSON: %s", self.json_path)
            anime_list = []

        self._anime = anime_list
        return self._anime

    async def search_anime(self, query: str) -> list[Anime]:
        query = query.strip().lower()
        if not query:
            return []
        return [
            anime for anime in self._load()
            if query in anime.title.lower() or query in anime.id.lower()
        ][:20]

    async def get_anime(self, anime_id: str) -> Anime | None:
        for anime in self._load():
            if anime.id == anime_id:
                return anime
        return None

    async def get_episode(self, anime_id: str, episode_id: str) -> Episode | None:
        anime = await self.get_anime(anime_id)
        if not anime:
            return None
        return next((ep for ep in anime.episodes if ep.id == episode_id), None)
