import asyncio
import hashlib
import logging
from pathlib import Path
import yt_dlp
from config import Settings
from services.errors import DownloadError

log = logging.getLogger(__name__)

class DownloadService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)

    async def close(self):
        pass

    async def download(self, url: str, anime_id: str, episode_id: str, quality: str) -> Path:
        name = hashlib.sha256(f"{anime_id}:{episode_id}:{quality}".encode()).hexdigest()[:24]
        target = self.settings.download_dir / f"{name}.mp4"
        limit = self.settings.max_download_mb * 1024 * 1024

        async with self.semaphore:
            loop = asyncio.get_running_loop()
            
            def _download_sync():
                ydl_opts = {
                    'outtmpl': str(target.with_suffix('')),
                    'format': 'bestvideo+bestaudio/best',
                    'max_filesize': limit,
                    'quiet': True,
                    'no_warnings': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    p = Path(filename)
                    if not p.exists():
                        matches = list(target.parent.glob(f"{name}*"))
                        if matches:
                            p = matches[0]
                    return p

            try:
                downloaded_path = await loop.run_in_executor(None, _download_sync)
                if not downloaded_path.exists() or downloaded_path.stat().st_size < 1000:
                    raise DownloadError("The downloaded file is empty or invalid.")
                
                if downloaded_path != target:
                    if target.exists():
                        target.unlink()
                    downloaded_path.rename(target)
                
                return target
            except Exception as exc:
                log.warning("Download failed via yt-dlp: %s", exc)
                if target.exists():
                    target.unlink(missing_ok=True)
                raise DownloadError("Unable to download this media source. Try again later.") from exc
                
