"""One-off diagnostic: dump what AnimeAlpha pages actually contain.

Run from the project venv:
    python diagnose.py > diag.txt
Then open diag.txt and paste its contents.
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi.requests import Session

BASE = "https://www.animealpha.cc"
ANIME_ID = "firefly-wedding"  # change if testing another title

client = Session(impersonate="chrome", timeout=15.0)


def dump(url: str) -> None:
    print("=" * 72)
    print("URL:", url)
    resp = client.get(url)
    print("status:", resp.status_code, "bytes:", len(resp.text))
    soup = BeautifulSoup(resp.text, "html.parser")

    print("\n--- all <a> links (first 40) ---")
    for a in soup.select("a[href]")[:40]:
        print(repr(a.get("href")), "|", a.get_text(" ", strip=True)[:60])

    print("\n--- iframes ---")
    for tag in soup.select("iframe[src]"):
        print(tag.get("src"))

    print("\n--- video/source tags ---")
    for tag in soup.select("video, source"):
        print(tag.name, dict(tag.attrs))

    print("\n--- raw .mp4 / .m3u8 occurrences in HTML ---")
    for m in sorted(set(re.findall(r"https?://[^\"'\s]+\.(?:mp4|m3u8)", resp.text))):
        print(m)

    print("\n--- script srcs (players often load via JS) ---")
    for tag in soup.select("script[src]"):
        print(tag.get("src"))

    # Follow the first episode-ish link found, then dump that page too.
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if re.search(r"(?:watch|episode|ep)", href, re.I):
            dump(urljoin(str(resp.url), href))
            return


dump(f"{BASE}/anime/{ANIME_ID}")
client.close()
