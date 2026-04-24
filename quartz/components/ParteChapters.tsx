import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import style from "./styles/partechapters.scss"
import { resolveRelative } from "../util/path"
import { classNames } from "../util/lang"

/**
 * Renderiza automaticamente a tabela de capítulos de uma Parte, lendo
 * allFiles e filtrando por `tipo: capítulo && parte == numero`.
 * Ordena por `numero_global`. Sem manutenção manual — adicionar um capítulo
 * novo com `parte: N` no frontmatter faz ele aparecer automaticamente.
 *
 * Só renderiza em páginas com `tipo: parte`; em outras retorna null.
 */
const ParteChapters: QuartzComponent = ({
  fileData,
  allFiles,
  displayClass,
}: QuartzComponentProps) => {
  const fm = fileData.frontmatter as Record<string, unknown> | undefined
  if (!fm || fm.tipo !== "parte") return null

  const numero = fm.numero as number | undefined
  if (numero === undefined) return null

  const chapters = allFiles
    .filter((f) => {
      const ffm = f.frontmatter as Record<string, unknown> | undefined
      return ffm?.tipo === "capítulo" && ffm?.parte === numero
    })
    .sort((a, b) => {
      const na = (a.frontmatter?.numero_global as number | undefined) ?? 0
      const nb = (b.frontmatter?.numero_global as number | undefined) ?? 0
      return na - nb
    })

  if (chapters.length === 0) return null

  return (
    <section class={classNames(displayClass, "parte-chapters")}>
      <h2>Capítulos</h2>
      <table>
        <thead>
          <tr>
            <th>Nº</th>
            <th>Código</th>
            <th>Título</th>
            <th>Data</th>
          </tr>
        </thead>
        <tbody>
          {chapters.map((f) => {
            const cfm = f.frontmatter as Record<string, unknown>
            const titulo = (cfm.title ?? cfm.titulo) as string
            const data = (cfm.data ?? "") as string
            const nglobal = cfm.numero_global as number | undefined
            const codigo = f.slug!.split("/").pop() ?? f.slug!
            return (
              <tr>
                <td>{nglobal ?? ""}</td>
                <td>{codigo}</td>
                <td>
                  <a href={resolveRelative(fileData.slug!, f.slug!)} class="internal">
                    {titulo}
                  </a>
                </td>
                <td>{data}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}

ParteChapters.css = style

export default (() => ParteChapters) satisfies QuartzComponentConstructor
