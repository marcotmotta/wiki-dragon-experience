# Wiki Dragon Experience

Fork do [Quartz v4](https://quartz.jzhao.xyz/) que publica a wiki da campanha de D&D **Dragon Experience** (pt-BR) como site estático em GitHub Pages, com o conteúdo migrado de `dragonexperience.fandom.com/pt-br`.

O conteúdo em `content/` é **gerado** — a fonte de verdade é a wiki na Fandom, e os scripts em `migracao-wiki/` (Python 3) fazem a ponte. Editar `content/` na mão não adianta: a próxima rodada do conversor sobrescreve.

---

## Atualizar o conteúdo com o da wiki

O caminho principal. Rode os quatro passos na ordem — o passo 3 depende do 2, porque ele varre o que o conversor acabou de escrever.

```bash
cd migracao-wiki

python3 pegar_paginas.py     # 1. Fandom → dump.xml + templates/*.wiki
python3 converter.py         # 2. dump.xml → content/**/*.md
python3 pegar_imagens.py     # 3. imagens novas → content/attachments/

cd .. && npx quartz build --serve   # 4. confere em http://localhost:8080
```

Depois: `git add`, commit e push na `main` — o deploy é automático (veja [Publicar](#publicar)).

### O que cada passo faz

**1. `pegar_paginas.py`** — baixa todas as páginas via API (namespaces 0/10/14/6) e regrava `dump.xml` no schema `export-0.11`, que é o que o conversor parseia. De quebra espelha cada Predefinição (ns=10) em `templates/*.wiki`.

Esse espelhamento não é detalhe: o `converter.py` lê `templates/Cp.wiki` como fonte de `numero_global` e `parte` de cada capítulo. Se o Cp sair de sincronia com a wiki, capítulos novos somem ou saem numerados errado.

Faz backup em `dump.xml.bak-YYYYMMDD-HHMMSS` antes de sobrescrever (os `.bak-*` são gitignored).

**2. `converter.py`** — converte o wikitext em markdown Obsidian com frontmatter, roteando cada página pra sua pasta pelo template de infobox que ela usa (`Capítulo` → `content/Capítulos/`, `Personagem` → `PCs/` ou `NPCs/` conforme o campo `tipo`, `Cidade`/`Reino`/`Estabelecimento` → `Lugares/`, e assim por diante). Resolve redirects em `aliases` no frontmatter.

⚠️ **Apaga e regenera** todos os `.md` das pastas do modo antes de escrever. Qualquer edição manual se perde.

Aceita `--only` pra trabalhar num subconjunto (default `all`):

| Modo          | Pastas de destino                                              |
| ------------- | -------------------------------------------------------------- |
| `personagens` | `PCs/`, `NPCs/`                                                |
| `capitulos`   | `Capítulos/`                                                   |
| `partes`      | `Partes/`                                                      |
| `lugares`     | `Lugares/`                                                     |
| `grupos`      | `Grupos/`                                                      |
| `outros`      | `Outros/` (campanhas, diários, itens, magias, mundo, batalhas) |
| `all`         | todas                                                          |

**3. `pegar_imagens.py`** — varre `content/` atrás de referências a imagem (campo `image:` do frontmatter, `<img src>` legado e embeds Obsidian `![[foo.jpg|240]]`) e baixa da Fandom só o que ainda falta em `content/attachments/`. Idempotente.

Tem um segundo modo, `--all`, que é outra coisa: baixa a wiki inteira via `allimages` pra `migracao-wiki/images/`. Isso alimenta o `subir_miraheze.py`, **não** o site.

**4. Conferir** — `npx quartz build --serve` sobe o site local com hot reload. Vale também um `git status content/` pra ver o tamanho do estrago antes de commitar.

### Pendência conhecida

A Fandom serve arquivos com extensão `.png`/`.jpg` cujo conteúdo real é webp. O `normalizar_imagens.py` conserta isso, mas varre **apenas** `migracao-wiki/images/` — os arquivos de `content/attachments/`, que são os que o site publica, seguem todos como webp disfarçado.

---

## Publicar

Push na `main` dispara `.github/workflows/deploy.yml`, que roda `npm ci && npx quartz build` e publica `./public` no GitHub Pages.

Build local:

```bash
npm ci                    # obrigatório antes de qualquer comando quartz
npx quartz build          # gera ./public
npx quartz build --serve  # dev server com hot reload
npm run check             # tsc --noEmit + prettier --check
npm run format            # prettier --write
```

---

## Referência dos scripts

Todos vivem em `migracao-wiki/` e rodam com `python3 <script>` a partir dali.

Duas pegadinhas de caminho: os scripts do pipeline têm o caminho do repo **hardcoded** (`REPO = Path("/Users/inco/mark/wiki-dragon-experience")`), então clonar em outro lugar exige ajustar essa constante; e `analisar_templates.py` e `pegar_templates.py` leem `dump.xml` / `relatorio_templates.txt` relativos ao cwd, ou seja, precisam rodar de dentro de `migracao-wiki/`.

### Pipeline principal

| Script                  | O que faz                                                    | Flags                               |
| ----------------------- | ------------------------------------------------------------ | ----------------------------------- |
| `pegar_paginas.py`      | Fandom → `dump.xml` + `templates/*.wiki`                     | —                                   |
| `converter.py`          | `dump.xml` → `content/**/*.md`                               | `--only <modo>`                     |
| `pegar_imagens.py`      | Imagens de `content/` → `content/attachments/`               | `--from-content` (default), `--all` |
| `normalizar_imagens.py` | Converte webp disfarçado in-place em `migracao-wiki/images/` | —                                   |

### Análise

| Script                  | O que faz                                                                                      |
| ----------------------- | ---------------------------------------------------------------------------------------------- |
| `analisar_templates.py` | Conta uso de templates no `dump.xml` e imprime o inventário. Gerou o `relatorio_templates.txt` |

### Escrita em wiki remota

Escrevem em servidor de verdade. Ambos rodam em **dry-run por padrão** — só `--apply` edita.

| Script              | O que faz                                                             | Credenciais                              |
| ------------------- | --------------------------------------------------------------------- | ---------------------------------------- |
| `aplicar_paleta.py` | Troca hex hardcoded por `{{Cor\|...}}` nos templates da Fandom        | `FANDOM_BOT_USER`, `FANDOM_BOT_PASS`     |
| `subir_miraheze.py` | Sobe `dump.xml` + `images/` pro Miraheze, na ordem ns 10 → 14 → 0 → 6 | `MIRAHEZE_BOT_USER`, `MIRAHEZE_BOT_PASS` |

`subir_miraheze.py` aceita ainda `--skip-pages` e `--skip-images` pra rodar só uma das fases, e loga tudo em `migracao.log` (append-only, gitignored).

Credenciais saem de variáveis de ambiente, nunca do código. Crie as senhas em `Special:BotPasswords` da wiki correspondente. **Nenhum script carrega o `.env` sozinho** — exporte antes:

```bash
set -a; source migracao-wiki/.env; set +a
```

### Legado

Superados, mantidos por referência: `pegar_templates.py` (incorporado ao `pegar_paginas.py`), `pegar_titulos.py` (só lista títulos, e é o único que precisa de `requests`), `pegar_imagens_demo.py` (do demo de 4 páginas).

### Testes

```bash
cd migracao-wiki
python3 test_aplicar_paleta.py
python3 test_subir_miraheze.py
```

`unittest` puro, sem dependência externa. Cobrem as funções puras — nada que fale com a rede.

---

## Requisitos

- **Node 24+** e **npm 11.12.1+** (veja `.node-version` e `engines` no `package.json`) — só pro Quartz
- **Python 3.10+** — os scripts usam só a biblioteca padrão (exceto `pegar_titulos.py`, legado, que quer `requests`)
- **macOS** pro `normalizar_imagens.py`, que depende do `sips`

---

## Estrutura

```
content/            # gerado pelo converter.py — não editar na mão
  Capítulos/  PCs/  NPCs/  Lugares/  Grupos/  Partes/  Outros/
  attachments/      # imagens que o site publica
migracao-wiki/      # scripts + insumos da migração
  dump.xml          # export da Fandom (fonte do converter)
  templates/        # Predefinições espelhadas da Fandom (*.wiki)
  images/           # espelho completo das imagens — insumo do Miraheze
quartz/             # upstream Quartz vendored — evite mexer
quartz.config.ts    # identidade do site (título, locale pt-BR, baseUrl, tema)
quartz.layout.ts    # layout
```

Documentação do Quartz em si: https://quartz.jzhao.xyz/
