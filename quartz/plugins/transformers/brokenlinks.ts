import { QuartzTransformerPlugin } from "../types"
import { visit } from "unist-util-visit"
import { Root, Element } from "hast"
import { simplifySlug } from "../../util/path"

/**
 * Marca <a class="internal"> como `.broken` quando o destino não existe
 * em ctx.allSlugs. Roda depois do CrawlLinks (que já populou data-slug).
 * Cobre body e qualquer link interno emitido em componentes (ex: Infobox).
 */
export const BrokenLinks: QuartzTransformerPlugin = () => ({
  name: "BrokenLinks",
  htmlPlugins(ctx) {
    return [
      () => (tree: Root) => {
        const knownSlugs = new Set(ctx.allSlugs.map((s) => simplifySlug(s)))
        visit(tree, "element", (node: Element) => {
          if (node.tagName !== "a") return
          const classes = (node.properties?.className ?? []) as string[]
          if (!Array.isArray(classes) || !classes.includes("internal")) return
          // HAST pode guardar data-slug como "data-slug" (kebab) ou "dataSlug" (camel)
          // dependendo da fonte — checamos os dois.
          const slug =
            (node.properties?.["data-slug"] as string | undefined) ??
            (node.properties?.["dataSlug"] as string | undefined)
          const resolved = slug ? knownSlugs.has(simplifySlug(slug as any)) : false
          if (!resolved && !classes.includes("broken")) {
            classes.push("broken")
            node.properties!.className = classes
          }
        })
      },
    ]
  },
})
