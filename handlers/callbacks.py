import logging
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile
from keyboards.episodes import episodes_keyboard
from keyboards.qualities import qualities_keyboard
from services.errors import DownloadError

router = Router()
log = logging.getLogger(__name__)

@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer("No media is configured for this option.", show_alert=True)

@router.callback_query(F.data.startswith("anime:"))
async def choose_anime(callback: CallbackQuery, catalog_source):
    anime_id = callback.data.split(":", 1)[1]
    anime = await catalog_source.get_anime(anime_id)
    if not anime:
        await callback.answer("Anime not found.", show_alert=True)
        return
    await callback.message.edit_text(f"{anime.title}\\nChoose an episode:",
                                     reply_markup=episodes_keyboard(anime))
    await callback.answer()

@router.callback_query(F.data.startswith("episode:"))
async def choose_episode(callback: CallbackQuery, catalog_source):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Invalid selection.", show_alert=True)
        return
    _, anime_id, episode_id = parts
    anime = await catalog_source.get_anime(anime_id)
    episode = await catalog_source.get_episode(anime_id, episode_id)
    if not anime or not episode:
        await callback.answer("Episode not found.", show_alert=True)
        return
    await callback.message.edit_text(
        f"{anime.title} — Episode {episode.number}\\n{episode.title}\\nChoose quality:",
        reply_markup=qualities_keyboard(anime_id, episode))
    await callback.answer()

@router.callback_query(F.data.startswith("quality:"))
async def choose_quality(callback: CallbackQuery, catalog_source, downloader):
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("Invalid selection.", show_alert=True)
        return
    _, anime_id, episode_id, quality = parts
    episode = await catalog_source.get_episode(anime_id, episode_id)
    if not episode or quality not in episode.qualities:
        await callback.answer("Quality unavailable.", show_alert=True)
        return
    await callback.answer("Preparing video…")
    status = await callback.message.answer(f"Preparing episode {episode.number} ({quality})…")
    try:
        path = await downloader.download(episode.qualities[quality], anime_id, episode_id, quality)
        await callback.message.answer_video(FSInputFile(path),
            caption=f"{episode.title} · {quality}", supports_streaming=True)
        await status.delete()
    except DownloadError as exc:
        await status.edit_text(str(exc))
    except TelegramBadRequest:
        log.exception("Telegram rejected video upload")
        await status.edit_text("Telegram rejected this upload. Check file size and Bot API setup.")
    except Exception:
        log.exception("Episode delivery failed")
        await status.edit_text("Unexpected error sending the episode.")
