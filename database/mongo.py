from pymongo import AsyncMongoClient
_client = None
_database = None

async def init_mongo(uri: str, database_name: str) -> None:
    global _client, _database
    _client = AsyncMongoClient(uri, serverSelectionTimeoutMS=5000)
    await _client.admin.command("ping")
    _database = _client[database_name]
    await _database["search_cache"].create_index("expires_at", expireAfterSeconds=0)

async def close_mongo() -> None:
    global _client, _database
    if _client is not None:
        await _client.close()
    _client = _database = None

def get_database():
    if _database is None:
        raise RuntimeError("MongoDB is not initialized")
    return _database
