---
tipo: outro
title: Diário de Campanha
tags:
  - Diários-de-Campanha
---

## Campanha 1

### [[Parte 1: Adentrando a Escuridão]]


```dataview
TABLE WITHOUT ID
  numero_global AS "Nº",
  link(file.name, title) AS "Título",
  data AS "Data"
FROM "Capítulos"
WHERE parte = 1
SORT numero_global ASC
```

### [[Parte 2: Peças de Ouro]]


```dataview
TABLE WITHOUT ID
  numero_global AS "Nº",
  link(file.name, title) AS "Título",
  data AS "Data"
FROM "Capítulos"
WHERE parte = 2
SORT numero_global ASC
```

### [[Parte 3: Coração Congelado]]


```dataview
TABLE WITHOUT ID
  numero_global AS "Nº",
  link(file.name, title) AS "Título",
  data AS "Data"
FROM "Capítulos"
WHERE parte = 3
SORT numero_global ASC
```

## Campanha 2

### [[Parte 4: Segredos e Festividades]]


```dataview
TABLE WITHOUT ID
  numero_global AS "Nº",
  link(file.name, title) AS "Título",
  data AS "Data"
FROM "Capítulos"
WHERE parte = 4
SORT numero_global ASC
```

### [[Parte 5: A Sombra que vem de Dentro]]


```dataview
TABLE WITHOUT ID
  numero_global AS "Nº",
  link(file.name, title) AS "Título",
  data AS "Data"
FROM "Capítulos"
WHERE parte = 5
SORT numero_global ASC
```

### [[Parte 6: Juramento de Vingança]]


```dataview
TABLE WITHOUT ID
  numero_global AS "Nº",
  link(file.name, title) AS "Título",
  data AS "Data"
FROM "Capítulos"
WHERE parte = 6
SORT numero_global ASC
```

### [[Parte 7: Inverno Eterno]]


```dataview
TABLE WITHOUT ID
  numero_global AS "Nº",
  link(file.name, title) AS "Título",
  data AS "Data"
FROM "Capítulos"
WHERE parte = 7
SORT numero_global ASC
```

### [[Parte 8: Dois Anos Depois]]


```dataview
TABLE WITHOUT ID
  numero_global AS "Nº",
  link(file.name, title) AS "Título",
  data AS "Data"
FROM "Capítulos"
WHERE parte = 8
SORT numero_global ASC
```

### [[Parte 9]]


```dataview
TABLE WITHOUT ID
  numero_global AS "Nº",
  link(file.name, title) AS "Título",
  data AS "Data"
FROM "Capítulos"
WHERE parte = 9
SORT numero_global ASC
```

## Campanha 3

### [[Parte 10: Cerco Sob Pedra]]


```dataview
TABLE WITHOUT ID
  numero_global AS "Nº",
  link(file.name, title) AS "Título",
  data AS "Data"
FROM "Capítulos"
WHERE parte = 10
SORT numero_global ASC
```

### [[Parte 11]]


```dataview
TABLE WITHOUT ID
  numero_global AS "Nº",
  link(file.name, title) AS "Título",
  data AS "Data"
FROM "Capítulos"
WHERE parte = 11
SORT numero_global ASC
```

## Especiais


```dataview
TABLE WITHOUT ID
  link(file.name, title) AS "Título",
  data AS "Data"
FROM "#Especiais"
SORT title ASC
```
