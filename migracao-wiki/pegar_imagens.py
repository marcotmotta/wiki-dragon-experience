"""Baixa do Fandom todas as imagens referenciadas por arquivos em content/.

Varre o YAML frontmatter (campo `image:`) e o HTML inline (`src="..."` nas
tags <img> dentro de <figure>). Só baixa o que ainda não existe em
content/attachments/. Idempotente — pode rodar várias vezes.
"""
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path("/Users/inco/mark/wiki-dragon-experience")
CONTENT = REPO / "content"
OUTPUT_LEGADO = CONTENT / "attachments"
OUTPUT_MIGRACAO = REPO / "migracao-wiki" / "images"
OUTPUT = OUTPUT_MIGRACAO  # default; main() ajusta conforme args
OUTPUT.mkdir(parents=True, exist_ok=True)
OUTPUT_LEGADO.mkdir(parents=True, exist_ok=True)

API = "https://dragonexperience.fandom.com/pt-br/api.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Extrai "image: foo.jpg" ou 'image: "foo.jpg"' do frontmatter YAML
FRONTMATTER_IMG = re.compile(r'^image:\s*["\']?([^"\'\n]+?)["\']?\s*$', re.MULTILINE)
# Extrai src das <img src="../attachments/foo.jpg" ...> (formato HTML legado)
BODY_IMG = re.compile(r'src="(?:\.\./)+attachments/([^"]+)"')
# Extrai embeds Obsidian ![[foo.jpg|240]] / ![[foo.png]] — formato que o
# converter.py gera hoje para imagens no corpo. Sem isto, toda imagem citada
# apenas no corpo (não no frontmatter) jamais é baixada.
EMBED_IMG = re.compile(
    r"!\[\[\s*([^\]|#]+?\.(?:png|jpe?g|gif|webp|svg|bmp))\s*(?:[|#][^\]]*)?\]\]",
    re.IGNORECASE,
)


def collect_filenames() -> set[str]:
    names: set[str] = set()
    for md in CONTENT.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        for m in FRONTMATTER_IMG.finditer(text):
            names.add(m.group(1).strip())
        for m in BODY_IMG.finditer(text):
            names.add(m.group(1).strip())
        for m in EMBED_IMG.finditer(text):
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


def list_all_images_api() -> list[dict]:
    """Lista TODAS as imagens da wiki via action=query&list=allimages.

    Retorna lista de dicts {name, url}. Trata paginação via aicontinue.
    """
    images: list[dict] = []
    aicontinue = ""
    while True:
        params = {
            "action": "query",
            "list": "allimages",
            "ailimit": "max",
            "aiprop": "url",
            "format": "json",
            "formatversion": "2",
        }
        if aicontinue:
            params["aicontinue"] = aicontinue
        url = API + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        for img in data.get("query", {}).get("allimages", []):
            images.append({"name": img["name"], "url": img["url"]})
        cont = data.get("continue", {})
        if "aicontinue" not in cont:
            break
        aicontinue = cont["aicontinue"]
    return images


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Baixa TODAS as imagens da wiki Fandom (via allimages API).",
    )
    parser.add_argument(
        "--from-content",
        action="store_true",
        help="Modo legado: baixa só imagens referenciadas em content/ (default).",
    )
    args = parser.parse_args()

    if not args.all and not args.from_content:
        args.from_content = True  # default mantém comportamento antigo

    global OUTPUT
    OUTPUT = OUTPUT_LEGADO if args.from_content else OUTPUT_MIGRACAO

    if args.all:
        print("Listando todas as imagens da Fandom via allimages API …")
        images = list_all_images_api()
        print(f"  {len(images)} imagens encontradas")
        existing = {p.name for p in OUTPUT.iterdir() if p.is_file()}
        missing = [img for img in images if img["name"] not in existing]
        print(f"  Já em images/: {len(images) - len(missing)}")
        print(f"  A baixar: {len(missing)}")
        if not missing:
            return
        ok = 0
        fail: list[str] = []
        for i, img in enumerate(missing, 1):
            dest = OUTPUT / img["name"]
            if download(img["url"], dest):
                ok += 1
                print(f"  [{i}/{len(missing)}] ok {img['name']} ({dest.stat().st_size:,} bytes)")
            else:
                fail.append(img["name"])
                print(f"  [{i}/{len(missing)}] FAILED: {img['name']}")
            time.sleep(0.1)
        print(f"\nBaixadas: {ok} | Falhas: {len(fail)}")
        if fail:
            print("\nFalhas:")
            for f in fail:
                print(f"  - {f}")
        return

    # Modo legado: varre content/
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
