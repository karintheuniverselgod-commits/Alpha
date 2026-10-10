from scrapers.base import CatalogSource
from scrapers.models import Anime, Episode

class DemoCatalogSource(CatalogSource):
    """Metadata-only demo. Replace with a source you are authorized to use."""
    def __init__(self):
        self.items = [Anime("sample-anime", "Sample Anime", "Navigation test only.",
            [Episode("sample-ep-1", 1, "Episode 1"), Episode("sample-ep-2", 2, "Episode 2")])]

    async def search_anime(self, query: str) -> list[Anime]:
        return [a for a in self.items if query.casefold() in a.title.casefold()]

    async def get_anime(self, anime_id: str) -> Anime | None:
        return next((a for a in self.items if a.id == anime_id), None)

    async def get_episode(self, anime_id: str, episode_id: str) -> Episode | None:
        anime = await self.get_anime(anime_id)
        return next((e for e in anime.episodes if e.id == episode_id), None) if anime else None
