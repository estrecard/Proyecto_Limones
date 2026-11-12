# Plan de entregas — Trusted Data Lab

> El contenido de cada entrega es una propuesta basada en la ponderación del proyecto. Se ajusta cuando el docente publique la rúbrica oficial de cada fase.

## Unidad 3

### E0 — Fundación del laboratorio (10 %) · etiqueta `e0`
- [x] Repositorio con estructura por capas
- [x] README con tema, pregunta y arquitectura
- [x] Acta de constitución, catálogo de fuentes y plan de calidad
- [x] Configuración, `.gitignore`, `.env.example` y `requirements.txt`
- [ ] Docentes agregados como colaboradores
- [ ] Etiqueta `e0` y registro en el formulario

### E1 — Pipeline Bronce → Plata (40 %) · etiqueta `e1`
- Scraper del SNIIM y clientes de API de Open-Meteo y Banxico
- Capa Bronce con archivos crudos fechados
- Puertas de calidad CQ-01 a CQ-12, capa Plata y cuarentena
- Orquestador `src/pipeline.py` y automatización con GitHub Actions
- Bitácoras, métricas de calidad y pruebas con pytest

## Unidad 4

### E2 — Capa Oro (20 %) · etiqueta `e2`
- Integración de precio, clima y tipo de cambio por fecha
- Variables derivadas (lluvia acumulada, temporada, variaciones)
- Diccionario de datos y linaje

### E3 — Observatorio en línea (15 %) · etiqueta `e3`
- Tablero interactivo publicado con indicadores, gráficas y panel de calidad

### E4 — Modelado e informe final (15 %) · etiqueta `e4`
- Notebook con pruebas de hipótesis y regresión múltiple
- Informe final y presentación

## Cómo etiquetar cada entrega

```bash
git add .
git commit -m "E1: pipeline bronce-plata con puertas de calidad"
git tag e1
git push origin main --tags
```