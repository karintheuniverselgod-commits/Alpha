import asyncio
import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse
import aiohttp
from config import Settings
from services.errors import DownloadError

log = logging.getLogger(__name__)

class DownloadService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        
        # Browser headers to pass Cloudflare / anti-bot verification checks
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://www.animealpha.cc/"
        }
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=settings.download_timeout_seconds)
        )

    async def close(self):
        await self.session.close()

    async def download(self, url: str, anime_id: str, episode_id: str, quality: str) -> Path:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise DownloadError("Only valid HTTPS media URLs are accepted.")
        name = hashlib.sha256(f"{anime_id}:{episode_id}:{quality}".encode()).hexdigest()[:24]
        target = self.settings.download_dir / f"{name}.mp4"
        temp = target.with_suffix(".part")
        limit = self.settings.max_download_mb * 1024 * 1024
        async with self.semaphore:
            try:
                async with self.session.get(url, allow_redirects=True) as response:
                    response.raise_for_status()
                    size = response.headers.get("Content-Length")
                    if size and int(size) > limit:
                        raise DownloadError(f"File exceeds the {self.settings.max_download_mb} MB limit.")
                    total = 0
                    with temp.open("wb") as output:
                        async for chunk in response.content.iter_chunked(262144):
                            total += len(chunk)
                            if total > limit:
                                raise DownloadError(f"File exceeds the {self.settings.max_download_mb} MB limit.")
                            output.write(chunk)
                if not total:
                    raise DownloadError("The source returned an empty file.")
                temp.replace(target)
                return target
            except DownloadError:
                temp.unlink(missing_ok=True)
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as exc:
                temp.unlink(missing_ok=True)
                log.warning("Download failed: %s", exc)
                raise DownloadError("Unable to download this media source. Try again later.") from exc
                
