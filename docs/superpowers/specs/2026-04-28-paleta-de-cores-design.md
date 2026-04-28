# Paleta de cores centralizada via Template:Cor

**Data:** 2026-04-28
**Escopo:** Wiki Dragon Experience na Fandom (`dragonexperience.fandom.com/pt-br`)
**Motivação:** as cores do tema visual da wiki estão hardcoded em dezenas de lugares (templates + páginas). Trocar o tema hoje exige busca-e-substitui em toda a wiki. Centralizar num template-variável reduz isso a uma edição.

## Problema

A wiki usa uma paleta consistente de 4 cores que viajam juntas:

| Hex | Papel | Onde aparece |
|---|---|---|
| `#b38600` | dourado/mostarda | bordas, títulos |
| `#fff9e6` | bege claríssimo | fundo de cards |
| `#ffecb3` | bege médio | fundo do Top Bar |
| `#262626` | cinza-escuro | texto |

Mapeamento atual (a partir de `migracao-wiki/dump.xml` e `migracao-wiki/templates/`):

- **6 templates** contêm referências hardcoded: `LinhaCap`, `Top Bar`, `Table-Intro`, `Table-Antagonistas`, `Personagens Principais` (este tem uma versão antiga comentada com `<!-- -->` no topo que também precisa ser atualizada, pra evitar ressurreição do hardcode caso alguém descomente), `Personagens Secundários`.
- **8 páginas de conteúdo** com hardcode inline (24 ocorrências de `#b38600` no total): `"Entre a Vida e as Flores: Uma História em 7 Atos" (1x7)`, `Grupo Marcial`, `Especiais`, `Livros de Lorelheim`, `Personagens Principais` (página, não template), `Personagens Estilhaços da Guerra`, `Personagens Night Sun`, `Wiki Dragon Experience`.

## Decisão

Criar um único template `Predefinição:Cor` que recebe a chave da cor e retorna o hex (sem `#`), implementado com `{{#switch}}`. Aplicar em todos os 6 templates e nas 8 páginas com hardcode (cobertura 100%).

### Por que essa abordagem

Avaliadas três alternativas:

- **A. Template único com `#switch`** *(escolhida)* — 1 arquivo, paleta inteira documentada num lugar, mesmo padrão do `Cp` (familiar).
- **B. Subtemplates separados** (`Cor/principal`, `Cor/fundo-claro`...) — evita corner case de pipe em sintaxe de tabela, mas espalha a paleta em 4 arquivos.
- **C. Classes CSS no `MediaWiki:Common.css`** — mais idiomático, mas exige reescrever todos os `style="..."` inline em classes (trabalho desproporcional pro benefício, e requer admin pra editar `Common.css`).

A escolheu-se A pelo equilíbrio entre simplicidade e centralização efetiva.

### Ergonomia já validada

- **Pipe em wikitext de tabela**: `{{Cor|principal}}` aparece dentro de `style="..."`, que é valor de atributo HTML — o pipe interno é interpretado como argumento do template, não separador de célula. Funciona.
- **Migração pro Miraheze**: o template é wikitext puro, vem no dump XML e funciona igual no Miraheze sem configuração extra (ParserFunctions já vem habilitado).

## Estrutura do Template:Cor

Conteúdo a ser criado em `Predefinição:Cor`:

```
<includeonly>{{#switch:{{{1}}}
|principal=b38600
|fundo-claro=fff9e6
|fundo-medio=ffecb3
|texto=262626
}}</includeonly><noinclude>
Paleta central da wiki. Edite aqui pra trocar o tema visual.

Uso: <code>style="color:#{{Cor|principal}}"</code>

| Chave | Hex | Papel |
|---|---|---|
| principal | b38600 | bordas e títulos (dourado) |
| fundo-claro | fff9e6 | fundo bege claro |
| fundo-medio | ffecb3 | fundo bege médio |
| texto | 262626 | texto cinza-escuro |
</noinclude>
```

Notas:
- Hex sem `#` — quem usa concatena `#{{Cor|...}}`. Isso permite o template ser usado também em contextos que não esperam `#` (raro, mas vale).
- Nomes de chave descrevem o **papel** (`principal`, `texto`), não a cor (`dourado`, `escuro`). Assim o nome continua válido depois de uma troca de tema.

## Plano de aplicação (visão geral)

| Etapa | Ação |
|---|---|
| 1 | Criar `Predefinição:Cor` na Fandom |
| 2 | Editar os 6 templates fazendo find/replace das 4 cores |
| 3 | Editar as 8 páginas com hardcode inline |
| 4 | Verificação visual de páginas-âncora (`Top Bar`, `Personagens Principais`, `Wiki Dragon Experience`, qualquer capítulo) |

Detalhes operacionais (qual ferramenta usar pra editar — manual via UI, pywikibot, API direto — e ordem das edições) ficam pra fase de plano de implementação.

### Substituições

| De | Para |
|---|---|
| `#b38600` | `#{{Cor\|principal}}` |
| `#fff9e6` | `#{{Cor\|fundo-claro}}` |
| `#ffecb3` | `#{{Cor\|fundo-medio}}` |
| `#262626` | `#{{Cor\|texto}}` |

Variações de caixa (`#B38600` etc) precisam ser tratadas — verificar antes de fazer find/replace cego.

## Critérios de sucesso

1. `Predefinição:Cor` existe na Fandom e renderiza `b38600` quando chamado com `{{Cor|principal}}`.
2. Nenhuma das 4 cores (`b38600`, `fff9e6`, `ffecb3`, `262626`) aparece literalmente em wikitext de templates ou páginas — a única fonte da verdade é o `Predefinição:Cor`.
3. Render visual de `Top Bar`, `Personagens Principais` (página) e qualquer capítulo continua idêntico ao estado anterior.
4. A mudança propaga via dump XML pro Miraheze sem ajuste adicional.

## Riscos e mitigações

- **Edição em massa fora de ordem**: criar `Predefinição:Cor` antes de qualquer página que o usa. Mitigação: ordem fixa de etapas (1 → 2 → 3).
- **Cache da Fandom**: alterações em template podem demorar a aparecer em páginas que o usam. Mitigação: forçar purge das páginas afetadas se necessário (`?action=purge`).
- **Variações de caixa do hex**: `#B38600` vs `#b38600` não casa em find/replace literal. Mitigação: rodar busca case-insensitive antes da substituição pra dimensionar e padronizar.
- **Outras cores escondidas**: o levantamento focou nessas 4. Pode haver outras cores menos óbvias (links, hovers). Mitigação: fora do escopo desta spec; se aparecerem, nova spec.

## Fora do escopo

- Refatorar pra classes CSS (Abordagem C).
- Criar variantes de tema (modo escuro, etc).
- Aplicar a mesma centralização nos arquivos já migrados em `content/` (Quartz usa sistema de tema próprio em `quartz.config.ts`, não wikitext).
