# Relatoría E2 · LimónLab Colima

**Equipo:** Estrella Elizabeth Cárdenas Cuevas (Liza la foránea), individual · **Periodo:** 21 al [dd] de noviembre de 2026

## 1. Qué nos propusimos

Integrar al observatorio una **fuente geoespacial** que agregue variables nuevas a cada mercado (ubicación, distancia a
Tecomán y comercios cercanos), documentar la **ética y legalidad** de todas las fuentes y lograr que **el 100 % de los
valores de la capa Oro** se pueda rastrear hasta su archivo de Bronce y su fecha de captura.

## 2. Qué hicimos

| Fecha | Actividad | Responsable | Tiempo |
|---|---|---|---|
| 21/11 | Revisión de las indicaciones de E2 y elección de la ruta geoespacial | Liza | 10 min |
| 21/11 | Revisión de la política de uso y del robots.txt de Nominatim y de Overpass; se descarta Nominatim | Liza | 15 min |
| 21/11 | Primer extractor con Overpass y transformación `geo.py` (GeoPandas, unión espacial, mapa) | Liza | 35 min |
| 21/11 | Linaje en Plata y Oro, validador y rastreador `linaje.py` | Liza | 25 min |
| 21/11 | 5 pruebas nuevas y ajuste de 4 pruebas de Oro (37 en total) | Liza | 15 min |
| 21/11 | Declaración de ética, ficha de entrega y relatoría | Liza | 25 min |
| 21/11 | Primera ejecución: el pipeline se detiene solo porque el robots.txt de Overpass prohíbe `/api/`; se verifica el archivo a mano | Liza | 10 min |
| 22/11 | Cambio a INEGI (Catálogo Único + DENUE): extractor `inegi_geo.py`, token del DENUE oculto, pruebas y ética actualizadas | Liza | [min] |
| [dd/11] | Primera captura del INEGI, ejecución en GitHub Actions y etiqueta `e2` | Liza | [min] |

Los tiempos salen de [`calidad/tiempo-liza.csv`](../calidad/tiempo-liza.csv).

## 3. Qué decidimos y por qué

| Decisión | Alternativas descartadas | Razón |
|---|---|---|
| Fuente **geoespacial** | Redes sociales; API con OAuth | Es la que aporta variables útiles para la pregunta del observatorio (distancia y demanda local alrededor de cada mercado) y no requiere datos de personas |
| **INEGI** (Catálogo Único + API del DENUE) | **Nominatim** y **Overpass** (OpenStreetMap); servidores espejo de Overpass | El robots.txt de Nominatim prohíbe `/search` y el de Overpass prohíbe `/api/`. Usar un espejo sería darle la vuelta a la prohibición; la regla del proyecto es buscar otra fuente. El INEGI es oficial, mexicano y de libre uso citando la fuente |
| Ubicación a nivel **localidad** | Geocodificar el nombre exacto de cada central de abasto | El Catálogo Único da coordenadas y población oficiales de cada localidad; se elige la más poblada con ese nombre en la entidad. El error de algunos km se declara en la ética |
| Radio de **5 km** | 10 km | Es el máximo que permite la API del DENUE; se complementa con la población de la localidad |
| **Caché** en Bronce y refresco manual mensual | Consultar al INEGI en cada ejecución diaria | Las ubicaciones casi no cambian; así se reduce la carga al servidor |
| Borrar los datos de contacto **antes** de escribir Bronce | Guardar crudo y limpiar en Plata | La regla de privacidad exige que nada personal llegue al disco, ni siquiera en Bronce |
| Linaje con **columnas** en cada fila de Oro | Una tabla de linaje aparte | Así cualquier persona que abra el CSV ve de dónde sale cada valor sin cruzar tablas |

## 4. Qué salió mal y cómo lo corregimos

| Defecto | Qué pasó | Corrección |
|---|---|---|
| D19 | El primer diseño usaba Nominatim sin revisar su robots.txt; al revisarlo resultó prohibido | Se cambió a Overpass y se agregó la revisión automática de robots.txt antes de cada consulta (`permitido_por_robots`) |
| D21 | En la primera ejecución, el pipeline detectó que el robots.txt de Overpass prohíbe `/api/` y se detuvo sin hacer ninguna consulta | Se confirmó a mano el robots.txt y se cambió la fuente a INEGI. El candado automático funcionó como se diseñó |
| D20 | Al agregar las columnas de linaje, 4 pruebas de la capa Oro fallaron porque sus datos de ejemplo no las tenían | Se actualizaron los datos de prueba; además ahora una prueba verifica `origen_valor` y el linaje del tipo de cambio |

## 5. Qué aprendimos

### Ingeniería de Datos
[Escribe aquí con tus palabras. Ejemplo: que para medir distancias hay que pasar las coordenadas de grados a un sistema en metros (EPSG:6372), y que una unión espacial permite contar cuántos comercios caen dentro de un radio.]

### Análisis Estadístico
[Escribe aquí con tus palabras. Ejemplo: cómo la distancia a Tecomán podría entrar como factor o covariable en el experimento o en el análisis multivariado.]

### Calidad en los Sistemas de Información
[Escribe aquí con tus palabras. Ejemplo: que el linaje convierte "confía en mí" en "compruébalo tú": cualquier cifra se rastrea hasta la URL y la hora en que se capturó.]

## 6. Evidencias

- Commits de la etapa: [enlace a la comparación `e1...e2` en GitHub](https://github.com/estrecard/Proyecto_Limones/compare/e1...e2)
- Mapa: [`dashboard/mapa_mercados.html`](../dashboard/mapa_mercados.html)
- Linaje: [`logs/linaje_resumen.json`](../logs/linaje_resumen.json)
- Ética: [`docs/etica-datos.md`](etica-datos.md)
- Ejecución en GitHub Actions: [enlace a la ejecución]

## Uso de IA generativa

Se usó **Claude (Anthropic)** como asistente para proponer el diseño de la fuente geoespacial, generar y revisar el código
(`inegi_geo.py`, `geo.py`, `linaje.py` y sus pruebas), investigar las políticas de uso de OpenStreetMap y del INEGI y redactar borradores de
la declaración de ética, la ficha de entrega y esta relatoría. Todo el código se ejecutó y verificó en el repositorio,
y las decisiones se revisaron antes de integrarlas.
