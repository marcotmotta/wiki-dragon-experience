import { QuartzTransformerPlugin } from "../types"
import { visit } from "unist-util-visit"
import { Root, Element } from "hast"
import fs from "fs"
import path from "path"
import matter from "gray-matter"

type Frontmatter = Record<string, unknown>

let cachedBuildId: string | null = null
let frontmatterCache: Map<string, Frontmatter> = new Map()

function buildCache(contentDir: string): Map<string, Frontmatter> {
  const cache = new Map<string, Frontmatter>()
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) {
        // pula pastas ignoradas pelo Quartz
        if (entry.name.startsWith(".") || entry.name === "node_modules") continue
        walk(full)
      } else if (entry.name.endsWith(".md")) {
        try {
          const src = fs.readFileSync(full, "utf-8")
          const { data } = matter(src)
          const slug = path.basename(entry.name, ".md")
          // última gravação vence (colisão de basenames improvável neste repo)
          cache.set(slug, data as Frontmatter)
        } catch {
          // ignora arquivos que falhem de parsear
        }
      }
    }
  }
  walk(contentDir)
  return cache
}

/**
 * Dado o frontmatter do alvo, devolve o display text a substituir no link.
 * null = não enriquecer (deixa como está).
 */
function renderDisplay(fm: Frontmatter): string | null {
  const title = (fm.title ?? fm.titulo ?? fm.nome) as string | undefined
  return title ?? null
}

export const RichWikilinks: QuartzTransformerPlugin = () => ({
  name: "RichWikilinks",
  htmlPlugins(ctx) {
    return [
      () => (tree: Root) => {
        if (cachedBuildId !== ctx.buildId) {
          frontmatterCache = buildCache(ctx.argv.directory)
          cachedBuildId = ctx.buildId
        }
        const cache = frontmatterCache

        visit(tree, "element", (node: Element) => {
          if (node.tagName !== "a") return
          const classes = (node.properties?.className ?? []) as string[]
          if (!Array.isArray(classes)) return
          if (!classes.includes("internal")) return
          // Usuário forneceu texto custom (CrawlLinks marca como "alias") — respeita.
          if (classes.includes("alias")) return

          const child = node.children?.[0]
          if (!child || child.type !== "text") return

          const slug = path.basename(child.value)
          const fm = cache.get(slug)
          if (!fm) return

          const display = renderDisplay(fm)
          if (display && display !== child.value) {
            child.value = display
          }
        })
      },
    ]
  },
})
