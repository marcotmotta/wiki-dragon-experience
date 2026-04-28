# Paleta de cores da wiki Fandom — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralizar 4 cores da paleta (`#b38600`, `#fff9e6`, `#ffecb3`, `#262626`) em um único `Predefinição:Cor` na wiki Fandom Dragon Experience, atualizando 6 templates e 8 páginas via API MediaWiki.

**Architecture:** Script Python standalone em `migracao-wiki/aplicar_paleta.py` que (1) autentica via bot password contra `api.php` da Fandom, (2) cria o `Predefinição:Cor`, (3) puxa, transforma e atualiza cada template/página afetada. Tem modo `--dry-run` (default) que mostra diffs sem chamar `action=edit`, e modo `--apply` que efetua. Lógica pura de substituição é testável e está em função separada com testes unitários (`pytest` ou `unittest`).

**Tech Stack:** Python 3.10+ (stdlib only — `urllib.request`, `urllib.parse`, `json`, `argparse`, `os`, `re`, `difflib`, `unittest`). Mesmo estilo dos scripts existentes (`pegar_imagens.py`, `pegar_titulos.py`).

**Spec:** `docs/superpowers/specs/2026-04-28-paleta-de-cores-design.md`

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `migracao-wiki/aplicar_paleta.py` | CLI principal: parse args, orquestra login → criar template → editar páginas |
| `migracao-wiki/test_aplicar_paleta.py` | Testes unitários da função de substituição |
| `docs/superpowers/specs/2026-04-28-paleta-de-cores-design.md` | (já existe — referência) |

Credenciais: **nunca** em arquivo. Lidas das variáveis de ambiente `FANDOM_BOT_USER` e `FANDOM_BOT_PASS` definidas pelo usuário no shell.

---

## Pré-requisitos (operacionais, antes da Task 1)

O usuário precisa fazer **antes** de rodar o script:

1. Logado na conta Fandom, ir em `Special:BotPasswords` (`https://dragonexperience.fandom.com/pt-br/wiki/Special:BotPasswords`)
2. Criar bot novo com nome `paleta` (ou similar)
3. Marcar grants: `Edit existing pages`, `Create, edit, and move pages`
4. Salvar — Fandom mostra `username` (formato `MarcoTulio@paleta`) e `password` (string longa, gerada uma vez)
5. No shell desta sessão, exportar:
   ```bash
   export FANDOM_BOT_USER='MarcoTulio@paleta'
   export FANDOM_BOT_PASS='<a-string-gerada-pela-fandom>'
   ```

Essas variáveis são lidas pelo script. Não vão pro git, não passam por mim em nenhum momento.

---

## Task 1: Estrutura inicial e parsing de argumentos

**Files:**
- Create: `migracao-wiki/aplicar_paleta.py`

- [ ] **Step 1: Criar arquivo com shell skeleton**

Conteúdo de `migracao-wiki/aplicar_paleta.py`:

```python
"""Aplica a paleta centralizada (Predefinição:Cor) na wiki Fandom Dragon Experience.

Pré-condição: variáveis de ambiente FANDOM_BOT_USER e FANDOM_BOT_PASS setadas
(criar em Special:BotPasswords). Modo padrão é --dry-run; passe --apply para
realmente editar.
"""
import argparse
import os
import sys


API = "https://dragonexperience.fandom.com/pt-br/api.php"

# Mapeamento de cor -> chave no Predefinição:Cor.
# Hex em lowercase (find é case-insensitive).
COR_MAP = {
    "b38600": "principal",
    "fff9e6": "fundo-claro",
    "ffecb3": "fundo-medio",
    "262626": "texto",
}

# Templates a atualizar (nomes na Fandom — namespace Predefinição/Template).
TEMPLATES = [
    "LinhaCap",
    "Top Bar",
    "Table-Intro",
    "Table-Antagonistas",
    "Personagens Principais",
    "Personagens Secundários",
]

# Páginas com hardcode inline (espaço principal).
PAGINAS = [
    '"Entre a Vida e as Flores: Uma História em 7 Atos" (1x7)',
    "Grupo Marcial",
    "Especiais",
    "Livros de Lorelheim",
    "Personagens Principais",
    "Personagens Estilhaços da Guerra",
    "Personagens Night Sun",
    "Wiki Dragon Experience",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica de verdade. Sem essa flag, roda em dry-run.",
    )
    args = parser.parse_args()

    user = os.environ.get("FANDOM_BOT_USER")
    pwd = os.environ.get("FANDOM_BOT_PASS")
    if not user or not pwd:
        print("ERRO: defina FANDOM_BOT_USER e FANDOM_BOT_PASS no env.", file=sys.stderr)
        return 2

    modo = "APPLY" if args.apply else "DRY-RUN"
    print(f"Modo: {modo}")
    print(f"Usuário: {user}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verificar que script roda sem credenciais**

Run: `cd /Users/inco/mark/wiki-dragon-experience/migracao-wiki && python3 aplicar_paleta.py`
Expected: saída `ERRO: defina FANDOM_BOT_USER e FANDOM_BOT_PASS no env.` e exit code 2.

- [ ] **Step 3: Verificar que script roda com env vars dummy**

Run: `cd /Users/inco/mark/wiki-dragon-experience/migracao-wiki && FANDOM_BOT_USER=dummy FANDOM_BOT_PASS=dummy python3 aplicar_paleta.py`
Expected: imprime `Modo: DRY-RUN` e `Usuário: dummy`. Exit 0.

- [ ] **Step 4: Não comitar ainda** — commits ficam pra fim de todas as tasks; usuário pediu pra revisar antes.

---

## Task 2: Função `substituir_cores` com testes

**Files:**
- Modify: `migracao-wiki/aplicar_paleta.py` (adicionar função)
- Create: `migracao-wiki/test_aplicar_paleta.py`

- [ ] **Step 1: Escrever os testes primeiro**

Criar `migracao-wiki/test_aplicar_paleta.py`:

```python
"""Testes de substituir_cores."""
import unittest

from aplicar_paleta import substituir_cores


class TestSubstituirCores(unittest.TestCase):
    def test_substitui_cor_principal_lowercase(self) -> None:
        entrada = 'style="border: 2px solid #b38600;"'
        esperado = 'style="border: 2px solid #{{Cor|principal}};"'
        self.assertEqual(substituir_cores(entrada), esperado)

    def test_substitui_caso_uppercase(self) -> None:
        entrada = "color:#B38600"
        esperado = "color:#{{Cor|principal}}"
        self.assertEqual(substituir_cores(entrada), esperado)

    def test_substitui_caso_mixed(self) -> None:
        entrada = "background: #FfEcB3"
        esperado = "background: #{{Cor|fundo-medio}}"
        self.assertEqual(substituir_cores(entrada), esperado)

    def test_substitui_todas_quatro_cores(self) -> None:
        entrada = (
            'style="border:#b38600;background:#fff9e6;color:#262626;'
            "outline:#ffecb3;\""
        )
        resultado = substituir_cores(entrada)
        self.assertIn("{{Cor|principal}}", resultado)
        self.assertIn("{{Cor|fundo-claro}}", resultado)
        self.assertIn("{{Cor|texto}}", resultado)
        self.assertIn("{{Cor|fundo-medio}}", resultado)
        # nenhum hex remanescente
        for hex_ in ("b38600", "fff9e6", "262626", "ffecb3"):
            self.assertNotIn(hex_, resultado.lower())

    def test_nao_toca_em_outros_hex(self) -> None:
        entrada = "color:#ff0000;border:#b38600;"
        resultado = substituir_cores(entrada)
        self.assertIn("#ff0000", resultado)
        self.assertIn("{{Cor|principal}}", resultado)

    def test_idempotente(self) -> None:
        # rodar duas vezes não duplica substituição
        entrada = "color:#b38600"
        uma_vez = substituir_cores(entrada)
        duas_vezes = substituir_cores(uma_vez)
        self.assertEqual(uma_vez, duas_vezes)

    def test_preserva_texto_sem_cores(self) -> None:
        entrada = "{{Capítulo|title1=Foo|capítulo=[[Parte 1]]}}"
        self.assertEqual(substituir_cores(entrada), entrada)

    def test_match_com_hash(self) -> None:
        # Só substitui quando tem #. Hex sem # não é cor.
        entrada = "version b38600 build"
        self.assertEqual(substituir_cores(entrada), entrada)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes (devem falhar)**

Run: `cd /Users/inco/mark/wiki-dragon-experience/migracao-wiki && python3 -m unittest test_aplicar_paleta.py -v`
Expected: 8 testes, todos com erro `ImportError: cannot import name 'substituir_cores'`.

- [ ] **Step 3: Implementar `substituir_cores`**

Em `migracao-wiki/aplicar_paleta.py`, adicionar antes de `main()`:

```python
import re


_HEX_PATTERN = re.compile(r"#([0-9a-fA-F]{6})")


def substituir_cores(texto: str) -> str:
    """Substitui hex-codes da paleta por chamadas {{Cor|chave}}.

    Case-insensitive nos 6 hex digits. Só substitui quando precedido de '#'.
    Idempotente: rodar duas vezes dá o mesmo resultado.
    """

    def repl(m: re.Match[str]) -> str:
        hex_lower = m.group(1).lower()
        chave = COR_MAP.get(hex_lower)
        if chave is None:
            return m.group(0)
        return "#{{Cor|" + chave + "}}"

    return _HEX_PATTERN.sub(repl, texto)
```

- [ ] **Step 4: Rodar testes — todos devem passar**

Run: `cd /Users/inco/mark/wiki-dragon-experience/migracao-wiki && python3 -m unittest test_aplicar_paleta.py -v`
Expected: `Ran 8 tests in 0.00X s\n\nOK`.

---

## Task 3: Cliente Fandom — login + CSRF token

**Files:**
- Modify: `migracao-wiki/aplicar_paleta.py`

- [ ] **Step 1: Adicionar cliente HTTP com cookies**

Em `aplicar_paleta.py`, adicionar imports no topo:

```python
import http.cookiejar
import json
import urllib.parse
import urllib.request
```

E adicionar antes de `main()`:

```python
class FandomClient:
    """Cliente mínimo para api.php da Fandom com sessão e CSRF token."""

    def __init__(self, api: str, user: str, pwd: str) -> None:
        self.api = api
        self.user = user
        self.pwd = pwd
        cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookies)
        )
        self.opener.addheaders = [("User-Agent", "DragonExp-PaletaBot/1.0")]
        self.csrf_token: str | None = None

    def _post(self, params: dict[str, str]) -> dict:
        data = urllib.parse.urlencode(params).encode("utf-8")
        with self.opener.open(self.api, data=data, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def _get(self, params: dict[str, str]) -> dict:
        url = self.api + "?" + urllib.parse.urlencode(params)
        with self.opener.open(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def login(self) -> None:
        """Login em duas etapas (token + clientlogin)."""
        # 1) pegar logintoken
        r = self._get(
            {
                "action": "query",
                "meta": "tokens",
                "type": "login",
                "format": "json",
            }
        )
        login_token = r["query"]["tokens"]["logintoken"]

        # 2) clientlogin (BotPasswords usam clientlogin com loginreturnurl)
        r = self._post(
            {
                "action": "login",
                "lgname": self.user,
                "lgpassword": self.pwd,
                "lgtoken": login_token,
                "format": "json",
            }
        )
        result = r.get("login", {}).get("result")
        if result != "Success":
            raise RuntimeError(f"Login falhou: {r}")

        # 3) pegar CSRF token
        r = self._get(
            {
                "action": "query",
                "meta": "tokens",
                "format": "json",
            }
        )
        self.csrf_token = r["query"]["tokens"]["csrftoken"]
        if not self.csrf_token or self.csrf_token == "+\\":
            raise RuntimeError("CSRF token vazio — login provavelmente não pegou.")

    def get_wikitext(self, title: str) -> str | None:
        """Retorna o wikitext atual da página, ou None se não existir."""
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
        return pages[0]["revisions"][0]["slots"]["main"]["content"]

    def edit(self, title: str, text: str, summary: str) -> dict:
        """Edita ou cria a página. Retorna o JSON de resposta da API."""
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
```

- [ ] **Step 2: Integrar com `main()` — substituir o stub**

Substituir o corpo de `main()` (depois da checagem de env vars) por:

```python
    client = FandomClient(API, user, pwd)
    print(f"Logando como {user}...")
    client.login()
    print("Login OK. CSRF token obtido.")

    modo = "APPLY" if args.apply else "DRY-RUN"
    print(f"Modo: {modo}")

    # próximas tasks adicionam: criar Predefinição:Cor + processar TEMPLATES + PAGINAS
    return 0
```

- [ ] **Step 3: Smoke test do login (precisa das credenciais reais)**

Run: `cd /Users/inco/mark/wiki-dragon-experience/migracao-wiki && python3 aplicar_paleta.py`
Expected: `Logando como MarcoTulio@paleta...\nLogin OK. CSRF token obtido.\nModo: DRY-RUN`. Exit 0.

Se falhar com `Login falhou`, verificar:
- Bot password ainda válido (`Special:BotPasswords`)?
- Username inclui o `@<botname>`?
- Bot tem grants `editpage` e `createeditmovepage`?

---

## Task 4: Dry-run mostra diffs sem editar

**Files:**
- Modify: `migracao-wiki/aplicar_paleta.py`

- [ ] **Step 1: Adicionar função de processamento e diff**

Em `aplicar_paleta.py`, adicionar imports:

```python
import difflib
```

E adicionar antes de `main()`:

```python
TEMPLATE_COR_CONTEUDO = """<includeonly>{{#switch:{{{1}}}
|principal=b38600
|fundo-claro=fff9e6
|fundo-medio=ffecb3
|texto=262626
}}</includeonly><noinclude>
Paleta central da wiki. Edite aqui pra trocar o tema visual.

Uso: <code>style="color:#{{Cor|principal}}"</code>

{| class="wikitable"
! Chave !! Hex !! Papel
|-
| principal || b38600 || bordas e títulos (dourado)
|-
| fundo-claro || fff9e6 || fundo bege claro
|-
| fundo-medio || ffecb3 || fundo bege médio
|-
| texto || 262626 || texto cinza-escuro
|}
</noinclude>"""

EDIT_SUMMARY = "Centraliza paleta de cores via Predefinição:Cor"


def mostrar_diff(titulo: str, antes: str, depois: str) -> bool:
    """Imprime diff. Retorna True se houve mudança."""
    if antes == depois:
        print(f"  [skip] {titulo} — sem mudanças")
        return False
    diff = difflib.unified_diff(
        antes.splitlines(keepends=True),
        depois.splitlines(keepends=True),
        fromfile=f"{titulo} (antes)",
        tofile=f"{titulo} (depois)",
        n=1,
    )
    print(f"  [diff] {titulo}")
    sys.stdout.writelines(diff)
    print()
    return True


def processar_paginas(
    client: FandomClient,
    titulos: list[str],
    namespace_label: str,
    dry_run: bool,
) -> tuple[int, int]:
    """Processa lista de títulos. Retorna (mudadas, sem_mudanca)."""
    mudadas, iguais = 0, 0
    for titulo in titulos:
        full_title = (
            f"Predefinição:{titulo}" if namespace_label == "template" else titulo
        )
        wikitext = client.get_wikitext(full_title)
        if wikitext is None:
            print(f"  [WARN] {full_title} — página não existe; pulando")
            continue
        novo = substituir_cores(wikitext)
        mudou = mostrar_diff(full_title, wikitext, novo)
        if not mudou:
            iguais += 1
            continue
        mudadas += 1
        if not dry_run:
            client.edit(full_title, novo, EDIT_SUMMARY)
            print(f"  [APPLY] {full_title} editado.")
    return mudadas, iguais
```

- [ ] **Step 2: Atualizar `main()` para chamar processar**

Substituir o corpo de `main()` (depois do print de modo) por:

```python
    print("\n=== Predefinição:Cor ===")
    cor_existente = client.get_wikitext("Predefinição:Cor")
    if cor_existente is None:
        print("  [diff] Predefinição:Cor (nova)")
        print(TEMPLATE_COR_CONTEUDO[:200] + "..." if len(TEMPLATE_COR_CONTEUDO) > 200 else TEMPLATE_COR_CONTEUDO)
        if args.apply:
            client.edit("Predefinição:Cor", TEMPLATE_COR_CONTEUDO, EDIT_SUMMARY)
            print("  [APPLY] Predefinição:Cor criado.")
    else:
        print("  [skip] Predefinição:Cor já existe; não sobrescrevo.")

    print("\n=== Templates ===")
    t_mudadas, t_iguais = processar_paginas(client, TEMPLATES, "template", not args.apply)

    print("\n=== Páginas ===")
    p_mudadas, p_iguais = processar_paginas(client, PAGINAS, "page", not args.apply)

    print(f"\nResumo: {t_mudadas + p_mudadas} mudada(s), {t_iguais + p_iguais} sem mudança.")
    if not args.apply:
        print("Dry-run. Rode com --apply para efetivar.")
    return 0
```

- [ ] **Step 3: Rodar dry-run e validar**

Run: `cd /Users/inco/mark/wiki-dragon-experience/migracao-wiki && python3 aplicar_paleta.py 2>&1 | tee /tmp/dryrun.log`
Expected:
- Login OK.
- Mostra que `Predefinição:Cor` é novo.
- 6 templates com diffs (todos contendo substituições `#b38600` → `#{{Cor|principal}}` etc).
- 8 páginas com diffs.
- Resumo final do tipo `15 mudada(s), 0 sem mudança.`.
- Mensagem "Dry-run. Rode com --apply..."

- [ ] **Step 4: Inspecionar `/tmp/dryrun.log` manualmente**

Verificar visualmente que:
- Os diffs em `Predefinição:Top Bar` e `Predefinição:LinhaCap` mostram trocas corretas.
- Nenhuma página listada como `[WARN] página não existe`.
- Nenhuma cor da paleta aparece literal nas linhas `+` (linhas adicionadas).

Se algo estranho — pausar e investigar antes de seguir.

---

## Task 5: Backup e aplicação real

**Files:**
- Não cria. Operação manual + execução.

- [ ] **Step 1: Backup do dump.xml atual**

Run:
```bash
cd /Users/inco/mark/wiki-dragon-experience/migracao-wiki && \
cp dump.xml "dump.xml.bak-pre-paleta-$(date +%Y%m%d-%H%M%S)"
```
Expected: arquivo de backup criado.

- [ ] **Step 2: Aplicação real**

Run: `cd /Users/inco/mark/wiki-dragon-experience/migracao-wiki && python3 aplicar_paleta.py --apply 2>&1 | tee /tmp/apply.log`
Expected:
- Mensagens `[APPLY] <titulo> editado.` para cada uma das ~15 páginas.
- Resumo final.
- Exit 0.

- [ ] **Step 3: Verificação visual na Fandom**

Abrir no navegador (uma a uma):
- `https://dragonexperience.fandom.com/pt-br/wiki/Predefinição:Cor` — confirma que template foi criado e exibe a tabela de paleta.
- `https://dragonexperience.fandom.com/pt-br/wiki/Predefinição:Top_Bar` — verificar wikitext (botão "Editar" ou `?action=raw`) e ver `{{Cor|principal}}` no lugar de `b38600`.
- `https://dragonexperience.fandom.com/pt-br/wiki/Wiki_Dragon_Experience` (página inicial) — render visual continua idêntico ao anterior.
- `https://dragonexperience.fandom.com/pt-br/wiki/Personagens_Principais` — render visual igual.
- Qualquer capítulo (ex: `1x1`) que use `LinhaCap` indiretamente via tabela — render igual.

Se algum render quebrou:
- Verificar `?action=purge` na página afetada (forçar recompile).
- Se ainda quebrar, reverter via histórico (`Special:Histórico/<página>` → `desfazer`).

- [ ] **Step 4: Sanity-check pós-aplicação**

Rodar dry-run de novo:

Run: `cd /Users/inco/mark/wiki-dragon-experience/migracao-wiki && python3 aplicar_paleta.py 2>&1 | tail -5`
Expected: `Resumo: 0 mudada(s), 14 sem mudança.` (idempotência confirmada — nada mais a substituir).

---

## Task 6: Commit do código (opcional, quando usuário aprovar)

**Files:**
- Add: `migracao-wiki/aplicar_paleta.py`, `migracao-wiki/test_aplicar_paleta.py`
- Add: `docs/superpowers/specs/2026-04-28-paleta-de-cores-design.md`
- Add: `docs/superpowers/plans/2026-04-28-paleta-de-cores-fandom.md`

- [ ] **Step 1: Pedir confirmação explícita**

Não comitar nada sem o usuário pedir. Quando ele pedir:

```bash
cd /Users/inco/mark/wiki-dragon-experience && \
git add migracao-wiki/aplicar_paleta.py migracao-wiki/test_aplicar_paleta.py \
        docs/superpowers/specs/2026-04-28-paleta-de-cores-design.md \
        docs/superpowers/plans/2026-04-28-paleta-de-cores-fandom.md && \
git commit -m "$(cat <<'EOF'
feat(migracao): script de centralização de paleta de cores na Fandom

Cria Predefinição:Cor com 4 cores temáticas e atualiza 6 templates +
8 páginas pra usarem {{Cor|chave}} em vez de hex hardcoded. Inclui
spec, plano e testes unitários da função de substituição.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Notas operacionais

- **Idempotência**: `substituir_cores` é idempotente. Rodar `--apply` duas vezes não duplica nada.
- **Cache da Fandom**: edições em template podem demorar minutos a aparecer em páginas que usam o template. Usar `?action=purge` na página se precisar.
- **Rate limiting**: ~15 edições muito abaixo do limite. Não precisa flag de bot. Mas se Fandom retornar `error.code = "ratelimited"`, o script falha visivelmente — adicionar `time.sleep(2)` entre edits no loop seria fácil mitigação (omitido pra manter simples).
- **Reversão**: cada edit gera revisão. Pra reverter, `Special:Histórico/<página>` → `desfazer`. Pra reverter em massa, manualmente uma a uma, ou rodar script inverso (não incluso aqui).
- **PortableInfobox**: as infoboxes (`Personagem`, `Capítulo`, etc) **não** entram no escopo deste plano — elas não usam essas cores diretamente em XML; o styling vem de CSS separado. Se quiser temar elas no futuro, é trabalho separado em `MediaWiki:Common.css`.
