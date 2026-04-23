"""Baixa apenas as imagens referenciadas pelas 4 páginas do demo."""
import json
import os
import urllib.request
import urllib.parse
from pathlib import Path

API = "https://dragonexperience.fandom.com/pt-br/api.php"
OUTPUT = Path("/Users/inco/mark/wiki-dragon-experience/content/attachments")
OUTPUT.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

IMAGES = ["Daniel.jpg", "Daniel2.jpg", "Eryn.jpg"]


def fetch_url(filename: str) -> str | None:
    """Pergunta à API do Fandom qual a URL real do arquivo."""
    params = {
        "action": "query",
        "titles": f"Arquivo:{filename}",
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
        "formatversion": "2",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    info = pages[0].get("imageinfo", [])
    return info[0].get("url") if info else None


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        dest.write_bytes(r.read())


def main():
    for fname in IMAGES:
        dest = OUTPUT / fname
        if dest.exists():
            print(f"  (já existe) {fname}")
            continue
        url = fetch_url(fname)
        if not url:
            print(f"  [MISSING] {fname}")
            continue
        download(url, dest)
        size = dest.stat().st_size
        print(f"  ok {fname} ({size:,} bytes) ← {url}")


if __name__ == "__main__":
    main()
