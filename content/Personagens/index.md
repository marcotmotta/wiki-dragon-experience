---
title: Personagens
---

# Personagens

```dataview
TABLE WITHOUT ID
  ("[[" + file.name + "]]") AS "Nome",
  raça AS "Raça",
  classe AS "Classe",
  status AS "Status",
  grupo AS "Grupo"
FROM "Personagens"
SORT file.name ASC
```

## Por campanha

### Campanha 1

```dataview
LIST
FROM "Personagens"
WHERE contains(campanhas, 1)
```
