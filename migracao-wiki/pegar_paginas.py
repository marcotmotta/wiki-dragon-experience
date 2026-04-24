"""Baixa todas as páginas do namespace principal (ns=0) da Fandom e
regenera migracao-wiki/dump.xml num formato compatível com converter.py.

Processo:
  1. Lista todas as páginas via action=query&list=allpages
  2. Em lotes de 50 títulos, baixa o wikitext via action=query&prop=revisions
  3. Serializa em XML no mesmo schema que a export oficial do MediaWiki
     usa (export-0.11) — é o que o converter.py parseia.

Idempotente: salva backup como dump.xml.bak-YYYYMMDD-HHMMSS antes de sobrescrever.
"""
import datetime as dt
import json
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

REPO = Path("/Users/inco/mark/wiki-dragon-experience")
DUMP = REPO / "migracao-wiki" / "dump.xml"
API = "https://dragonexperience.fandom.com/pt-br/api.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}
BATCH_SIZE = 50
NAMESPACE = 0


def api_get(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def list_all_titles() -> list[str]:
    titles: list[str] = []
    apcontinue = ""
    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "aplimit": "max",
            "apnamespace": NAMESPACE,
            "format": "json",
            "formatversion": "2",
        }
        if apcontinue:
            params["apcontinue"] = apcontinue
        data = api_get(params)
        for p in data.get("query", {}).get("allpages", []):
            titles.append(p["title"])
        cont = data.get("continue", {})
        if "apcontinue" not in cont:
            break
        apcontinue = cont["apcontinue"]
    return titles


def fetch_pages_batch(titles: list[str]) -> list[dict]:
    """Devolve lista de {title, ns, text} pras páginas dadas (até 50 por chamada)."""
    params = {
        "action": "query",
        "titles": "|".join(titles),
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
        "formatversion": "2",
    }
    data = api_get(params)
    out = []
    for p in data.get("query", {}).get("pages", []):
        if p.get("missing"):
            continue
        revs = p.get("revisions", [])
        if not revs:
            continue
        main = revs[0].get("slots", {}).get("main", {})
        text = main.get("content", "")
        out.append({
            "title": p["title"],
            "ns": p.get("ns", 0),
            "text": text,
        })
    return out


def build_xml(pages: list[dict]) -> str:
    """Constrói XML mimetizando o formato export-0.11 do MediaWiki."""
    lines = [
        '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://www.mediawiki.org/xml/export-0.11/ '
        'http://www.mediawiki.org/xml/export-0.11.xsd" version="0.11" xml:lang="pt-br">',
    ]
    for p in pages:
        lines.append("  <page>")
        lines.append(f"    <title>{xml_escape(p['title'])}</title>")
        lines.append(f"    <ns>{p['ns']}</ns>")
        lines.append("    <revision>")
        lines.append(f'      <text xml:space="preserve" bytes="{len(p["text"])}">'
                     f'{xml_escape(p["text"])}</text>')
        lines.append("    </revision>")
        lines.append("  </page>")
    lines.append("</mediawiki>")
    return "\n".join(lines)


def main() -> None:
    print("1/3  Listando todas as páginas em ns=0 …")
    titles = list_all_titles()
    print(f"     {len(titles)} títulos encontrados")

    print("2/3  Baixando wikitext (lotes de 50) …")
    pages: list[dict] = []
    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i : i + BATCH_SIZE]
        pages.extend(fetch_pages_batch(batch))
        print(f"     {min(i + BATCH_SIZE, len(titles)):>4}/{len(titles)}")
        time.sleep(0.15)  # bom cidadão com a API
    print(f"     {len(pages)} páginas com conteúdo")

    print("3/3  Escrevendo dump.xml …")
    if DUMP.exists():
        ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = DUMP.with_name(f"dump.xml.bak-{ts}")
        shutil.copy2(DUMP, backup)
        print(f"     backup: {backup.name}")
    DUMP.write_text(build_xml(pages), encoding="utf-8")
    print(f"     {DUMP.name} atualizado ({DUMP.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
