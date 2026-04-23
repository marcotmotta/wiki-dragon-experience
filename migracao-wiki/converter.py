"""Converter focado no demo: 4 páginas da wiki Dragon Experience.

Lê o dump.xml, localiza 4 páginas escolhidas, converte wikitext → markdown
Obsidian com frontmatter mínimo e escreve em content/.

Limitações do demo (remoções conscientes, a tratar na migração completa):
- <ref>...</ref> é removido (footnotes ficam p/ depois)
- [[File:...]] é comentado (imagens ainda não baixadas)
- Templates não-core (Icon*, Top Bar, Colorbox) são removidos
- Nenhum parse de tabelas wikitext complexas (nenhuma aparece nas 4)
"""
from __future__ import annotations
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path("/Users/inco/mark/wiki-dragon-experience")
DUMP = REPO / "migracao-wiki" / "dump.xml"
CP_TEMPLATE = REPO / "migracao-wiki" / "templates" / "Cp.wiki"
CONTENT = REPO / "content"
NS = "{http://www.mediawiki.org/xml/export-0.11/}"

# título da página no dump → (pasta, filename-sem-extensão, tipo)
# título da página no dump → (pasta, filename-sem-extensão, tipo-fallback)
# O tipo-fallback é usado quando o template principal da página não tem campo "tipo".
# Para Personagens, o próprio template define "tipo" (PC/NPC) e sobrescreve o fallback.
DEMO_PAGES = {
    '"Ataque Surpresa" (1x1)': ("Capítulos", "1x1", "capítulo"),
    "Daniel":                  ("Personagens", "Daniel", "personagem"),
    "Eryn Montreal":           ("Personagens", "Eryn Montreal", "personagem"),
    "Bosque do Retorno":       ("Locais", "Bosque do Retorno", "local"),
}


def load_cp_database() -> dict[str, str]:
    """Parse Cp.wiki's #switch to map codes like '1x1', '1d1', '1r1' → string."""
    text = CP_TEMPLATE.read_text(encoding="utf-8")
    db: dict[str, str] = {}
    # Matches lines like: |1x1=[["Ataque Surpresa" (1x1)]]
    # or:                 |1d1=09/03/2019
    for m in re.finditer(r"^\s*\|([A-Za-z0-9]+)\s*=\s*(.*?)\s*$", text, re.MULTILINE):
        key, val = m.group(1), m.group(2)
        # Strip outer brackets for display: [["X"]] → "X"
        val = re.sub(r"^\[\[(.+)\]\]$", r"\1", val.strip())
        db[key] = val
    return db


def parse_template_params(body: str) -> dict[str, str]:
    """Parse the body of {{Template|k=v|k=v|...}} into a dict.

    Handles | inside [[...]] and {{...}} by tracking nesting depth.
    Input is the content between outer {{ and }} without the template name.
    """
    params: dict[str, str] = {}
    depth_br = 0  # [[ ]]
    depth_tpl = 0  # {{ }}
    current = []
    parts: list[str] = []
    i = 0
    while i < len(body):
        c = body[i]
        two = body[i : i + 2]
        if two == "[[":
            depth_br += 1
            current.append(two); i += 2; continue
        if two == "]]":
            depth_br -= 1
            current.append(two); i += 2; continue
        if two == "{{":
            depth_tpl += 1
            current.append(two); i += 2; continue
        if two == "}}":
            depth_tpl -= 1
            current.append(two); i += 2; continue
        if c == "|" and depth_br == 0 and depth_tpl == 0:
            parts.append("".join(current))
            current = []
            i += 1; continue
        current.append(c); i += 1
    if current:
        parts.append("".join(current))

    for part in parts:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        params[k.strip()] = v.strip()
    return params


def find_top_template(text: str, names: list[str]) -> tuple[str, str, int, int] | None:
    """Find the first occurrence of any {{Name|...}} at the top level.

    Returns (name, body, start, end) — positions of the full {{...}} in text.
    """
    # Procura por cada nome; escolhe o primeiro por posição
    candidates = []
    for name in names:
        m = re.search(r"\{\{\s*" + re.escape(name) + r"\b", text)
        if m:
            candidates.append((m.start(), name))
    if not candidates:
        return None
    candidates.sort()
    start, name = candidates[0]
    # Localiza o }} correspondente balanceado
    depth = 0
    i = start
    while i < len(text):
        two = text[i : i + 2]
        if two == "{{":
            depth += 1; i += 2
        elif two == "}}":
            depth -= 1; i += 2
            if depth == 0:
                end = i
                body = text[start + 2 + len(name) : end - 2]
                # remove leading "|" if present
                body = body.lstrip()
                if body.startswith("|"):
                    body = body[1:]
                return (name, body, start, end)
        else:
            i += 1
    return None


def yaml_escape(val: str) -> str:
    """Escape a value for inline YAML. Quotes if it contains special chars."""
    if val == "":
        return '""'
    if any(c in val for c in ':#[]{}&*!|>\'"%@`,\n'):
        return '"' + val.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return val


def render_frontmatter(fields: dict[str, object]) -> str:
    lines = ["---"]
    for k, v in fields.items():
        if isinstance(v, list):
            if not v:
                continue
            lines.append(f"{k}:")
            for p in v:
                lines.append(f"  - {yaml_escape(str(p))}")
            continue
        s = str(v)
        # Multi-valor (tem <br/>): vira lista YAML
        parts = [p.strip() for p in re.split(r"<br\s*/?>", s) if p.strip()]
        if len(parts) > 1:
            lines.append(f"{k}:")
            for p in parts:
                lines.append(f"  - {yaml_escape(p)}")
        else:
            lines.append(f"{k}: {yaml_escape(s)}")
    lines.append("---")
    return "\n".join(lines)


def resolve_cp_inline(text: str, cp_db: dict[str, str]) -> str:
    """Resolve {{Cp|...}} inside arbitrary text (body or frontmatter values)."""

    def cp_repl(m):
        args = [p.strip() for p in m.group(1).split("|")]
        if len(args) == 1:
            code = args[0]
            if re.match(r"^\d+x\d+$", code):
                return f"[[{code}]]"
            return cp_db.get(code, f"[[{code}]]")
        if len(args) == 2:
            code, mod = args
            m2 = re.match(r"^(\d+)x(\d+)$", code)
            if m2:
                campanha, numero = m2.groups()
                key = f"{campanha}{mod}{numero}"
                return cp_db.get(key, f"[[{code}]]")
        return m.group(0)
    return re.sub(r"\{\{Cp\|([^{}]+?)\}\}", cp_repl, text)


def extract_categories(text: str) -> tuple[list[str], str]:
    """Extrai [[Categoria:X]] do wikitext, devolve (lista, texto-sem-categorias)."""
    cats: list[str] = []
    def repl(m):
        cats.append(m.group(1).strip())
        return ""
    text = re.sub(r"\[\[Categoria:([^\]]+)\]\]", repl, text)
    return cats, text


def convert_body(text: str, cp_db: dict[str, str]) -> str:
    """Converte wikitext → markdown. Ordem dos passos importa."""

    # Remover <ref ... /> self-closing e <ref>...</ref> (balanced, greedy-safe)
    text = re.sub(r"<ref[^>]*/\s*>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)

    # {{Quote box|quote=...|person=...}}  →  callout > [!quote]
    def quote_box_repl(m):
        params = parse_template_params(m.group(1))
        # tira marcações internas do quote; mantém apenas linhas de texto
        quote = params.get("quote", "")
        quote = re.sub(r"<br\s*/?>", "\n", quote)
        quote = re.sub(r"''(.+?)''", r"\1", quote)  # sem italic aninhado
        person = params.get("person", "").strip()
        lines = [ln.strip() for ln in quote.split("\n") if ln.strip()]
        quote_lines = [f"> {ln}" for ln in lines]
        attribution = f"> — {person}" if person else None
        parts = ["> [!quote]"] + quote_lines
        if attribution:
            parts += ["> ", attribution]
        # blank lines antes/depois garantem separação do parágrafo anterior/seguinte
        return "\n\n" + "\n".join(parts) + "\n\n"
    text = re.sub(r"\{\{Quote box\s*\|(.+?)\}\}", quote_box_repl, text, flags=re.DOTALL)

    # {{Cp|...}} no corpo — usa o mesmo resolver do frontmatter
    text = resolve_cp_inline(text, cp_db)

    # Templates auxiliares: remover (ou comentar)
    text = re.sub(r"\{\{Referências\}\}", "", text)
    text = re.sub(r"\{\{Icon [^{}]+\}\}", "", text)
    text = re.sub(r"\{\{Main Article\s*\|\s*([^{}]+?)\}\}",
                  lambda m: f"> [!info] Artigo principal\n> [[{m.group(1).strip()}]]\n", text)

    # [[Categoria:X]] — já extraído antes pelo convert_page (via extract_categories)
    text = re.sub(r"\[\[Categoria:[^\]]+\]\]", "", text)

    # [[File:foo.jpg|left|thumb|235x235px|Legenda]] — suporta size + caption
    # Emite <figure> com <img> + opcional <figcaption>.
    KNOWN_FORMATS = {"thumb", "thumbnail", "frame", "frameless", "border"}
    KNOWN_ALIGNS = {"left", "right", "center", "none"}

    def file_repl(m):
        inner = m.group(1)
        parts = [p.strip() for p in inner.split("|")]
        fname = parts[0]
        size_attr = ""
        align_class = ""
        caption = ""
        for p in parts[1:]:
            if not p:
                continue
            if p in KNOWN_FORMATS:
                continue
            if p in KNOWN_ALIGNS:
                align_class = f"wiki-align-{p}"
                continue
            if p.startswith("link=") or p.startswith("alt="):
                continue
            size_m = re.match(r"^(\d+)(?:x(\d+))?px$", p)
            if size_m:
                size_attr = f' width="{size_m.group(1)}"'
                if size_m.group(2):
                    size_attr += f' height="{size_m.group(2)}"'
                continue
            # qualquer outra coisa = caption (última geralmente é a legenda)
            caption = p

        classes = ["wiki-figure"]
        if align_class:
            classes.append(align_class)
        cls = " ".join(classes)
        src = f"ASSET_PREFIX{fname}"
        # Sempre envolve com \n\n antes e depois — blocos HTML precisam disso
        # para o micromark fechar o bloco e voltar a parsear markdown.
        if caption:
            return ("\n\n"
                    f'<figure class="{cls}">'
                    f'<img src="{src}"{size_attr} alt="{caption}" />'
                    f'<figcaption>{caption}</figcaption>'
                    f'</figure>'
                    "\n\n")
        return f'\n\n<figure class="{cls}"><img src="{src}"{size_attr} alt="" /></figure>\n\n'

    text = re.sub(r"\[\[File:([^\[\]]+?)\]\]", file_repl, text)
    text = re.sub(r"\[\[Arquivo:([^\[\]]+?)\]\]", file_repl, text)

    # Headings: ===== H5 =====, ==== H4 ====, === H3 ===, == H2 ==
    # [ \t]* em vez de \s* pra não engolir \n (com MULTILINE, $ matcha antes de \n
    # e \s* consumiria o \n fazendo os matches subsequentes colar headings vizinhos).
    for n in (6, 5, 4, 3, 2):
        sig = "=" * n
        pat = rf"^[ \t]*{sig}[ \t]*(.+?)[ \t]*{sig}[ \t]*$"
        text = re.sub(pat, lambda m, n=n: ("#" * n) + " " + m.group(1), text, flags=re.MULTILINE)

    # Bold '''x''' antes de italic ''x'' (bold tem 3 aspas, italic tem 2)
    text = re.sub(r"'''(.+?)'''", r"**\1**", text, flags=re.DOTALL)
    text = re.sub(r"''(.+?)''", r"*\1*", text, flags=re.DOTALL)

    # Links externos [url texto] → [texto](url)
    text = re.sub(r"\[(https?://[^\s\]]+)\s+([^\]]+)\]", r"[\2](\1)", text)

    # <br/> e <br> em body → duas quebras de linha (hard break em markdown)
    text = re.sub(r"<br\s*/?>", "\n\n", text)

    # Garante linha em branco antes de qualquer heading ATX (# a ######)
    # para o CommonMark reconhecer o heading mesmo após bloco anterior.
    text = re.sub(r"(?<!\n\n)(\n)(#{1,6} )", r"\n\n\2", text)

    # Limpar múltiplas linhas em branco (3+ → 2)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip() + "\n"


def convert_page(title: str, wikitext: str, cp_db: dict[str, str]) -> tuple[Path, str]:
    folder, slug, tipo = DEMO_PAGES[title]
    # Detectar o primeiro infobox (Personagem, Capítulo, Cidade, Reino, Grupo, ...)
    INFOBOX_NAMES = ["Personagem", "Capítulo", "Cidade", "Reino", "Grupo",
                     "Estabelecimento", "Mundo", "Item", "Magia", "Batalha", "Diário"]
    infobox = find_top_template(wikitext, INFOBOX_NAMES)

    frontmatter: dict[str, object] = {"tipo": tipo, "title": title}

    # Extrai categorias do wikitext inteiro (antes de qualquer outro parsing)
    categories, wikitext = extract_categories(wikitext)
    if categories:
        frontmatter["tags"] = categories

    body = wikitext
    if infobox:
        name, params_body, start, end = infobox
        params = parse_template_params(params_body)
        for k, v in params.items():
            if not v:
                continue  # não escrever campos vazios (respeita "zero bloat")
            if k == "title1":
                continue  # o título vem do dump
            # Para Personagem o template traz "tipo" = PC/NPC — é o tipo efetivo.
            # Para outros infoboxes, o tipo vem da pasta (já setado acima).
            # image1 → image / caption-image1 → image_caption (nomes mais limpos p/ YAML)
            if k == "image1":
                k = "image"
            elif k == "caption-image1" or k == "caption1":
                k = "image_caption"
            # Resolve {{Cp|...}} inline em valores de frontmatter
            v = resolve_cp_inline(v, cp_db)
            # Remove <ref>...</ref> e <br/> de valores simples (antes da serialização YAML)
            v = re.sub(r"<ref[^>]*>.*?</ref>", "", v, flags=re.DOTALL)
            v = re.sub(r"<ref[^>]*/\s*>", "", v)
            frontmatter[k] = v
        # Remover o bloco do infobox do body
        body = body[:start] + body[end:]

    body_md = convert_body(body, cp_db)
    # Substitui ASSET_PREFIX pelo caminho relativo p/ /attachments/ a partir desta pasta
    # folder = "Capítulos" → depth=1 → prefix = "../attachments/"
    depth = len(folder.split("/"))
    asset_prefix = "../" * depth + "attachments/"
    body_md = body_md.replace("ASSET_PREFIX", asset_prefix)

    fm_yaml = render_frontmatter(frontmatter)
    content = fm_yaml + "\n\n" + body_md

    out_path = CONTENT / folder / f"{slug}.md"
    return out_path, content


def main() -> None:
    cp_db = load_cp_database()
    print(f"Cp DB: {len(cp_db)} entradas")

    tree = ET.parse(DUMP)
    root = tree.getroot()

    # Limpar content/ (mantém .obsidian, images, etc.)
    for sub in ("Campanhas", "Capítulos", "Personagens", "Locais"):
        d = CONTENT / sub
        if d.exists():
            for f in d.glob("*.md"):
                f.unlink()
    # Também remover o "Todos os Capítulos.md" e index.md (serão recriados)
    for f in [CONTENT / "Todos os Capítulos.md", CONTENT / "index.md"]:
        if f.exists():
            f.unlink()

    produced = 0
    for page in root.findall(f"{NS}page"):
        title = (page.find(f"{NS}title").text or "").strip()
        if title not in DEMO_PAGES:
            continue
        rev = page.find(f"{NS}revision")
        if rev is None:
            continue
        text_el = rev.find(f"{NS}text")
        if text_el is None or not text_el.text:
            continue
        path, content = convert_page(title, text_el.text, cp_db)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"  → {path.relative_to(REPO)} ({len(content)} bytes)")
        produced += 1

    # index.md mínimo
    (CONTENT / "index.md").write_text(
        "---\ntitle: Dragon Experience Wiki (demo)\n---\n\n"
        "# Dragon Experience Wiki\n\n"
        "Demo de 4 páginas migradas do Fandom.\n\n"
        "## Páginas\n\n"
        "- [[1x1]]\n"
        "- [[Daniel]]\n"
        "- [[Eryn Montreal]]\n"
        "- [[Bosque do Retorno]]\n",
        encoding="utf-8",
    )
    print(f"Total: {produced} páginas + index.md")


if __name__ == "__main__":
    main()
