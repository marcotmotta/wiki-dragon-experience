---
tipo: campanha
numero: 1
titulo: "Campanha 1"
---

# Campanha 1

A primeira campanha da Dragon Experience, iniciada em março de 2019. Acompanha a formação do grupo A Mão e sua jornada pelo [[Bosque do Retorno]], passando por [[Lorelheim]] até a ilha de [[Melidria]].

## Episódios

```dataview
TABLE WITHOUT ID
  numero_na_campanha AS "Cap",
  ("[[" + file.name + "|" + titulo + "]]") AS "Título",
  data AS "Data"
FROM "Capítulos"
WHERE campanha = 1
SORT numero_na_campanha ASC
```

## Personagens principais

```dataview
LIST
FROM "Personagens"
WHERE contains(campanhas, 1)
```

## Locais visitados

- [[Bosque do Retorno]]
- [[Vila do Dente Quebrado]]
- [[Lorelheim]]
- [[Melidria]]
