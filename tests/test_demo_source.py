import pytest
from scrapers.demo import DemoCatalogSource

@pytest.mark.asyncio
async def test_demo_catalog():
    source = DemoCatalogSource()
    found = await source.search_anime("sample")
    assert len(found) == 1
    ep = await source.get_episode(found[0].id, "sample-ep-1")
    assert ep is not None
    assert ep.number == 1
