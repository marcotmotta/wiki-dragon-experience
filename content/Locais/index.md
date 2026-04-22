---
title: Locais
---

# Locais

```dataview
TABLE WITHOUT ID
  ("[[" + file.name + "]]") AS "Nome",
  categoria AS "Categoria",
  região AS "Região"
FROM "Locais"
SORT file.name ASC
```
