# Entrega E2 · LimónLab Colima — Observatorio del Limón de Colima

**Equipo:** Estrella Elizabeth Cárdenas Cuevas (Liza la foránea), modalidad individual autorizada · **Etiqueta:** `e2` ·
**Tablero:** mapa interactivo en [`dashboard/mapa_mercados.html`](../../dashboard/mapa_mercados.html) (tablero público en construcción) ·
**Repositorio:** https://github.com/estrecard/Proyecto_Limones · **Fecha:** [dd/mm/2026]

## Resumen en tres líneas

1. Se integró una **fuente geoespacial** (servicios web del INEGI —Catálogo Único de Claves Geoestadísticas y API del DENUE— + GeoPandas): ubicación de 18 mercados, distancia a Tecomán y comercios de frutas y verduras a 5 km por **unión espacial**, con un **mapa interactivo**.
2. Se escribió la **declaración de ética y legalidad** por fuente; se **descartó Nominatim** porque su robots.txt lo prohíbe, y los datos de contacto de comercios se eliminan antes de guardar.
3. Cada registro de la capa Oro es **rastreable hasta su archivo de Bronce y su fecha de captura**: [X] % de trazabilidad medida automáticamente en cada ejecución.

## Ingeniería de Datos

| Criterio de la rúbrica | Evidencia (enlace) | Nota del equipo |
|---|---|---|
| **Fuente especializada** (45): integrada al pipeline y visible en el tablero, sin datos personales | Extractor: [`src/ingest/inegi_geo.py`](../../src/ingest/inegi_geo.py) · GeoPandas: [`src/transform/geo.py`](../../src/transform/geo.py) · Oro: [`data/gold/mercados_geo.csv`](../../data/gold/mercados_geo.csv), [`mercados_geo.geojson`](../../data/gold/mercados_geo.geojson) · Mapa: [`dashboard/mapa_mercados.html`](../../dashboard/mapa_mercados.html) · Integración en Oro: columnas `distancia_tecoman_km`, `comercios_5km`, `poblacion`, `lat`, `lon` de [`limon_semanal.csv`](../../data/gold/limon_semanal.csv) · Orquestación: [`src/pipeline.py`](../../src/pipeline.py) | Geoespacial con INEGI. Reproyección EPSG:4326 → **EPSG:6372** (metros), distancia a Tecomán, **buffer de 5 km** y **`gpd.sjoin`** (unión espacial) con fruterías y mayoristas del DENUE. Puerta Pandera propia (GEO-01 a GEO-03) con cuarentena `data/quarantine/geo_*_cuarentena.csv`. **Cero datos personales**: `anonimizar()` borra nombres, razón social, domicilio, teléfonos y correos antes de Bronce, y el token del DENUE nunca se guarda (probado en `tests/test_e2.py`). Caché: la ejecución diaria no le pega al INEGI |
| **Declaración de ética y legalidad** (30): base legal, licencia, riesgos y sesgos por fuente | [`docs/etica-datos.md`](../etica-datos.md) | Cuatro fuentes con términos de uso, robots.txt, licencia (libre uso INEGI, CC BY 4.0), privacidad, sesgos y mitigación. Documenta dos fuentes **descartadas por su robots.txt**: Nominatim (en el diseño) y Overpass (el pipeline la detuvo solo) |
| **Linaje de datos** (15): cada registro rastreable hasta su origen | Validador y rastreador: [`src/quality/linaje.py`](../../src/quality/linaje.py) · Resultado: [`logs/linaje_resumen.json`](../../logs/linaje_resumen.json) · Columnas de linaje en Oro: `archivos_bronce`, `fecha_captura`, `origen_valor`, `archivo_bronce_clima`, `archivo_bronce_banxico`, `archivo_bronce_geo` · `id_registro` en Plata | Cadena **Oro semanal → Oro diario (`ids_plata`) → Plata (`id_registro`, `archivo_origen`, `fecha_captura`) → Bronce (`.meta.json` con URL y fecha)**. Se valida en cada ejecución que los archivos existan. Ejemplo: `python -m src.quality.linaje --destino "Jalisco: Mercado de Abasto de Guadalajara" --calibre "#5" --semana 2026-10-05` |

## Análisis Estadístico

| Criterio de la rúbrica | Evidencia (enlace) | Nota del equipo |
|---|---|---|
| Diseño y principios (25) | Pendiente | |
| Dos factores con interacción (20) | Pendiente | |
| Completo vs. fraccionado (20) | Pendiente | |
| Análisis y confirmación (25) | Pendiente | |

## Calidad en los Sistemas de Información

| Criterio de la rúbrica | Evidencia (enlace) | Nota del equipo |
|---|---|---|
| Evaluación ISO/IEC 25010 (30) | Pendiente | |
| Evaluación ISO/IEC 25012 (25) | Pendiente | |
| Antecedentes normativos (10) | Pendiente | |
| Auditoría cruzada (25) | Pendiente | |

## Relatoría de etapa

[`docs/relatoria-E2.md`](../relatoria-E2.md)

## Pruebas automáticas

39 pruebas (`python -m pytest`), entre ellas las nuevas de [`tests/test_e2.py`](../../tests/test_e2.py): anonimización del DENUE, token oculto, elección de localidad, respeto a robots.txt, caché, distancia y unión espacial con GeoPandas, y detección de registros sin linaje. Evidencia: [`docs/E2/evidencia_pruebas.txt`](evidencia_pruebas.txt).

## Issues de la entrega anterior

[Lista de issues abiertos por los docentes en GitHub y el commit que cierra cada uno. Si no hay issues, escribir "Sin issues abiertos al dd/mm/2026".]
