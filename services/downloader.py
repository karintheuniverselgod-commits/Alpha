import asyncio
import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import aiohttp

from config import Settings
from services.errors import DownloadError

log = logging.getLogger(__name__)

# Browser-like headers: many anime CDNs reject the aiohttp default
# User-Agent ("aiohttp/3.x") or serve an empty body without a Referer.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}


class DownloadService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        # Create the session lazily from inside the running event loop.
        self.session = None

    def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(
                    total=self.settings.download_timeout_seconds
                )
            )
        return self.session

    async def close(self):
        if self.session is not None and not self.session.closed:
            await self.session.close()
        self.session = None

    async def download(
        self,
        url: str,
        anime_id: str,
        episode_id: str,
        quality: str,
        referer: str | None = None,
    ) -> Path:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise DownloadError("Only valid HTTPS media URLs are accepted.")

        name = hashlib.sha256(f"{anime_id}:{episode_id}:{quality}".encode()).hexdigest()[:24]
        target = self.settings.download_dir / f"{name}.mp4"
        # Unique partial paths prevent simultaneous requests for the same episode
        # from writing to or deleting each other's in-progress file.
        temp = target.with_name(f"{target.stem}.{uuid4().hex}.part")
        limit = self.settings.max_download_mb * 1024 * 1024

        headers = dict(DEFAULT_HEADERS)
        # A per-episode Referer can be passed by the caller; otherwise fall
        # back to a global one from settings (e.g. settings.download_referer).
        referer = referer or getattr(self.settings, "download_referer", None)
        if referer:
            headers["Referer"] = referer

        total = 0
        prefix = bytearray()

        async with self.semaphore:
            try:
                self.settings.download_dir.mkdir(parents=True, exist_ok=True)
                async with self._get_session().get(
                    url, headers=headers, allow_redirects=True
                ) as response:
                    log.info(
                        "download start: %s -> status=%s type=%s length=%s",
                        url, response.status_code,
                        response.headers.get("Content-Type"),
                        response.headers.get("Content-Length"),
                    )
                    response.raise_for_status()
                    if response.url.scheme != "https":
                        raise DownloadError("The media source redirected to an insecure URL.")

                    size = response.headers.get("Content-Length")
                    if size:
                        try:
                            if int(size) > limit:
                                raise DownloadError(
                                    f"File exceeds the {self.settings.max_download_mb} MB limit."
                                )
                        except ValueError:
                            # Non-numeric Content-Length (chunked/unknown): the
                            # streaming check below still enforces the limit.
                            pass

                    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                    # Reject any textual type outright, not just HTML — error
                    # pages are often served as text/plain with status 200.
                    if content_type.startswith("text/") or content_type in {
                        "application/xhtml+xml", "application/xml", "application/json"
                    }:
                        raise DownloadError("The source returned a web page instead of a media file.")

                    with temp.open("wb") as output:
                        async for chunk in response.content.iter_chunked(262144):
                            total += len(chunk)
                            if total > limit:
                                raise DownloadError(
                                    f"File exceeds the {self.settings.max_download_mb} MB limit."
                                )
                            if len(prefix) < 1024:
                                prefix.extend(chunk[:1024 - len(prefix)])
                            output.write(chunk)

                if not total:
                    raise DownloadError("The source returned an empty file.")
                if bytes(prefix).lstrip().lower().startswith(
                    (b"<!doctype html", b"<html", b"<head", b"<body", b"<script")
                ):
                    raise DownloadError("The source returned a web page instead of a media file.")
                # Every real MP4 starts with a box whose type is "ftyp"
                # (bytes 4-8). This catches error pages served with a
                # video/* or octet-stream content type.
                if len(prefix) >= 8 and prefix[4:8] != b"ftyp":
                    log.warning(
                        "download: %s first bytes %r do not look like MP4",
                        url, bytes(prefix[:16]),
                    )

                temp.replace(target)
                return target
            except asyncio.CancelledError:
                temp.unlink(missing_ok=True)
                raise
            except DownloadError:
                temp.unlink(missing_ok=True)
                raise
            except Exception as exc:
                temp.unlink(missing_ok=True)
                log.warning("Download failed: %s", exc)
                raise DownloadError("Unable to download this media source. Try again later.") from exc
