# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

This repo is a fork of [Quartz v4](https://quartz.jzhao.xyz/) used to publish the **Dragon Experience** wiki — a D&D campaign wiki in **Portuguese (pt-BR)** originally hosted at `dragonexperience.fandom.com/pt-br` — as a static site on GitHub Pages at `marcotmotta.github.io/wiki-dragon-experience`.

The codebase has two distinct layers:

1. **Upstream Quartz** (`quartz/`, most of `package.json`, upstream workflows, etc.) — vendored from `jackyzha0/quartz`. Treat it as a dependency: do **not** modify files under `quartz/` casually; prefer configuration in `quartz.config.ts` / `quartz.layout.ts` or custom components.
2. **This wiki's own work** — so far, three commits authored by the repo owner:
   - `1132933` Setup inicial — populated `quartz.config.ts` (title, locale pt-BR, baseUrl, theme)
   - `6d4f045` Replaced the four upstream workflows (`ci.yaml`, `build-preview.yaml`, `deploy-preview.yaml`, `docker-build-push.yaml`) with a single custom `.github/workflows/deploy.yml`
   - `0f204b1` `migration test` — added `migracao-wiki/` and the first 12 migrated content files

Everything else in `git log` is upstream Quartz history. When pulling upstream updates (`npx quartz update`), expect conflicts centered on these three commits — especially workflows and `quartz.config.ts`.

## Commands

Requires Node 24+ and npm 11.12.1+ (see `.node-version` and `engines` in `package.json`).

```bash
npm ci                      # install deps (required before any quartz command)

npx quartz build            # build static site into ./public
npx quartz build --serve    # dev server with hot reload (default http://localhost:8080)
npx quartz update           # pull latest upstream Quartz changes
npx quartz sync             # sync content with GitHub remote

npm run check               # tsc --noEmit + prettier --check
npm run format              # prettier --write
npm test                    # tsx --test (runs *.test.ts via node:test)
```

Run a single test: `npx tsx --test path/to/file.test.ts`.

Deploy is automatic: any push to `main` triggers `.github/workflows/deploy.yml`, which runs `npm ci && npx quartz build` and publishes `./public` to GitHub Pages.

## Content architecture (`content/`)

The wiki source. Obsidian-flavored markdown processed by `Plugin.ObsidianFlavoredMarkdown` + `Plugin.GitHubFlavoredMarkdown` (see `quartz.config.ts`). All content uses pt-BR.

Folder conventions (enforced by convention, not code):

- `content/Campanhas/` — one file per campaign (e.g. `Campanha 1.md`)
- `content/Capítulos/` — episodes named by code `{campanha}x{episódio}.md` (e.g. `1x1.md`, `2x15.md`)
- `content/Personagens/` — NPCs/PCs
- `content/Locais/` — places
- `content/index.md` — wiki home
- `content/Todos os Capítulos.md` — index page

### Frontmatter schema

Not enforced by a schema file — these are the fields **actually used** in existing content. Preserve and extend this vocabulary when adding new content.

**Capítulo:** `tipo: capítulo`, `titulo`, `codigo`, `aliases`, `numero_global`, `campanha`, `numero_na_campanha`, `arco`, `numero_no_arco`, `data` (ISO), `personagens` (wikilink list), `locais`, `tags` (include `campanha-N`).

**Personagem:** `tipo: personagem`, `nome`, `aliases`, `raça`, `classe`, `status`, `grupo` (wikilink), `primeira_aparição` (wikilink), `campanhas`, `tags`.

**Local / Campanha:** similar patterns; see `content/Locais/Bosque do Retorno.md` and `content/Campanhas/Campanha 1.md` for current shape.

Body commonly uses Obsidian callouts (`> [!info] Sinopse`), wikilinks (`[[Daniel]]`, `[[1x1|"Ataque Surpresa" (1x1)]]`), and inline tables. Dataview queries appear in some source files — Quartz does **not** execute dataview, so convert to static markdown or a custom Quartz component before relying on them in the published site.

`ignorePatterns` in `quartz.config.ts` excludes `private`, `templates`, `.obsidian`.

## Migration from Fandom (`migracao-wiki/`)

This is the active, unfinished work. The current 12 content files were produced manually; the bulk migration from MediaWiki dump is pending.

- `dump.xml` — full MediaWiki export from `dragonexperience.fandom.com/pt-br`
- `pegar_titulos.py` — lists all page titles via Fandom's `allpages` API
- `pegar_imagens.py` — downloads all images via `allimages` API into `images/`
- `analisar_templates.py` — scans the dump for MediaWiki templates and counts usage
- `relatorio_templates.txt` — inventory: **33 distinct templates** to translate to markdown. The heaviest are `Cp` (487 uses, 211 pages), `LinhaCap` (195/12), `Personagem` (141/141), `Capítulo` (101/100), `Quote box` (69/52), `Referências` (29/29). Each template with `usos >> páginas` is a cross-reference primitive — the conversion must resolve these into wikilinks, not just strip them.

When extending migration tooling, keep scripts here (Python 3) — they are independent of the Quartz build.

## Upstream divergence to watch

Three files are expected to conflict with upstream pulls:

- `.github/workflows/` — upstream has `ci.yaml`, `build-preview.yaml`, `deploy-preview.yaml`, `docker-build-push.yaml`; this repo has only a custom `deploy.yml`. When resolving, **keep** the custom `deploy.yml`.
- `quartz.config.ts` — carries site identity (title, locale, baseUrl, theme). Merge upstream plugin changes, keep the local `configuration` block.
- `content/` and `migracao-wiki/` — not present upstream; always keep local.
