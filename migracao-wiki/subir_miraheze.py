"""Sobe páginas e imagens pro Miraheze a partir de dump.xml + images/.

Pré-condição: variáveis de ambiente MIRAHEZE_BOT_USER e MIRAHEZE_BOT_PASS
setadas (criar em https://dragonexperience.miraheze.org/wiki/Special:BotPasswords).
Modo padrão é --dry-run; passe --apply para realmente subir.
"""
import argparse
import http.cookiejar
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


REPO = Path("/Users/inco/mark/wiki-dragon-experience")
DUMP = REPO / "migracao-wiki" / "dump.xml"
IMAGES_DIR = REPO / "migracao-wiki" / "images"
LOG_FILE = REPO / "migracao-wiki" / "migracao.log"

API = "https://dragonexperience.miraheze.org/w/api.php"

# Ordem importa: templates antes de páginas que os usam.
NAMESPACE_ORDER = [10, 14, 0, 6]

# Sleeps entre operações (rate limit polite).
SLEEP_EDIT = 0.5
SLEEP_UPLOAD = 1.0


def log_linha(linha: str) -> None:
    """Append-only para migracao.log + print stdout."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {linha}\n")
    print(linha)


def com_retry(fn, *args, max_retries: int = 5, **kwargs):
    """Retry com backoff exponencial em caso de ratelimited ou rede."""
    delay = 0.5
    for tentativa in range(1, max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except RuntimeError as e:
            msg = str(e).lower()
            if "ratelimited" in msg or "ratelimit" in msg:
                log_linha(f"  [RETRY {tentativa}/{max_retries}] rate-limited; sleep {delay}s")
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            log_linha(f"  [RETRY {tentativa}/{max_retries}] erro de rede: {e}; sleep 2s")
            time.sleep(2)
    raise RuntimeError(f"Falhou após {max_retries} retries.")


class MirahezeClient:
    """Cliente para api.php do Miraheze. Modelado em FandomClient (aplicar_paleta.py)."""

    def __init__(self, api: str, user: str, pwd: str) -> None:
        self.api = api
        self.user = user
        self.pwd = pwd
        cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookies)
        )
        self.opener.addheaders = [("User-Agent", "DragonExp-MigracaoBot/1.0")]
        self.csrf_token: str | None = None

    def _post(self, params: dict[str, str]) -> dict:
        data = urllib.parse.urlencode(params).encode("utf-8")
        with self.opener.open(self.api, data=data, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))

    def _get(self, params: dict[str, str]) -> dict:
        url = self.api + "?" + urllib.parse.urlencode(params)
        with self.opener.open(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def login(self) -> None:
        r = self._get(
            {"action": "query", "meta": "tokens", "type": "login", "format": "json"}
        )
        login_token = r["query"]["tokens"]["logintoken"]
        r = self._post(
            {
                "action": "login",
                "lgname": self.user,
                "lgpassword": self.pwd,
                "lgtoken": login_token,
                "format": "json",
            }
        )
        if r.get("login", {}).get("result") != "Success":
            raise RuntimeError(f"Login falhou: {r}")
        r = self._get({"action": "query", "meta": "tokens", "format": "json"})
        self.csrf_token = r["query"]["tokens"]["csrftoken"]
        if not self.csrf_token or self.csrf_token == "+\\":
            raise RuntimeError("CSRF token vazio.")

    def get_wikitext(self, title: str) -> str | None:
        r = self._get(
            {
                "action": "query",
                "prop": "revisions",
                "titles": title,
                "rvprop": "content",
                "rvslots": "main",
                "format": "json",
                "formatversion": "2",
            }
        )
        pages = r["query"]["pages"]
        if not pages or pages[0].get("missing"):
            return None
        revs = pages[0].get("revisions", [])
        if not revs:
            return None
        return revs[0]["slots"]["main"]["content"]

    def edit(self, title: str, text: str, summary: str) -> dict:
        if self.csrf_token is None:
            raise RuntimeError("Chame login() antes de edit().")
        r = self._post(
            {
                "action": "edit",
                "title": title,
                "text": text,
                "summary": summary,
                "token": self.csrf_token,
                "bot": "1",
                "format": "json",
            }
        )
        if "error" in r:
            raise RuntimeError(f"Edit em {title!r} falhou: {r['error']}")
        return r

    def upload(self, filename: str, file_path: Path, comment: str) -> dict:
        """Upload de arquivo via multipart/form-data (sem requests, só urllib)."""
        if self.csrf_token is None:
            raise RuntimeError("Chame login() antes de upload().")

        boundary = "----DragonExpMigracao" + os.urandom(8).hex()
        content_type = f"multipart/form-data; boundary={boundary}"

        body_parts: list[bytes] = []
        fields = {
            "action": "upload",
            "filename": filename,
            "comment": comment,
            "token": self.csrf_token,
            "ignorewarnings": "1",
            "format": "json",
        }
        for k, v in fields.items():
            body_parts.append(f"--{boundary}\r\n".encode())
            body_parts.append(
                f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode()
            )
            body_parts.append(v.encode("utf-8"))
            body_parts.append(b"\r\n")
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
        )
        body_parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
        body_parts.append(file_path.read_bytes())
        body_parts.append(f"\r\n--{boundary}--\r\n".encode())
        body = b"".join(body_parts)

        req = urllib.request.Request(self.api, data=body)
        req.add_header("Content-Type", content_type)
        req.add_header("User-Agent", "DragonExp-MigracaoBot/1.0")
        with self.opener.open(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
        if "error" in data:
            raise RuntimeError(f"Upload de {filename!r} falhou: {data['error']}")
        return data


def paginas_do_dump(path: Path) -> list[dict]:
    """Parsa o dump.xml e devolve lista de {title, ns, text}.

    Lê o XML em streaming para tolerar arquivos grandes. Schema esperado:
    formato export-0.11 do MediaWiki.
    """
    NS = "{http://www.mediawiki.org/xml/export-0.11/}"
    pages: list[dict] = []
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != f"{NS}page":
            continue
        title_el = elem.find(f"{NS}title")
        ns_el = elem.find(f"{NS}ns")
        rev_el = elem.find(f"{NS}revision")
        if title_el is None or ns_el is None or rev_el is None:
            elem.clear()
            continue
        text_el = rev_el.find(f"{NS}text")
        text = text_el.text if text_el is not None and text_el.text else ""
        pages.append({
            "title": title_el.text or "",
            "ns": int(ns_el.text or 0),
            "text": text,
        })
        elem.clear()
    return pages


def precisa_atualizar(local: str, remoto: str | None) -> bool:
    """Decide se precisa enviar edit. True se remoto não existe ou difere."""
    if remoto is None:
        return True
    return local != remoto


EDIT_SUMMARY = "Migração inicial Fandom → Miraheze"


def subir_paginas(
    client: MirahezeClient,
    paginas: list[dict],
    dry_run: bool,
) -> tuple[int, int, int]:
    """Sobe páginas em ordem de namespace (templates primeiro).

    Retorna (criadas, atualizadas, puladas).
    """
    ordem_idx = {ns: i for i, ns in enumerate(NAMESPACE_ORDER)}
    paginas_ordenadas = sorted(
        paginas, key=lambda p: ordem_idx.get(p["ns"], 999)
    )

    criadas = 0
    atualizadas = 0
    puladas = 0
    falhas: list[str] = []

    total = len(paginas_ordenadas)
    for i, p in enumerate(paginas_ordenadas, 1):
        title = p["title"]
        text = p["text"]
        try:
            remoto = com_retry(client.get_wikitext, title)
        except Exception as e:
            log_linha(f"  [ERR] {title}: get falhou — {e}")
            falhas.append(title)
            continue

        if not precisa_atualizar(text, remoto):
            log_linha(f"  [skip {i}/{total}] {title} (idêntico)")
            puladas += 1
            continue

        acao = "criar" if remoto is None else "atualizar"
        if dry_run:
            log_linha(f"  [{acao} {i}/{total}] {title} (dry-run)")
        else:
            try:
                com_retry(client.edit, title, text, EDIT_SUMMARY)
                log_linha(f"  [OK {acao} {i}/{total}] {title}")
                time.sleep(SLEEP_EDIT)
            except Exception as e:
                log_linha(f"  [ERR] {title}: edit falhou — {e}")
                falhas.append(title)
                continue
        if remoto is None:
            criadas += 1
        else:
            atualizadas += 1

    if falhas:
        log_linha(f"\n  Falhas em páginas: {len(falhas)}")
        for t in falhas:
            log_linha(f"    - {t}")
    return criadas, atualizadas, puladas


UPLOAD_COMMENT = "Migração inicial Fandom → Miraheze"


def validacao_inline(
    client: MirahezeClient,
    paginas: list[dict],
    n_amostras: int = 5,
) -> int:
    """Valida que N páginas-âncora aleatórias batem entre dump e Miraheze.

    Retorna número de mismatches (0 = sucesso).
    """
    if len(paginas) <= n_amostras:
        amostras = paginas
    else:
        amostras = random.sample(paginas, n_amostras)
    mismatches = 0
    log_linha(f"\n  Validando {len(amostras)} páginas aleatórias...")
    for p in amostras:
        try:
            remoto = com_retry(client.get_wikitext, p["title"])
        except Exception as e:
            log_linha(f"  [ERR validação] {p['title']}: {e}")
            mismatches += 1
            continue
        if remoto is None:
            log_linha(f"  [FAIL] {p['title']}: não existe no Miraheze")
            mismatches += 1
        elif remoto != p["text"]:
            log_linha(f"  [FAIL] {p['title']}: conteúdo difere")
            mismatches += 1
        else:
            log_linha(f"  [OK]   {p['title']}")
    return mismatches


def subir_imagens(
    client: MirahezeClient,
    images_dir: Path,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Sobe todas as imagens em images_dir pro Miraheze.

    Retorna (subidas, puladas, falhas).
    """
    arquivos = sorted([p for p in images_dir.iterdir() if p.is_file()])
    log_linha(f"  {len(arquivos)} arquivos em {images_dir}")

    subidas = 0
    puladas = 0
    falhas: list[str] = []

    total = len(arquivos)
    for i, f in enumerate(arquivos, 1):
        nome = f.name
        if dry_run:
            log_linha(f"  [upload {i}/{total}] {nome} (dry-run, {f.stat().st_size:,} bytes)")
            subidas += 1
            continue
        try:
            r = com_retry(client.upload, nome, f, UPLOAD_COMMENT)
            result = r.get("upload", {}).get("result", "")
            if result == "Success":
                log_linha(f"  [OK upload {i}/{total}] {nome}")
                subidas += 1
            elif result == "Warning":
                warnings = r.get("upload", {}).get("warnings", {})
                if "duplicate" in warnings or "exists" in warnings:
                    log_linha(f"  [skip {i}/{total}] {nome} (já existe)")
                    puladas += 1
                else:
                    log_linha(f"  [WARN {i}/{total}] {nome}: {warnings}")
                    subidas += 1
            else:
                log_linha(f"  [WARN {i}/{total}] {nome}: result={result}")
                subidas += 1
            time.sleep(SLEEP_UPLOAD)
        except Exception as e:
            log_linha(f"  [ERR] {nome}: upload falhou — {e}")
            falhas.append(nome)

    if falhas:
        log_linha(f"\n  Falhas em uploads: {len(falhas)}")
        for nm in falhas:
            log_linha(f"    - {nm}")
    return subidas, puladas, len(falhas)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica de verdade. Sem essa flag, roda em dry-run.",
    )
    parser.add_argument(
        "--skip-pages",
        action="store_true",
        help="Pula a fase de páginas (só sobe imagens).",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="Pula a fase de imagens (só sobe páginas).",
    )
    args = parser.parse_args()

    user = os.environ.get("MIRAHEZE_BOT_USER")
    pwd = os.environ.get("MIRAHEZE_BOT_PASS")
    if not user or not pwd:
        print("ERRO: defina MIRAHEZE_BOT_USER e MIRAHEZE_BOT_PASS no env.", file=sys.stderr)
        return 2

    client = MirahezeClient(API, user, pwd)
    print(f"Logando em {API} como {user}...")
    client.login()
    print("Login OK. CSRF token obtido.")

    modo = "APPLY" if args.apply else "DRY-RUN"
    print(f"Modo: {modo}")

    if not args.skip_pages:
        log_linha(f"\n=== Carregando dump de {DUMP} ===")
        paginas = paginas_do_dump(DUMP)
        log_linha(f"  {len(paginas)} páginas no dump")

        log_linha("\n=== Subindo páginas (templates → categorias → ns0 → arquivos) ===")
        criadas, atualizadas, puladas = subir_paginas(client, paginas, not args.apply)
        log_linha(
            f"\n  Páginas: {criadas} criadas, {atualizadas} atualizadas, "
            f"{puladas} puladas"
        )

    if not args.skip_images:
        log_linha("\n=== Subindo imagens ===")
        i_subidas, i_puladas, i_falhas = subir_imagens(
            client, IMAGES_DIR, not args.apply
        )
        log_linha(
            f"\n  Imagens: {i_subidas} subidas, {i_puladas} puladas, "
            f"{i_falhas} falhas"
        )

    if args.apply and not args.skip_pages:
        log_linha("\n=== Validação inline ===")
        mismatches = validacao_inline(client, paginas, n_amostras=5)
        if mismatches:
            log_linha(f"\n  ⚠️  {mismatches} mismatch(es) detectado(s) na validação")
            return 1
        else:
            log_linha("  ✓ Todas as 5 páginas-âncora batem.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
