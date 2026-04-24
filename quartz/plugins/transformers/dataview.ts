import { QuartzTransformerPlugin } from "../types"
import fs from "fs"
import path from "path"
import matter from "gray-matter"

/**
 * Processa blocos ```dataview``` no markdown source e os substitui por uma
 * tabela markdown estática gerada executando a query contra o frontmatter
 * de todos os arquivos em content/.
 *
 * Alinha renderização Obsidian ↔ Quartz: o Obsidian renderiza a query via
 * plugin Dataview (live); o Quartz renderiza a tabela estática (substituição
 * feita aqui no textTransform, antes do parse do markdown).
 *
 * Suporta um subset DQL suficiente pros casos da wiki:
 *   TABLE [WITHOUT ID]
 *     col [AS "label"],
 *     link(path_expr, display_expr) [AS "label"],
 *     ...
 *   FROM "Pasta"
 *   WHERE field OP value
 *   SORT field ASC|DESC
 */

type Column = { expr: string; label: string }

type ParsedQuery = {
  withoutId: boolean
  columns: Column[]
  from: string | null
  where: string | null
  sortField: string | null
  sortDir: "ASC" | "DESC"
  limit: number | null
}

type Frontmatter = Record<string, unknown>
type FileData = { slug: string; fm: Frontmatter }

let cachedBuildId: string | null = null
let fileCache: FileData[] = []

function buildFileCache(contentDir: string): FileData[] {
  const out: FileData[] = []
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) {
        if (entry.name.startsWith(".") || entry.name === "node_modules") continue
        walk(full)
      } else if (entry.name.endsWith(".md")) {
        try {
          const { data } = matter(fs.readFileSync(full, "utf-8"))
          // slug relativo a content/, sem a extensão
          const rel = path.relative(contentDir, full).replace(/\.md$/, "")
          out.push({ slug: rel, fm: data as Frontmatter })
        } catch {
          // ignore
        }
      }
    }
  }
  walk(contentDir)
  return out
}

function parseColumns(src: string): Column[] {
  // Split on top-level commas (respeitando parens de funções tipo link(a, b))
  const cols: string[] = []
  let buf = ""
  let depth = 0
  for (const ch of src) {
    if (ch === "(") depth++
    else if (ch === ")") depth--
    else if (ch === "," && depth === 0) {
      if (buf.trim()) cols.push(buf.trim())
      buf = ""
      continue
    }
    buf += ch
  }
  if (buf.trim()) cols.push(buf.trim())

  return cols.map((c) => {
    const asMatch = c.match(/^(.+?)\s+AS\s+"([^"]+)"\s*$/i)
    if (asMatch) return { expr: asMatch[1].trim(), label: asMatch[2] }
    return { expr: c, label: c }
  })
}

function parseDQL(src: string): ParsedQuery | null {
  const text = src.trim()
  if (!/^TABLE\b/i.test(text)) return null // só TABLE por enquanto

  // Separa clausulas por regex multilinha — FROM/WHERE/SORT começam linha
  const sections: Record<string, string> = {}
  const keywords = ["FROM", "WHERE", "SORT", "GROUP BY", "LIMIT"]
  // marca início de cada cláusula
  let pointer = text
  const positions: Array<{ kw: string; pos: number }> = []
  for (const kw of keywords) {
    const re = new RegExp(`(^|\\n)\\s*${kw}\\b`, "i")
    const m = pointer.match(re)
    if (m && m.index !== undefined) {
      positions.push({ kw, pos: m.index + (m[1] ? m[1].length : 0) })
    }
  }
  positions.sort((a, b) => a.pos - b.pos)

  const tableEnd = positions[0]?.pos ?? text.length
  const tableRaw = text.slice(0, tableEnd)

  const withoutId = /WITHOUT\s+ID/i.test(tableRaw)
  const colsRaw = tableRaw
    .replace(/^TABLE\s+(WITHOUT\s+ID\s+)?/i, "")
    .trim()
  const columns = parseColumns(colsRaw)

  for (let i = 0; i < positions.length; i++) {
    const start = positions[i].pos
    const end = positions[i + 1]?.pos ?? text.length
    const kw = positions[i].kw.toUpperCase()
    sections[kw] = text.slice(start, end).replace(new RegExp(`^\\s*${kw}\\s*`, "i"), "").trim()
  }

  let from: string | null = null
  if (sections.FROM) {
    const m = sections.FROM.match(/^"([^"]+)"/)
    if (m) from = m[1]
  }

  const where = sections.WHERE || null

  let sortField: string | null = null
  let sortDir: "ASC" | "DESC" = "ASC"
  if (sections.SORT) {
    const m = sections.SORT.match(/^(\w+)\s*(ASC|DESC)?/i)
    if (m) {
      sortField = m[1]
      sortDir = ((m[2] ?? "ASC").toUpperCase()) as "ASC" | "DESC"
    }
  }

  let limit: number | null = null
  if (sections.LIMIT) {
    const m = sections.LIMIT.match(/^(\d+)/)
    if (m) limit = parseInt(m[1], 10)
  }

  return { withoutId, columns, from, where, sortField, sortDir, limit }
}

// Avalia expressão de coluna → string markdown pronta pra célula da tabela
function evalExpr(expr: string, f: FileData): string {
  expr = expr.trim()

  // link(pathExpr, displayExpr) → [[path\|display]]
  // O `\|` escapa o pipe pra que o GFM não interprete como separador de célula.
  // OFM wikilinkRegex aceita tanto `|` quanto `\|` no alias.
  const linkMatch = expr.match(/^link\s*\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)$/i)
  if (linkMatch) {
    const p = evalScalar(linkMatch[1], f)
    const d = evalScalar(linkMatch[2], f)
    if (!p) return ""
    return `[[${p}\\|${escapePipe(d)}]]`
  }

  // file.link → [[basename]]
  if (expr === "file.link") {
    const name = f.slug.split("/").pop() ?? f.slug
    return `[[${name}]]`
  }

  // Scalar simples (field name ou file.name ou file.path)
  return escapePipe(evalScalar(expr, f))
}

function evalScalar(expr: string, f: FileData): string {
  expr = expr.trim()
  if (expr === "file.name") {
    return f.slug.split("/").pop() ?? f.slug
  }
  if (expr === "file.path") return f.slug
  // String literal?
  const strMatch = expr.match(/^"([^"]*)"$/)
  if (strMatch) return strMatch[1]
  // Campo do frontmatter
  const v = f.fm[expr]
  if (v === undefined || v === null) return ""
  return String(v)
}

function escapePipe(s: string): string {
  // Dentro de tabelas markdown, | precisa ser escapado
  return s.replace(/\|/g, "\\|")
}

function matchesWhere(clause: string, f: FileData): boolean {
  // Só suporta "field OP value" simples
  const m = clause.match(/^(\w+(?:\.\w+)*)\s*(=|!=|>=|<=|>|<)\s*(.+)$/)
  if (!m) return true
  const [, field, op, rhsRaw] = m
  const rhs = rhsRaw.trim()

  const actual = evalScalar(field, f)
  const actualNum = Number(actual)
  const rhsNum = Number(rhs.replace(/^"(.*)"$/, "$1"))
  const rhsStr = rhs.replace(/^"(.*)"$/, "$1")

  const useNum = !Number.isNaN(actualNum) && !Number.isNaN(rhsNum)
  const a = useNum ? actualNum : actual
  const b = useNum ? rhsNum : rhsStr

  switch (op) {
    case "=":  return a === b
    case "!=": return a !== b
    case ">":  return (a as any) > (b as any)
    case "<":  return (a as any) < (b as any)
    case ">=": return (a as any) >= (b as any)
    case "<=": return (a as any) <= (b as any)
  }
  return true
}

function executeQuery(q: ParsedQuery, files: FileData[]): FileData[] {
  let rows = files
  if (q.from) {
    if (q.from.startsWith("#")) {
      // FROM "#tag" → filtra por presença na lista tags do frontmatter
      const tag = q.from.slice(1)
      rows = rows.filter((f) => {
        const tags = f.fm.tags
        return Array.isArray(tags) && tags.some((t) => String(t) === tag)
      })
    } else {
      // FROM "Pasta" → filtra por prefix do slug
      const prefix = q.from.replace(/^\/+|\/+$/g, "") + "/"
      rows = rows.filter((f) => f.slug.startsWith(prefix))
    }
  }
  if (q.where) {
    rows = rows.filter((f) => matchesWhere(q.where!, f))
  }
  if (q.sortField) {
    const field = q.sortField
    const dir = q.sortDir === "DESC" ? -1 : 1
    rows = [...rows].sort((a, b) => {
      const av = a.fm[field]
      const bv = b.fm[field]
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir
      return String(av ?? "").localeCompare(String(bv ?? "")) * dir
    })
  }
  if (q.limit !== null) {
    rows = rows.slice(0, q.limit)
  }
  return rows
}

function buildMarkdownTable(q: ParsedQuery, rows: FileData[]): string {
  if (rows.length === 0) {
    return `*(Sem resultados para a query.)*`
  }
  const header = "| " + q.columns.map((c) => c.label).join(" | ") + " |"
  const sep = "|" + q.columns.map(() => "---").join("|") + "|"
  const body = rows.map((f) => {
    const cells = q.columns.map((c) => evalExpr(c.expr, f) || " ")
    return "| " + cells.join(" | ") + " |"
  })
  return [header, sep, ...body].join("\n")
}

const DATAVIEW_BLOCK = /^```dataview\s*\n([\s\S]*?)\n```$/gm

export const Dataview: QuartzTransformerPlugin = () => ({
  name: "Dataview",
  textTransform(ctx, src) {
    if (!DATAVIEW_BLOCK.test(src)) return src
    DATAVIEW_BLOCK.lastIndex = 0

    if (cachedBuildId !== ctx.buildId) {
      fileCache = buildFileCache(ctx.argv.directory)
      cachedBuildId = ctx.buildId
    }

    return src.replace(DATAVIEW_BLOCK, (match, queryText: string) => {
      const parsed = parseDQL(queryText)
      if (!parsed) return match
      const rows = executeQuery(parsed, fileCache)
      // \n\n antes/depois garante que o GFM reconheça a tabela como bloco
      // independente vs o conteúdo adjacente no source.
      return "\n\n" + buildMarkdownTable(parsed, rows) + "\n\n"
    })
  },
})
