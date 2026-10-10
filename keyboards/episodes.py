from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from scrapers.models import Anime

def episodes_keyboard(anime: Anime) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=f"E{e.number:02d}",
               callback_data=f"episode:{anime.id}:{e.id}") for e in anime.episodes]
    rows = [buttons[i:i+4] for i in range(0, len(buttons), 4)]
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(
        text="No episodes listed", callback_data="noop")]])
