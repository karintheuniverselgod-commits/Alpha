from aiogram import Dispatcher
from handlers.start import router as start_router
from handlers.search import router as search_router
from handlers.callbacks import router as callbacks_router

def register_handlers(dp: Dispatcher) -> None:
    dp.include_router(start_router)
    dp.include_router(search_router)
    dp.include_router(callbacks_router)
