# Entrega E3 · LimónLab Colima — Observatorio del Limón de Colima

**Equipo:** Estrella Elizabeth Cárdenas Cuevas (Liza la foránea), modalidad individual autorizada · **Etiqueta:** `e3` ·
**Repositorio:** https://github.com/estrecard/Proyecto_Limones · **Dataset:** [`dataset/`](../../dataset/) y Release `dataset-v1.0.0` ·
**Fecha:** 24/11/2026

## Resumen en tres líneas

1. Se **optimizó el pipeline** con 5 cambios medidos contra la versión `e2`, con la misma capa Bronce:
   - **tiempo** de reconstrucción Plata → Oro → linaje,
   - **memoria pico**,
   - **errores** ante archivos de Bronce dañados (la versión anterior fallaba y no actualizaba Oro; la nueva los aísla y termina bien).

   Las salidas de Plata y Oro son **idénticas byte por byte** antes y después.
2. Se **publicó el dataset curado** (versión congelada 1.0.0, 2023-01-02 a 2026-11-22) bajo licencia **CC BY 4.0**, con su esquema estándar **Frictionless Data Package** (`datapackage.json`: tipo y descripción de cada columna, llave primaria y huella SHA-256).
3. Se escribió la **ficha técnica (Datasheet for Datasets)** con motivación, composición, recolección, preprocesamiento, usos recomendados y no recomendados, distribución y mantenimiento.

## Ingeniería de Datos

| Entregable | Evidencia (enlace) | Nota del equipo |
|---|---|---|
| **Optimización medida** del pipeline: tiempo, memoria y reducción de errores, antes vs. después | Comparativa: [`docs/E3/optimizacion.md`](optimizacion.md) · Datos crudos de la medición: [`docs/E3/benchmark.json`](benchmark.json) · Herramienta: [`src/quality/benchmark.py`](../../src/quality/benchmark.py) | **Medición reproducible** (`python -m src.quality.benchmark`): el código de la etiqueta `e2` y el actual corren en carpetas temporales con **la misma capa Bronce**. Tiempo con `perf_counter` (mediana de 3 repeticiones), memoria con `tracemalloc` (corrida aparte), **inyección de fallas** (3 archivos de Bronce dañados) y **huella SHA-256** de las 7 salidas para demostrar que los resultados no cambiaron. Se perfiló primero con `cProfile`: el 73 % del tiempo de Plata se iba en volver a leer los HTML con BeautifulSoup y el 80 % del de Oro en `lambda` por grupo |
| Optimizaciones aplicadas | O1 caché de lectura del SNIIM: [`silver.py`](../../src/transform/silver.py) · O2 agregaciones vectorizadas: [`gold.py`](../../src/transform/gold.py) · O3 `usecols` y liberación de memoria · O4 tolerancia a Bronce dañado ([`data/quarantine/bronce_ilegible.csv`](../../data/quarantine/bronce_ilegible.csv)) · O5 avisos sin repetir | La caché se invalida sola si cambia el lector (`VERSION_LECTOR_SNIIM`). Su costo: unos 8 MB en disco (`data/cache/`) y **+5.9 MB de memoria pico en Plata (+11.9 %)**, porque la caché se carga completa. Se acepta el intercambio porque Plata baja de 27.2 s a 5.0 s; Oro sí reduce memoria (−13.1 %). Siguiente mejora posible: guardar la caché por columnas para bajar también la memoria de Plata. La primera corrida sin caché cuesta lo mismo que antes; la ganancia está en las ejecuciones diarias. Equivalencia probada en [`tests/test_e3.py`](../../tests/test_e3.py) |
| **Dataset limpio publicado con licencia abierta** | [`dataset/`](../../dataset/): `limon_semanal.csv` (3,448 filas), `limon_semanal_nacional.csv` (708), `mercados_geo.csv` (18) · [`datapackage.json`](../../dataset/datapackage.json) · [`LICENSE.md`](../../dataset/LICENSE.md) (CC BY 4.0) · [`README.md`](../../dataset/README.md) · Release `dataset-v1.0.0` con el `.zip` · Generador: [`src/publicacion/dataset.py`](../../src/publicacion/dataset.py) | Versión **congelada** con fecha de corte en `config/settings.yaml` (reproducible). CC BY 4.0 es compatible con las fuentes (SNIIM público, Open-Meteo CC BY 4.0, Banxico y INEGI citando la fuente). La publicación **se detiene sola** si aparece una columna con datos personales, una columna sin descripción o una llave primaria duplicada |
| **Datasheet for Datasets** | [`docs/E3/datasheet.md`](datasheet.md) | Estructura de Gebru et al. (2021): motivación, composición (cobertura, faltantes por `origen_valor`, sesgos), recolección, preprocesamiento (puerta Pandera, atípicos, imputación, linaje), **usos recomendados y no recomendados**, distribución y mantenimiento (versionado semántico) |

## Análisis Estadístico

| Criterio de la rúbrica | Evidencia (enlace) | Nota del equipo |
|---|---|---|
| E3 de Análisis Estadístico | Pendiente | |

## Calidad en los Sistemas de Información

| Criterio de la rúbrica | Evidencia (enlace) | Nota del equipo |
|---|---|---|
| E3 de Calidad en los Sistemas de Información | Pendiente | |

## Relatoría de etapa

[`docs/relatoria-E3.md`](../relatoria-E3.md)

## Pruebas automáticas

46 pruebas (`python -m pytest`). Las 7 nuevas de [`tests/test_e3.py`](../../tests/test_e3.py) comprueban:
- que la caché da exactamente lo mismo que leer todo y solo interpreta archivos nuevos;
- que un Bronce dañado se aísla sin detener la lectura;
- que las agregaciones vectorizadas son iguales a las originales, incluidos los empates de la moda;
- que el paquete publicado trae licencia, huellas correctas y descripciones, y se detiene ante datos personales.

Evidencia: [`docs/E3/evidencia_pruebas.txt`](evidencia_pruebas.txt).

## Issues de la entrega anterior

Sin issues abiertos al 24/11/2026.
