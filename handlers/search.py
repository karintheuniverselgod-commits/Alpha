from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from keyboards.anime import anime_results_keyboard

router = Router()

@router.message(Command("search"))
async def search(message: Message, catalog_source):
    query = (message.text or "").partition(" ")[2].strip()
    if not query:
        await message.answer("Usage: /search anime name")
        return
    results = await catalog_source.search_anime(query)
    if not results:
        await message.answer("No matching anime found.")
        return
    await message.answer(f"Results for {query}:", reply_markup=anime_results_keyboard(results))
