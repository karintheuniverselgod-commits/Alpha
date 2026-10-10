from config import Settings
from scrapers.demo import DemoCatalogSource
from scrapers.authorized_json import AuthorizedJsonCatalogSource
from scrapers.animealpha import AnimeAlphaCatalogSource

def build_catalog_source(settings: Settings):
    if settings.catalog_source == "animealpha":
        return AnimeAlphaCatalogSource()
    if settings.catalog_source == "authorized_json":
        return AuthorizedJsonCatalogSource(settings.authorized_catalog_json)
    return DemoCatalogSource()
    
