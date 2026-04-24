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
# Mapa: template principal da página → (pasta, tipo-fallback).
# "Personagem" é tratado especialmente — o tipo vem do campo `tipo = PC/NPC/...`
# do próprio template, não do fallback, e dispara pra PCs/ ou NPCs/.
INFOBOX_ROUTES: dict[str, tuple[str, str]] = {
    "Capítulo":        ("Capítulos", "capítulo"),
    "Cidade":          ("Lugares", "lugar"),
    "Reino":           ("Lugares", "lugar"),
    "Estabelecimento": ("Lugares", "lugar"),
    "Mundo":           ("Mundo", "mundo"),
    "Grupo":           ("Grupos", "grupo"),
    "Item":            ("Itens", "item"),
    "Magia":           ("Magias", "magia"),
    "Batalha":         ("Batalhas", "batalha"),
    "Diário":          ("Diários", "diário"),
}

INFOBOX_NAMES: list[str] = ["Personagem"] + list(INFOBOX_ROUTES.keys())


def sanitize_filename(title: str) -> str:
    """Remove caracteres proibidos em nomes de arquivo."""
    return title.replace("/", "-").replace("\\", "-")


# "Parte 1", "Parte 1: Adentrando", "Parte 11" — todas são Partes.
# Redirects ("Parte 1" que aponta pra "Parte 1: Adentrando") são filtrados
# antes por is_redirect().
PARTE_TITLE_RE = re.compile(r"^Parte\s+\d+(?::\s|\s*$)")
CAMPANHA_TITLE_RE = re.compile(r"^Campanha\s+")


def is_redirect(wikitext: str) -> bool:
    return bool(re.match(r"#REDIREC", wikitext.strip(), re.IGNORECASE))


def redirect_target(wikitext: str) -> str | None:
    """Se a página é um redirect, devolve o título do alvo. Senão None."""
    m = re.match(r"#REDIREC[A-Z]*\s*\[\[([^\]]+)\]\]",
                 wikitext.strip(), re.IGNORECASE)
    return m.group(1).strip() if m else None


def build_redirect_map(root: ET.Element) -> dict[str, list[str]]:
    """Scaneia dump.xml e devolve {alvo: [títulos-fonte-de-redirect, ...]}.
    Usado pra injetar `aliases:` no frontmatter da página alvo, permitindo
    que wikilinks `[[Alexander]]` resolvam em `[[Alexander d'Morales]]`
    tanto no Obsidian quanto no Quartz."""
    targets: dict[str, list[str]] = {}
    for page in root.findall(f"{NS}page"):
        title = (page.find(f"{NS}title").text or "").strip()
        rev = page.find(f"{NS}revision")
        if rev is None:
            continue
        text_el = rev.find(f"{NS}text")
        if text_el is None or not text_el.text:
            continue
        target = redirect_target(text_el.text)
        if target:
            # pode ter anchor (#...) — ignora, só importa o nome da página
            target = target.split("#")[0].strip()
            targets.setdefault(target, []).append(title)
    return targets



# Mapa categoria-do-Fandom → pasta de destino. Se a página tem qualquer uma
# dessas categorias em [[Categoria:X]], vai pra pasta correspondente. Se não
# tem nenhuma, cai em Outros/. O roteamento é por CATEGORIA — independente de
# qual template de infobox a página usa (ou se tem infobox). Espelha a
# taxonomia nativa da Fandom.
CATEGORY_TO_FOLDER: dict[str, str] = {
    "PC": "PCs",
    "NPC": "NPCs",
    "Capítulos": "Capítulos",
    "Partes": "Partes",
    "Lugares": "Lugares",
    "Grupos e Organizações": "Grupos",
}


def _page_categories(wikitext: str) -> list[str]:
    """Lista categorias [[Categoria:X]] (sem sort key) da página."""
    return [
        m.group(1).split("|")[0].strip()
        for m in re.finditer(r"\[\[Categoria:([^\]]+?)\]\]", wikitext)
    ]


def route_page(title: str, wikitext: str) -> tuple[str, str, str] | None:
    """Decide (folder, slug, tipo) baseado nas categorias da página (espelho
    direto da taxonomia Fandom). Se a página tem `[[Categoria:PC]]`, vai pra
    `PCs/`; se não tem nenhuma das categorias conhecidas, cai em `Outros/`."""
    # Redirects são páginas de apenas 1 linha apontando pra outra; pula.
    if is_redirect(wikitext):
        return None

    # Pasta por categoria (primeira match vence)
    cats = _page_categories(wikitext)
    folder: str | None = None
    for c in cats:
        if c in CATEGORY_TO_FOLDER:
            folder = CATEGORY_TO_FOLDER[c]
            break
    if folder is None:
        folder = "Outros"

    # Deriva `tipo` e `slug`:
    # - Template reconhecido → tipo do template (pra rodar o Infobox correto)
    # - Senão → tipo "parte"/"campanha" por padrão de título, ou "outro" fallback.
    infobox = find_top_template(wikitext, INFOBOX_NAMES)
    tipo: str
    slug: str
    if infobox:
        name, body, _, _ = infobox
        if name == "Personagem":
            params = parse_template_params(body)
            tipo = (params.get("tipo") or "NPC").strip()
        else:
            _, tipo = INFOBOX_ROUTES[name]
        if name == "Capítulo":
            m = re.search(r"\((\d+x\d+)\)", title)
            slug = m.group(1) if m else sanitize_filename(title)
        else:
            slug = sanitize_filename(title)
    else:
        if PARTE_TITLE_RE.match(title):
            tipo = "parte"
        elif CAMPANHA_TITLE_RE.match(title):
            tipo = "campanha"
        else:
            tipo = "outro"
        slug = sanitize_filename(title)

    return folder, slug, tipo


# Modos de execução: controla qual subconjunto de páginas migrar e quais
# pastas limpar antes. O filtro é por FOLDER de destino (derivado de route_page),
# não pelo nome do template — assim Partes e Campanhas (sem infobox, detectadas
# por título) entram no modo "all".
# 7 pastas terminais — espelho direto das categorias Fandom + Outros fallback.
# Pastas legacy (Campanhas, Diários, Diário, Itens, Magias, Mundo, Batalhas,
# Personagens, Locais) estão na clean list pra garantir limpeza em migrações.
_ALL_FOLDERS = {"PCs", "NPCs", "Capítulos", "Partes", "Lugares", "Grupos", "Outros"}
_ALL_CLEAN = list(_ALL_FOLDERS) + [
    # legacy — remover se ainda existirem no disco de corridas anteriores
    "Campanhas", "Diários", "Diário", "Itens", "Magias", "Mundo", "Batalhas",
    "Personagens", "Locais",
]

MODES: dict[str, dict] = {
    "personagens": {"folders": {"PCs", "NPCs"}, "clean": ["PCs", "NPCs", "Personagens"]},
    "capitulos":   {"folders": {"Capítulos"}, "clean": ["Capítulos"]},
    "partes":      {"folders": {"Partes"}, "clean": ["Partes"]},
    "lugares":     {"folders": {"Lugares"}, "clean": ["Lugares", "Locais"]},
    "grupos":      {"folders": {"Grupos"}, "clean": ["Grupos"]},
    "outros":      {"folders": {"Outros"}, "clean": [
                       "Outros", "Campanhas", "Diários", "Diário",
                       "Itens", "Magias", "Mundo", "Batalhas"]},
    "all":         {"folders": _ALL_FOLDERS, "clean": _ALL_CLEAN},
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
    # Procura por cada nome; escolhe o primeiro por posição.
    # Exige `\s*\|` depois do nome — infoboxes reais sempre têm parâmetros.
    # Isso evita falsos positivos como {{Diário}} no final de páginas de Partes
    # (que é uma referência cross-page, não um infobox).
    candidates = []
    for name in names:
        m = re.search(r"\{\{\s*" + re.escape(name) + r"\s*\|", text)
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


def clean_wikilink_value(v: str) -> str:
    """Normaliza um wikilink de frontmatter pra que o Obsidian reconheça
    como link clicável:
    - `[[Título com (NxM)]]` → `[[NxM]]` (slug real do arquivo)
    - `[[X]] (anotação)` → `[[X]]` (Obsidian Properties só trata como link
      valores que são só o wikilink)
    """
    v = re.sub(r"\[\[[^\[\]]*?\((\d+x\d+)\)\]\]", r"[[\1]]", v)
    v = re.sub(r"(\[\[[^\]]+\]\])\s*\([^)]+\)", r"\1", v)
    return v


def extract_list_with_annotations(value: str) -> tuple[list[str] | None, list[str] | None]:
    """Se o valor tem múltiplas partes (separadas por <br/>) e pelo menos
    uma tem anotação parentética ao final — tipo `[[A Mão]] (membro)` —,
    separa em duas listas paralelas: itens (sem anotação) e anotações.
    Senão retorna (None, None) e deixa o caller usar o caminho escalar.
    """
    if not re.search(r"<br\s*/?>", value):
        return None, None

    parts = re.split(r"<br\s*/?>", value)
    items: list[str] = []
    annotations: list[str] = []
    has_annotation = False
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Detecta "...[[X]]... (anotação)" ao final da linha
        m = re.match(r"^(.*?\[\[[^\]]+\]\].*?)\s*\(([^)]+)\)\s*$", p)
        if m:
            has_annotation = True
            items.append(m.group(1).strip())
            annotations.append(m.group(2).strip())
        else:
            items.append(p)
            annotations.append("")
    if not has_annotation:
        return None, None
    return items, annotations


def _split_cells_respecting_brackets(text: str, sep: str) -> list[str]:
    """Divide uma string em células respeitando nesting de [[...]] e {{...}}.
    `sep` é o separador (ex: `||` pra células de dados, `!!` pra headers).
    """
    cells: list[str] = []
    buf: list[str] = []
    depth_br = 0
    depth_tpl = 0
    i = 0
    while i < len(text):
        two = text[i : i + 2]
        if two == "[[":
            depth_br += 1; buf.append(two); i += 2; continue
        if two == "]]":
            depth_br -= 1; buf.append(two); i += 2; continue
        if two == "{{":
            depth_tpl += 1; buf.append(two); i += 2; continue
        if two == "}}":
            depth_tpl -= 1; buf.append(two); i += 2; continue
        if two == sep and depth_br == 0 and depth_tpl == 0:
            cells.append("".join(buf))
            buf = []
            i += 2
            continue
        buf.append(text[i]); i += 1
    if buf:
        cells.append("".join(buf))
    return cells


def _strip_cell_attrs(cell: str) -> str:
    """Remove atributos wikitext no início da célula:
    `style="..." | content`  →  `content`
    `colspan="2" | content`  →  `content`
    Conservador: só strippa se tem `=` seguido de `|` antes de qualquer
    wikilink/template.
    """
    # Procura primeiro `|` top-level que NÃO esteja em [[...]] ou {{...}}
    depth_br = 0
    depth_tpl = 0
    pipe_pos = -1
    for i in range(len(cell)):
        two = cell[i : i + 2]
        if two == "[[":
            depth_br += 1; continue
        if two == "]]":
            depth_br -= 1; continue
        if two == "{{":
            depth_tpl += 1; continue
        if two == "}}":
            depth_tpl -= 1; continue
        if cell[i] == "|" and depth_br == 0 and depth_tpl == 0:
            pipe_pos = i
            break
    if pipe_pos < 0:
        return cell.strip()
    # Verifica se prefixo tem cara de atributos: tem "=" antes do |
    prefix = cell[:pipe_pos]
    if "=" in prefix and re.match(r'^\s*(\w+\s*=\s*"[^"]*"\s*)+$', prefix):
        return cell[pipe_pos + 1:].strip()
    return cell.strip()


def _simplify_file_refs_inline(content: str) -> str:
    """Converte `[[File:X|...]]` em `![[X|width]]` inline. Necessário ANTES
    do file_repl global, que emitiria um callout multi-linha e quebraria
    a tabela markdown onde a célula vive."""
    def repl(m: re.Match) -> str:
        parts = [p.strip() for p in m.group(1).split("|")]
        fname = parts[0]
        width = "200"
        for p in parts[1:]:
            sm = re.match(r"^(\d+)(?:x\d+)?px$", p)
            if sm:
                width = sm.group(1)
        return f"![[{fname}|{width}]]"
    content = re.sub(r"\[\[File:([^\[\]]+?)\]\]", repl, content)
    content = re.sub(r"\[\[Arquivo:([^\[\]]+?)\]\]", repl, content)
    return content


def convert_wikitables_to_markdown(text: str) -> str:
    """Converte blocos `{| ... |}` de wikitext em tabelas markdown pipe.

    Subset suportado: headers (`!`), separadores de linha (`|-`), células
    multi-linha (`||`), linhas em branco como separador implícito de linha
    (padrão comum no Fandom pra layouts sem `|-`). Colspan/rowspan/caption
    são descartados (markdown puro não suporta).
    """
    def convert(match: re.Match) -> str:
        body = match.group(1)
        rows: list[list[str]] = []
        current: list[str] = []

        def flush_row():
            nonlocal current
            if current:
                rows.append(current)
                current = []

        for raw_line in body.split("\n"):
            line = raw_line.rstrip()
            s = line.strip()
            if not s:
                # Linha em branco = row separator implícito (comum em Fandom)
                flush_row()
                continue
            if s.startswith("|}"):
                break
            if s.startswith("|+"):
                continue  # caption
            if s.startswith("|-"):
                flush_row()
                continue
            if s.startswith("!"):
                content_ = _simplify_file_refs_inline(s[1:])
                cells = _split_cells_respecting_brackets(content_, "!!")
                cells = [_strip_cell_attrs(c) for c in cells]
                current.extend(cells)
                continue
            if s.startswith("|"):
                content_ = _simplify_file_refs_inline(s[1:])
                cells = _split_cells_respecting_brackets(content_, "||")
                cells = [_strip_cell_attrs(c) for c in cells]
                current.extend(cells)
                continue
            # Continuação da célula anterior (conteúdo multi-linha)
            if current:
                appended = _simplify_file_refs_inline(s)
                current[-1] = (current[-1] + " " + appended).strip()

        flush_row()

        rows = [r for r in rows if any(c.strip() for c in r)]
        if not rows:
            return ""

        num_cols = max(len(r) for r in rows)
        rows = [r + [""] * (num_cols - len(r)) for r in rows]

        header = rows[0]
        body_rows = rows[1:] if len(rows) > 1 else []

        out_lines = ["| " + " | ".join(header) + " |"]
        out_lines.append("|" + "|".join(["---"] * num_cols) + "|")
        for r in body_rows:
            out_lines.append("| " + " | ".join(r) + " |")

        return "\n\n" + "\n".join(out_lines) + "\n\n"

    return re.sub(
        r"^\s*\{\|[^\n]*\n([\s\S]*?)^\s*\|\}",
        convert,
        text,
        flags=re.MULTILINE,
    )


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


def normalize_tag(tag: str) -> str:
    """Normaliza nome de tag: espaço → hífen. Case preservado.
    Obsidian não suporta tags com espaço (trata como múltiplas tags).
    """
    return tag.strip().replace(" ", "-")


def extract_categories(text: str) -> tuple[list[str], str]:
    """Extrai [[Categoria:X]] do wikitext, devolve (lista, texto-sem-categorias).
    Nomes normalizados (espaços → hífen) pra compat com Obsidian."""
    cats: list[str] = []
    def repl(m):
        cats.append(normalize_tag(m.group(1)))
        return ""
    text = re.sub(r"\[\[Categoria:([^\]]+)\]\]", repl, text)
    return cats, text


def convert_body(text: str, cp_db: dict[str, str]) -> str:
    """Converte wikitext → markdown. Ordem dos passos importa."""

    # Remover <ref ... /> self-closing e <ref>...</ref> (balanced, greedy-safe)
    text = re.sub(r"<ref[^>]*/\s*>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    # Tags MediaWiki custom tipo <mainpage-leftcolumn-start /> e <gallery>
    text = re.sub(r"<mainpage-[^/>]+/?\s*>", "", text)
    text = re.sub(r"<gallery[^>]*>.*?</gallery>", "", text, flags=re.DOTALL)
    # Comentários HTML grandes (wikitext usa pra esconder seções em progresso)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Magic words do MediaWiki: __TOC__, __NOTOC__, __FORCARTDC__ etc.
    text = re.sub(r"__[A-Z]+__", "", text)

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

    # {{LinhaCap|...}} e {{LinhaLast|...}}: usados em tabelas de capítulos
    # das páginas de Parte. Removemos aqui — a listagem é gerada
    # automaticamente via bloco Dataview injetado pelo converter.
    text = re.sub(r"\{\{LinhaCap\s*\|[^{}]*\}\}", "", text)
    text = re.sub(r"\{\{LinhaLast[^{}]*\}\}", "", text)

    # Converte wikitext tables `{| ... |}` em markdown pipe tables ANTES
    # dos outros passos (a conversão lida com o próprio fechamento).
    text = convert_wikitables_to_markdown(text)

    # Remove tabelas markdown vazias (só header + separator, sem linhas de
    # dados). Aparecem quando LinhaCap foi strippado e a tabela do wikitext
    # só tinha o cabeçalho. Seriam substituídas por um bloco Dataview injetado
    # depois, mas ficaria órfã se não removesse aqui.
    text = re.sub(
        r"^\|[^\n]*\|\s*\n\|[-|\s]+\|\s*\n(?!\|)",
        "",
        text,
        flags=re.MULTILINE,
    )

    # Qualquer resto órfão de table markers (tabelas mal-formadas, restos
    # de LinhaCap, etc): strip linhas inteiras pra não poluir o markdown.
    # Cuidado: o separador markdown `|---|---|---|` NÃO pode ser matchado aqui.
    text = re.sub(r"^\s*\{\|[^\n]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\|\}\s*$", "", text, flags=re.MULTILINE)
    # `|-` wikitext = row separator: chars depois do `-` devem ser espaço ou fim de linha.
    # Isso exclui `|---|...` (markdown separator) que tem `-` contíguo após `|-`.
    text = re.sub(r"^\s*\|-(\s.*)?$", "", text, flags=re.MULTILINE)

    # Templates auxiliares com tratamento específico:
    # {{Diário}} = tabela de navegação; expande pra lista de links markdown.
    diario_expansion = (
        "\n\n**[[Diário de Campanha]]** • "
        "[[Parte 1: Adentrando a Escuridão|Parte 1]] • "
        "[[Parte 2: Peças de Ouro|Parte 2]] • "
        "[[Parte 3: Coração Congelado|Parte 3]] • "
        "[[Parte 4: Segredos e Festividades|Parte 4]] • "
        "[[Parte 5: A Sombra que vem de Dentro|Parte 5]] • "
        "[[Parte 6: Juramento de Vingança|Parte 6]] • "
        "[[Parte 7: Inverno Eterno|Parte 7]] • "
        "[[Parte 8: Dois Anos Depois|Parte 8]] • "
        "[[Parte 9]] • "
        "[[Parte 10: Cerco Sob Pedra|Parte 10]] • "
        "[[Parte 11]]\n\n"
    )
    text = re.sub(r"\{\{Diário\}\}", diario_expansion, text)
    # {{Hr}} = horizontal rule estilizada → thematic break markdown
    text = re.sub(r"\{\{Hr\}\}", "\n\n---\n\n", text)
    # {{Arrow Right}} = símbolo inline
    text = re.sub(r"\{\{Arrow Right\}\}", "→", text)
    # {{Referências}} = lista de footnotes; removemos pois os <ref> foram stripados
    # acima (TODO Fase 3.5: converter refs em footnotes markdown nativas).
    text = re.sub(r"\{\{Referências\}\}", "", text)
    # {{Top Bar}} sem conteúdo útil quando não recebe params → remover
    text = re.sub(r"\{\{Top Bar\s*\}\}", "", text)
    # {{Colorbox|#hexcor}} → span colorido inline pra legendas de cores
    text = re.sub(
        r"\{\{Colorbox\s*\|\s*([^{}|]+?)\s*\}\}",
        r'<span style="display:inline-block;width:1em;height:1em;background:\1;vertical-align:middle;border:1px solid #888"></span>',
        text,
    )
    # {{Icon X Symbol}} — símbolos inline; sem arte mapeada ainda, remover
    text = re.sub(r"\{\{Icon [^{}]+\}\}", "", text)
    text = re.sub(r"\{\{Main Article\s*\|\s*([^{}]+?)\}\}",
                  lambda m: f"> [!info] Artigo principal\n> [[{m.group(1).strip()}]]\n", text)

    # [[Categoria:X]] — já extraído antes pelo convert_page (via extract_categories)
    text = re.sub(r"\[\[Categoria:[^\]]+\]\]", "", text)

    # [[File:foo.jpg|left|thumb|235x235px|Legenda]] — suporta size + alignment + caption.
    # Emite sintaxe Obsidian-native: embed ![[X|width]] opcionalmente dentro de
    # callout > [!figure|left/right/center] quando há caption ou alignment.
    # Renderiza nos dois lados (Obsidian + Quartz) via mesma regra CSS.
    KNOWN_FORMATS = {"thumb", "thumbnail", "frame", "frameless", "border",
                     "miniaturadaimagem", "miniatura", "mini"}
    # Mapa de alinhamento: chave = valor no wikitext, valor = normalizado pro CSS
    ALIGN_NORMALIZE = {
        "left": "left", "esq": "left", "esquerda": "left",
        "right": "right", "dir": "right", "direita": "right",
        "center": "center", "centro": "center",
        "none": None,  # sem float
    }

    def file_repl(m):
        inner = m.group(1)
        parts = [p.strip() for p in inner.split("|")]
        fname = parts[0]
        align: str | None = None
        width: str | None = None
        caption: str = ""
        has_thumb_format = False  # se "thumb"/"miniaturadaimagem" foi usado
        for p in parts[1:]:
            if not p:
                continue
            if p in KNOWN_FORMATS:
                has_thumb_format = True
                continue
            if p in ALIGN_NORMALIZE:
                align = ALIGN_NORMALIZE[p]
                continue
            if p.startswith("link=") or p.startswith("alt="):
                continue
            size_m = re.match(r"^(\d+)(?:x\d+)?px$", p)
            if size_m:
                # Obsidian embed só aceita width (altura vira auto pelo CSS)
                width = size_m.group(1)
                continue
            # qualquer outra coisa = caption
            caption = p

        # Default: 200px de largura quando o wikitext não especifica dimensão
        if not width:
            width = "200"
        embed = f"![[{fname}|{width}]]"

        # Default segue convenção MediaWiki/Fandom: `thumb`/`miniaturadaimagem`
        # sem alinhamento explícito = float right (comportamento padrão da wiki
        # original). Sem formato nem alinhamento = inline (nenhum float).
        if align is None:
            align = "right" if has_thumb_format else "none"

        # Emite callout [!figure|align] com caption opcional.
        # align="none" deixa o callout sem float (bloco normal, centrado).
        meta = "" if align == "none" else f"|{align}"
        return f"\n\n> [!figure{meta}] {caption}\n> {embed}\n\n"

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


def _inject_diario_dataview(body_md: str) -> str:
    """Insere blocos Dataview abaixo de cada heading `### [[Parte N...]]` e
    `## Especiais` na página Diário de Campanha. Cada bloco filtra capítulos
    daquela Parte (ou, no caso dos Especiais, por tag)."""

    def parte_block(m: re.Match) -> str:
        heading = m.group(0)
        numero = m.group(1)
        dv = (
            "```dataview\n"
            "TABLE WITHOUT ID\n"
            '  numero_global AS "Nº",\n'
            '  link(file.name, title) AS "Título",\n'
            '  data AS "Data"\n'
            'FROM "Capítulos"\n'
            f"WHERE parte = {numero}\n"
            "SORT numero_global ASC\n"
            "```"
        )
        return f"{heading}\n\n{dv}\n"

    body_md = re.sub(
        r"^### \[\[Parte (\d+)[^\]]*\]\]\s*$",
        parte_block,
        body_md,
        flags=re.MULTILINE,
    )

    especiais_block = (
        "```dataview\n"
        "TABLE WITHOUT ID\n"
        '  link(file.name, title) AS "Título",\n'
        '  data AS "Data"\n'
        'FROM "#Especiais"\n'
        "SORT title ASC\n"
        "```"
    )
    body_md = re.sub(
        r"^## Especiais\s*$",
        lambda m: f"{m.group(0)}\n\n{especiais_block}\n",
        body_md,
        count=1,
        flags=re.MULTILINE,
    )
    return body_md


def convert_page(
    title: str,
    wikitext: str,
    cp_db: dict[str, str],
    aliases: list[str] | None = None,
) -> tuple[Path, str] | None:
    """Converte uma página do dump em (path-destino, conteúdo-markdown).
    Retorna None se a página não tem infobox reconhecido (ignora).
    `aliases` vem do mapa de redirects — títulos de páginas-redirect apontando
    pra esta; vão pro frontmatter como `aliases:` (Obsidian + Quartz resolvem)."""
    route = route_page(title, wikitext)
    if route is None:
        return None
    folder, slug, tipo = route
    infobox = find_top_template(wikitext, INFOBOX_NAMES)

    frontmatter: dict[str, object] = {"tipo": tipo, "title": title}
    if aliases:
        frontmatter["aliases"] = list(aliases)

    # Campos derivados para cross-ref automática de listagens:
    # - capítulos ganham `parte`, `numero_global` e `campanha` via lookup no Cp DB
    # - partes ganham `numero` extraído do título
    if tipo == "capítulo":
        m = re.match(r"^(\d+)x(\d+)$", slug)
        if m:
            camp, num = m.groups()
            frontmatter["campanha"] = int(camp)
            parte_val = cp_db.get(f"{camp}p{num}")
            if parte_val and parte_val.isdigit():
                frontmatter["parte"] = int(parte_val)
            nglobal = cp_db.get(f"{camp}n{num}")
            if nglobal and nglobal.isdigit():
                frontmatter["numero_global"] = int(nglobal)
    elif tipo == "parte":
        m = re.match(r"^Parte\s+(\d+)", title)
        if m:
            frontmatter["numero"] = int(m.group(1))

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
            # Colisão com nosso `tipo` de roteamento: infoboxes não-Personagem
            # (Estabelecimento, Grupo, Item, etc.) têm um campo `tipo` que é
            # subcategoria (Taverna, Facção, Arma). Renomeia pra `categoria`.
            # Personagem mantém `tipo` porque lá ele É o tipo efetivo (PC/NPC).
            elif k == "tipo" and infobox[0] != "Personagem":
                k = "categoria"
            # Resolve {{Cp|...}} inline em valores de frontmatter
            v = resolve_cp_inline(v, cp_db)
            # Remove <ref>...</ref> e <br/> de valores simples (antes da serialização YAML)
            v = re.sub(r"<ref[^>]*>.*?</ref>", "", v, flags=re.DOTALL)
            v = re.sub(r"<ref[^>]*/\s*>", "", v)
            # Detecta lista multi-valor com anotações parentéticas:
            # ex: "[[A Mão]] (membro)<br/>[[Bahamut]] (devoto)"
            # Nesse caso, extrai pra dois campos paralelos (itens + anotações)
            # pra preservar a info sem quebrar o link no Obsidian Properties.
            items, annotations = extract_list_with_annotations(v)
            if items is not None:
                items = [clean_wikilink_value(i) for i in items]
                frontmatter[k] = items
                frontmatter[f"{k}_anotacoes"] = annotations
            else:
                # Caminho escalar — só limpa (6a + 6b: strip de anotações)
                v = clean_wikilink_value(v)
                frontmatter[k] = v
        # Remover o bloco do infobox do body
        body = body[:start] + body[end:]

    body_md = convert_body(body, cp_db)
    # Substitui ASSET_PREFIX pelo caminho relativo p/ /attachments/ a partir desta pasta
    # folder = "Capítulos" → depth=1 → prefix = "../attachments/"
    depth = len(folder.split("/"))
    asset_prefix = "../" * depth + "attachments/"
    body_md = body_md.replace("ASSET_PREFIX", asset_prefix)

    # Diário de Campanha: cada `### [[Parte N...]]` ganha um bloco Dataview
    # filtrando capítulos daquela parte. `## Especiais` filtra via tag.
    if title == "Diário de Campanha":
        body_md = _inject_diario_dataview(body_md)

    # Páginas de Parte ganham um bloco Dataview listando os capítulos
    # automaticamente. Renderiza no Obsidian via plugin e no Quartz via
    # transformer Dataview (subset DQL).
    if tipo == "parte" and "numero" in frontmatter:
        dv = (
            "```dataview\n"
            "TABLE WITHOUT ID\n"
            '  numero_global AS "Nº",\n'
            '  link(file.name, title) AS "Título",\n'
            '  data AS "Data"\n'
            'FROM "Capítulos"\n'
            f"WHERE parte = {frontmatter['numero']}\n"
            "SORT numero_global ASC\n"
            "```"
        )
        # Se a página tem "## Resumo dos Capítulos", injeta o bloco logo depois.
        # Caso contrário, apende como nova seção ao final.
        # \n\n antes e depois do bloco são obrigatórios para GFM terminar
        # tanto o heading anterior quanto a tabela gerada limpo.
        new_body, n = re.subn(
            r"(^## Resumo dos Capítulos\s*\n)",
            r"\1\n" + dv + "\n\n",
            body_md,
            count=1,
            flags=re.MULTILINE,
        )
        if n == 0:
            new_body = body_md.rstrip() + "\n\n## Capítulos\n\n" + dv + "\n"
        body_md = new_body

    fm_yaml = render_frontmatter(frontmatter)
    content = fm_yaml + "\n\n" + body_md

    out_path = CONTENT / folder / f"{slug}.md"
    return out_path, content


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Converter Fandom dump → markdown Quartz")
    parser.add_argument("--only", choices=list(MODES.keys()), default="all",
                        help="Subset a migrar (default: all)")
    args = parser.parse_args()

    mode = MODES[args.only]
    allowed_folders: set[str] = mode["folders"]

    cp_db = load_cp_database()
    print(f"Cp DB: {len(cp_db)} entradas")
    print(f"Modo: --only {args.only} (folders de destino: {sorted(allowed_folders)})")

    tree = ET.parse(DUMP)
    root = tree.getroot()

    # Mapa redirects: {"Alexander d'Morales": ["Alexander", ...]}
    # Usado pra injetar aliases no frontmatter do alvo.
    redirect_map = build_redirect_map(root)
    print(f"Redirects: {sum(len(v) for v in redirect_map.values())} apontando pra "
          f"{len(redirect_map)} páginas-alvo")

    # Limpa só as pastas relevantes ao modo — preserva o resto do content/.
    for sub in mode["clean"]:
        d = CONTENT / sub
        if d.exists():
            for f in d.rglob("*.md"):
                f.unlink()

    counts = {"ok": 0, "skip": 0, "error": 0}
    errors: list[str] = []
    for page in root.findall(f"{NS}page"):
        title = (page.find(f"{NS}title").text or "").strip()
        rev = page.find(f"{NS}revision")
        if rev is None:
            continue
        text_el = rev.find(f"{NS}text")
        if text_el is None or not text_el.text:
            continue
        wikitext = text_el.text

        # Filtra por pasta de destino (derivada de route_page).
        route = route_page(title, wikitext)
        if route is None:
            counts["skip"] += 1
            continue
        folder, _, _ = route
        if folder not in allowed_folders:
            counts["skip"] += 1
            continue

        aliases = redirect_map.get(title)
        try:
            result = convert_page(title, wikitext, cp_db, aliases=aliases)
            if result is None:
                counts["skip"] += 1
                continue
            path, content = result
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            counts["ok"] += 1
        except Exception as e:
            errors.append(f"{title}: {type(e).__name__}: {e}")
            counts["error"] += 1

    print(f"\nProcessados: {counts['ok']} | Pulados: {counts['skip']} | "
          f"Erros: {counts['error']}")
    if errors:
        print("\nErros:")
        for e in errors[:20]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
