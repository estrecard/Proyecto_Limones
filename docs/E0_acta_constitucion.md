# E0 — Acta de constitución del laboratorio

**Laboratorio:** LimónLab Colima
**Proyecto:** Observatorio del Limón de Colima
**Integrante:** Liza la foránea
**Modalidad:** individual
**Fecha:** noviembre de 2026

---

## 1. Misión del laboratorio

Producir datos **confiables, trazables y actualizados** sobre el precio del limón mexicano de Colima, y ponerlos a disposición de productores, comerciantes y ciudadanía mediante un observatorio en línea.

## 2. Problema

El limón es uno de los productos agrícolas más importantes de Colima. Su precio cambia mucho a lo largo del año por la estacionalidad de la cosecha, el clima, las plagas y el mercado. Además, hay una brecha grande entre lo que recibe el productor y lo que paga el consumidor.

La información existe, pero está **dispersa** en varias fuentes oficiales con formatos distintos, sin integrar y sin control de calidad. Eso dificulta analizarla.

## 3. Objetivo general

Construir un pipeline automatizado con arquitectura medallón (Bronce → Plata → Oro) que capture, valide e integre datos de precio, clima y tipo de cambio. Sobre él se harán análisis estadísticos y un tablero interactivo.

## 4. Objetivos específicos

1. Automatizar la ingesta de **tres fuentes**: una por web scraping (SNIIM) y dos por API (Open-Meteo y Banxico).
2. Diseñar e implementar **puertas de calidad** que separen los registros válidos de los que van a cuarentena.
3. Generar una **tabla analítica (capa Oro)** con frecuencia diaria por central de abasto.
4. Aplicar **pruebas estadísticas y modelos de regresión** para explicar el precio.
5. Publicar un **observatorio en línea** con indicadores y gráficas interactivas.

## 5. Preguntas e hipótesis (Análisis Estadístico)

| # | Pregunta | Hipótesis (H₁) | Técnica prevista |
|---|---|---|---|
| 1 | ¿El precio es mayor en temporada baja de cosecha (ene–abr) que en temporada alta (may–sep)? | μ_baja > μ_alta | Prueba t / Mann-Whitney |
| 2 | ¿La lluvia acumulada de los 30 días previos en Tecomán se relaciona con el precio? | ρ ≠ 0 | Correlación de Pearson/Spearman con rezagos |
| 3 | ¿El tipo de cambio se asocia con el precio de mayoreo? | β_tc ≠ 0 | Regresión lineal múltiple |
| 4 | ¿El precio del limón de Colima difiere entre centrales de abasto? | Al menos una media distinta | ANOVA / Kruskal-Wallis |

## 6. Alcance

**Incluye:**
- Limón mexicano (con semilla) de **origen Colima**.
- Centrales de abasto que reporte el SNIIM (al menos Guadalajara, CDMX-Iztapalapa y Monterrey).
- Periodo histórico desde enero de 2023, con actualización automática diaria o semanal.
- Clima de Tecomán (lat 18.9089, lon −103.8747).

**No incluye:**
- Precio al productor en campo. Puede añadirse como extensión si hay datos.
- Pronóstico de precios con machine learning, que queda fuera del temario.

## 7. Partes interesadas

| Actor | Interés |
|---|---|
| Productores de limón de Tecomán y Armería | Saber en qué central conviene vender |
| Comerciantes y consumidores | Anticipar alzas de precio |
| Docentes evaluadores | Calidad técnica, estadística y de datos |

## 8. Riesgos y mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| El SNIIM cambia su estructura HTML | Media | Alto | Selectores en `config/`, pruebas que detecten el cambio y copia del HTML crudo en Bronce |
| El SNIIM bloquea o tarda en responder | Media | Medio | Reintentos con espera, pausa entre peticiones y User-Agent identificado |
| Límite de consultas de la API de Banxico | Baja | Bajo | Consultas por rango de fechas (una petición por periodo) |
| Días sin dato (fines de semana o festivos) | Alta | Bajo | Se documenta como completitud esperada, sin imputar en Plata |
| Exposición del token en GitHub | Media | Alto | Archivo `.env` excluido por `.gitignore` y secretos de GitHub Actions |

## 9. Herramientas

Python 3.11+, pandas, requests, BeautifulSoup, PyYAML, pytest, Git/GitHub, GitHub Actions (automatización), Jupyter (estadística) y Streamlit (observatorio).

## 10. Cronograma

| Semana | Fase | Entregable |
|---|---|---|
| 1 | E0 | Acta, diseño y repositorio |
| 2–4 | E1 | Ingesta, Bronce, Plata, puertas de calidad y cuarentena |
| 5 | E2 | Capa Oro y diccionario de datos |
| 6 | E3 | Observatorio en línea |
| 7 | E4 | Modelos estadísticos, informe y presentación |

> Las fechas exactas se ajustan al calendario oficial del docente.