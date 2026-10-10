from abc import ABC, abstractmethod
from scrapers.models import Anime, Episode

class CatalogSource(ABC):
    @abstractmethod
    async def search_anime(self, query: str) -> list[Anime]: ...
    @abstractmethod
    async def get_anime(self, anime_id: str) -> Anime | None: ...
    @abstractmethod
    async def get_episode(self, anime_id: str, episode_id: str) -> Episode | None: ...
