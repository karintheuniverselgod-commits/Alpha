from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from scrapers.models import Anime

def anime_results_keyboard(items: list[Anime]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=a.title[:60], callback_data=f"anime:{a.id}")]
        for a in items[:20]])
