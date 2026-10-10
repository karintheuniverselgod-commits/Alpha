from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from scrapers.models import Episode

ORDER = ("360p", "480p", "720p", "1080p")

def qualities_keyboard(anime_id: str, episode: Episode) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=q, callback_data=f"quality:{anime_id}:{episode.id}:{q}")
               for q in ORDER if q in episode.qualities]
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    if not buttons:
        rows = [[InlineKeyboardButton(text="No authorized video URL configured",
                                      callback_data="noop")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)
