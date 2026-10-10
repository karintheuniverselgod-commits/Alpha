import json
from pathlib import Path
from scrapers.base import CatalogSource
from scrapers.models import Anime, Episode

class AuthorizedJsonCatalogSource(CatalogSource):
    """Loads a JSON catalog of metadata and direct URLs for authorized media."""
    def __init__(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Catalog missing: {path}. See README.md.")
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.items = []
        for item in raw.get("anime", []):
            eps = []
            for ep in item.get("episodes", []):
                qualities = {str(k): str(v) for k, v in ep.get("qualities", {}).items()
                    if k in {"360p", "480p", "720p", "1080p"} and str(v).startswith("https://")}
                eps.append(Episode(str(ep["id"]), int(ep["number"]),
                                   str(ep.get("title", f"Episode {ep['number']}")), qualities))
            self.items.append(Anime(str(item["id"]), str(item["title"]),
                                    str(item.get("synopsis", "")), eps))

    async def search_anime(self, query: str) -> list[Anime]:
        return [a for a in self.items if query.casefold() in a.title.casefold()][:20]

    async def get_anime(self, anime_id: str) -> Anime | None:
        return next((a for a in self.items if a.id == anime_id), None)

    async def get_episode(self, anime_id: str, episode_id: str) -> Episode | None:
        anime = await self.get_anime(anime_id)
        return next((e for e in anime.episodes if e.id == episode_id), None) if anime else None
