import asyncio
import hashlib
import logging
from pathlib import Path
from curl_cffi.requests import AsyncSession
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
        temp = target.with_suffix(".part")
        limit = self.settings.max_download_mb * 1024 * 1024

        async with self.semaphore:
            try:
                # Use curl_cffi AsyncSession with Chrome TLS fingerprinting and browser headers
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Referer": "https://www.animealpha.cc/"
                }
                
                async with AsyncSession(impersonate="chrome", headers=headers, timeout=300.0) as client:
                    response = await client.get(url, stream=True, follow_redirects=True)
                    if response.status_code != 200:
                        raise DownloadError(f"Server returned status code {response.status_code}")
                    
                    total = 0
                    with temp.open("wb") as output:
                        async for chunk in response.aiter_content(chunk_size=524288):
                            if chunk:
                                total += len(chunk)
                                if total > limit:
                                    raise DownloadError(f"File exceeds the {self.settings.max_download_mb} MB limit.")
                                output.write(chunk)
                                
                if total < 1000000:  # If file is under 1MB, it's an HTML error page or stub
                    raise DownloadError("The downloaded file is invalid or empty.")
                    
                temp.replace(target)
                return target
            except DownloadError:
                temp.unlink(missing_ok=True)
                raise
            except Exception as exc:
                temp.unlink(missing_ok=True)
                log.warning("Download failed: %s", exc)
                raise DownloadError("Unable to download this media source. Try again later.") from exc
                
