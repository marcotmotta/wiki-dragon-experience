import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import style from "./styles/infobox.scss"
import { QuartzPluginData } from "../plugins/vfile"
import { resolveRelative, FullSlug } from "../util/path"
import { classNames } from "../util/lang"

type Schema = { label: string; source: string }[]

// Schemas derivados dos templates Fandom em migracao-wiki/templates/*.wiki
// Ordem preservada da ordem do <data source="..."> original.
// Para o demo incluí apenas PC/NPC/capítulo; outros tipos serão adicionados na migração completa.
const SCHEMAS: Record<string, Schema> = {
  PC: [
    { source: "jogador", label: "Jogador" },
    { source: "campanha", label: "Campanha" },
    { source: "nome", label: "Nome" },
    { source: "nascimento", label: "Nascimento" },
    { source: "morte", label: "Morte" },
    { source: "título", label: "Título" },
    { source: "conhecido_como", label: "Também Conhecido Como" },
    { source: "criatura", label: "Criatura" },
    { source: "raça", label: "Raça" },
    { source: "classe", label: "Classe" },
    { source: "classificação", label: "Classificação" },
    { source: "tendência", label: "Tendência" },
    { source: "idiomas", label: "Idiomas" },
    { source: "plano", label: "Plano" },
    { source: "lugares", label: "Lugares" },
    { source: "família", label: "Família" },
    { source: "conexões", label: "Conexões" },
    { source: "inimigos", label: "Inimigos" },
    { source: "profissão", label: "Profissão" },
    { source: "visto_pela_primeira_vez", label: "Visto Pela Primeira Vez" },
    { source: "nível", label: "Nível" },
  ],
  NPC: [
    // mesmo schema de PC, mas "jogador" normalmente ausente
    { source: "campanha", label: "Campanha" },
    { source: "nome", label: "Nome" },
    { source: "nascimento", label: "Nascimento" },
    { source: "morte", label: "Morte" },
    { source: "título", label: "Título" },
    { source: "conhecido_como", label: "Também Conhecido Como" },
    { source: "criatura", label: "Criatura" },
    { source: "raça", label: "Raça" },
    { source: "classe", label: "Classe" },
    { source: "tendência", label: "Tendência" },
    { source: "idiomas", label: "Idiomas" },
    { source: "lugares", label: "Lugares" },
    { source: "família", label: "Família" },
    { source: "conexões", label: "Conexões" },
    { source: "inimigos", label: "Inimigos" },
    { source: "profissão", label: "Profissão" },
    { source: "visto_pela_primeira_vez", label: "Visto Pela Primeira Vez" },
    { source: "nível", label: "Nível" },
  ],
  capítulo: [
    { source: "capítulo", label: "Capítulo" },
    { source: "data", label: "Data" },
    { source: "pcs", label: "PCs" },
    { source: "npcs_marcantes", label: "NPCs Principais" },
    { source: "npcs_secundários", label: "NPCs Secundários" },
    { source: "lugares", label: "Lugares" },
    { source: "capítulo_anterior", label: "Anterior" },
    { source: "próximo_capítulo", label: "Próximo" },
  ],
}

const WIKILINK_RE = /\[\[([^\[\]|]+)(?:\|([^\[\]]+))?\]\]/g

/**
 * Renderiza um valor do frontmatter (string, lista ou número) resolvendo
 * wikilinks [[X]] para links reais ancorados via allFiles.
 */
function renderValue(
  value: unknown,
  currentSlug: FullSlug,
  allFiles: QuartzPluginData[],
): (string | JSX.Element)[] {
  if (Array.isArray(value)) {
    const out: (string | JSX.Element)[] = []
    value.forEach((v, i) => {
      if (i > 0) out.push(<br />)
      out.push(...renderValue(v, currentSlug, allFiles))
    })
    return out
  }
  const str = String(value ?? "")
  if (!str) return []

  const parts: (string | JSX.Element)[] = []
  let lastIdx = 0
  for (const m of str.matchAll(WIKILINK_RE)) {
    const [full, target, alias] = m
    const start = m.index ?? 0
    if (start > lastIdx) parts.push(str.slice(lastIdx, start))

    // tenta encontrar o arquivo por slug. Quartz slugifica espaços para "-",
    // então "Eryn Montreal" precisa bater contra base "Eryn-Montreal".
    const target_simple = target.trim()
    const target_slugified = target_simple.replace(/ /g, "-")
    const match = allFiles.find((f) => {
      if (!f.slug) return false
      const base = f.slug.split("/").pop() ?? f.slug
      const fmTitle = (f.frontmatter?.title ?? f.frontmatter?.nome) as string | undefined
      return (
        base === target_simple ||
        base === target_slugified ||
        f.slug === target_simple ||
        fmTitle === target_simple
      )
    })
    const displayText =
      alias?.trim() ?? (match?.frontmatter?.title as string | undefined) ?? target_simple
    if (match?.slug) {
      parts.push(
        <a href={resolveRelative(currentSlug, match.slug)} class="internal">
          {displayText}
        </a>,
      )
    } else {
      // link quebrado: ainda emite <a> pra consistência visual + navegação eventual
      parts.push(
        <a href={`./${target_slugified}`} class="internal broken">
          {displayText}
        </a>,
      )
    }
    lastIdx = start + full.length
  }
  if (lastIdx < str.length) parts.push(str.slice(lastIdx))
  return parts
}

const Infobox: QuartzComponent = ({ fileData, allFiles, displayClass }: QuartzComponentProps) => {
  const fm = fileData.frontmatter as Record<string, unknown> | undefined
  if (!fm) return null
  const tipo = fm.tipo as string | undefined
  if (!tipo) return null
  const schema = SCHEMAS[tipo]
  if (!schema) return null

  const title = (fm.title ?? fm.titulo ?? fm.nome) as string | undefined
  const rows = schema
    .map((field) => ({ field, value: fm[field.source] }))
    .filter(({ value }) => value !== undefined && value !== null && value !== "")

  if (rows.length === 0) return null

  const image = fm.image as string | undefined
  const imageCaption = fm.image_caption as string | undefined
  const imageSrc = image
    ? resolveRelative(fileData.slug!, `attachments/${image}` as FullSlug)
    : null

  return (
    <aside class={classNames(displayClass, "infobox")}>
      <div class="infobox-header">
        {title}
        <div class="infobox-tipo">{tipo}</div>
      </div>
      {imageSrc && (
        <div class="infobox-image">
          <img src={imageSrc} alt={imageCaption ?? title ?? ""} />
          {imageCaption && <div class="infobox-caption">{imageCaption}</div>}
        </div>
      )}
      <table>
        <tbody>
          {rows.map(({ field, value }) => (
            <tr>
              <th scope="row">{field.label}</th>
              <td>{renderValue(value, fileData.slug!, allFiles)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </aside>
  )
}

Infobox.css = style

export default (() => Infobox) satisfies QuartzComponentConstructor
