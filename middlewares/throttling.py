import time
from collections import defaultdict
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

class SimpleThrottlingMiddleware(BaseMiddleware):
    def __init__(self, interval_seconds: float = 0.7):
        self.interval = interval_seconds
        self.last_seen = defaultdict(float)

    async def __call__(self, handler, event, data):
        user = event.from_user
        if user:
            now = time.monotonic()
            if now - self.last_seen[user.id] < self.interval:
                if isinstance(event, Message):
                    await event.answer("Please wait a moment.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("Please wait a moment.")
                return
            self.last_seen[user.id] = now
        return await handler(event, data)
