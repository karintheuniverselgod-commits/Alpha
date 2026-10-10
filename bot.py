import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from config import get_settings
from database.mongo import init_mongo, close_mongo
from handlers import register_handlers
from scrapers.factory import build_catalog_source
from services.downloader import DownloadService
from middlewares.throttling import SimpleThrottlingMiddleware

async def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper(),
                        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    session = AiohttpSession()
    if settings.telegram_local_api:
        await session.close()
        session = AiohttpSession(api=TelegramAPIServer.from_base(
            settings.telegram_api_base, is_local=True))
    bot = Bot(token=settings.bot_token, session=session)
    dp = Dispatcher()
    await init_mongo(settings.mongodb_uri, settings.mongodb_database)
    downloader = DownloadService(settings)
    dp["catalog_source"] = build_catalog_source(settings)
    dp["downloader"] = downloader
    dp["settings"] = settings
    dp.message.middleware(SimpleThrottlingMiddleware())
    dp.callback_query.middleware(SimpleThrottlingMiddleware())
    register_handlers(dp)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await downloader.close()
        await close_mongo()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
