"""Baixa do Fandom todas as imagens referenciadas por arquivos em content/.

Varre o YAML frontmatter (campo `image:`) e o HTML inline (`src="..."` nas
tags <img> dentro de <figure>). Só baixa o que ainda não existe em
content/attachments/. Idempotente — pode rodar várias vezes.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path("/Users/inco/mark/wiki-dragon-experience")
CONTENT = REPO / "content"
OUTPUT = CONTENT / "attachments"
OUTPUT.mkdir(parents=True, exist_ok=True)

API = "https://dragonexperience.fandom.com/pt-br/api.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Extrai "image: foo.jpg" ou 'image: "foo.jpg"' do frontmatter YAML
FRONTMATTER_IMG = re.compile(r'^image:\s*["\']?([^"\'\n]+?)["\']?\s*$', re.MULTILINE)
# Extrai src das <img src="../attachments/foo.jpg" ...>
BODY_IMG = re.compile(r'src="(?:\.\./)+attachments/([^"]+)"')


def collect_filenames() -> set[str]:
    names: set[str] = set()
    for md in CONTENT.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        for m in FRONTMATTER_IMG.finditer(text):
            names.add(m.group(1).strip())
        for m in BODY_IMG.finditer(text):
            names.add(m.group(1).strip())
    return names


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
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    info = pages[0].get("imageinfo", [])
    return info[0].get("url") if info else None


def download(url: str, dest: Path) -> bool:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            dest.write_bytes(r.read())
        return True
    except Exception:
        return False


def main() -> None:
    names = collect_filenames()
    print(f"Referências únicas de imagens: {len(names)}")

    existing = {p.name for p in OUTPUT.iterdir() if p.is_file()}
    missing = sorted(names - existing)
    print(f"Já em content/attachments/: {len(names & existing)}")
    print(f"A baixar: {len(missing)}")

    if not missing:
        return

    ok = 0
    fail: list[str] = []
    for i, fname in enumerate(missing, 1):
        url = fetch_url(fname)
        if not url:
            fail.append(fname)
            print(f"  [{i}/{len(missing)}] MISSING: {fname}")
            continue
        dest = OUTPUT / fname
        if download(url, dest):
            ok += 1
            print(f"  [{i}/{len(missing)}] ok {fname} ({dest.stat().st_size:,} bytes)")
        else:
            fail.append(fname)
            print(f"  [{i}/{len(missing)}] FAILED download: {fname}")
        # Ser bom cidadão com a API do Fandom
        time.sleep(0.1)

    print(f"\nBaixadas: {ok} | Falhas: {len(fail)}")
    if fail:
        print("\nAusentes/falhas na Fandom:")
        for f in fail:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
