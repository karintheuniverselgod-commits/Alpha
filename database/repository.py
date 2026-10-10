from datetime import datetime, timezone
from database.mongo import get_database

async def cache_search(query: str, results: list[dict]) -> None:
    await get_database()["search_cache"].update_one(
        {"_id": query.casefold()},
        {"$set": {"results": results, "updated_at": datetime.now(timezone.utc)}},
        upsert=True)

async def get_cached_search(query: str):
    doc = await get_database()["search_cache"].find_one({"_id": query.casefold()})
    return None if doc is None else doc.get("results", [])
