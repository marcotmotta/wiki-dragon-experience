---
title: Todos os Capítulos
---

# Todos os Capítulos

Lista completa de todos os capítulos da Dragon Experience, ordenados cronologicamente.

```dataview
TABLE WITHOUT ID
  numero_global AS "#",
  ("Camp. " + campanha) AS "Campanha",
  ("[[" + file.name + "|" + titulo + "]]") AS "Título",
  data AS "Data"
FROM "Capítulos"
SORT numero_global ASC
```

## Por campanha

### Campanha 1

```dataview
LIST ("[[" + file.name + "|" + titulo + "]]")
FROM "Capítulos"
WHERE campanha = 1
SORT numero_na_campanha ASC
```

### Campanha 2

```dataview
LIST ("[[" + file.name + "|" + titulo + "]]")
FROM "Capítulos"
WHERE campanha = 2
SORT numero_na_campanha ASC
```

### Campanha 3

```dataview
LIST ("[[" + file.name + "|" + titulo + "]]")
FROM "Capítulos"
WHERE campanha = 3
SORT numero_na_campanha ASC
```
