# Relatoría E3 · LimónLab Colima

**Equipo:** Estrella Elizabeth Cárdenas Cuevas (Liza la foránea), individual · **Periodo:** 24 de noviembre de 2026

## 1. Qué nos propusimos

Hacer el pipeline **más rápido, más ligero y más resistente a fallas**, demostrando cada mejora con una medición
reproducible y **sin cambiar ni un dato** del resultado. Además, **publicar el dataset curado** con licencia abierta y una
ficha técnica para que otras personas lo puedan usar bien.

## 2. Qué hicimos

| Fecha | Actividad | Responsable | Tiempo |
|---|---|---|---|
| 24/11 | Lectura de las indicaciones de E3 y perfilado del pipeline con `cProfile` y `tracemalloc` | Liza | 20 min |
| 24/11 | Optimizaciones O1-O5 (caché del SNIIM, agregaciones vectorizadas, `usecols`, tolerancia a Bronce dañado) | Liza | 40 min |
| 24/11 | Herramienta de medición antes/después con inyección de fallas y huellas SHA-256 | Liza | 25 min |
| 24/11 | Publicación del dataset (`datapackage.json`, licencia CC BY 4.0, Release) y ficha técnica | Liza | 35 min |
| 24/11 | 7 pruebas nuevas, ficha de entrega y relatoría | Liza | 20 min |

Los tiempos salen de [`calidad/tiempo-liza.csv`](../calidad/tiempo-liza.csv).

## 3. Qué decidimos y por qué

| Decisión | Alternativas descartadas | Razón |
|---|---|---|
| **Perfilar antes de optimizar** (`cProfile`) | Optimizar "a ojo" | El perfil mostró dónde estaba el tiempo: 73 % de Plata en BeautifulSoup y 80 % de Oro en funciones `lambda` por grupo. Sin medir, habríamos optimizado lo que no importaba |
| **Caché** de los HTML ya interpretados | Cambiar de BeautifulSoup a otro lector | Bronce no cambia nunca: interpretar dos veces el mismo archivo es trabajo repetido. La caché da el mismo resultado garantizado y se invalida sola si cambia el lector |
| Caché en **JSON** | CSV | En la prueba, el CSV no distinguía un campo vacío (`""`) de uno ausente (`null`), y eso cambiaba algunos `id_registro`. JSON conserva la diferencia |
| Comparar contra la **etiqueta `e2`** en una carpeta temporal | Medir "antes" y "después" a mano en días distintos | Mismo Bronce, misma máquina y el mismo día: la comparación es justa y cualquiera la puede repetir con un comando |
| **Huella SHA-256** de las salidas | Revisar los datos a ojo | Una optimización que cambia los resultados no es una optimización, es un error. La huella lo demuestra byte por byte |
| Dataset **congelado** con fecha de corte | Publicar la capa Oro que cambia cada día | Quien use los datos necesita que la versión 1.0.0 no cambie mañana; las últimas semanas se recalculan cuando llegan datos nuevos |
| **CC BY 4.0** y **Frictionless Data Package** | Sin licencia; un diccionario de datos en texto libre | CC BY es compatible con todas las fuentes. `datapackage.json` es un estándar que leen herramientas automáticas e incluye huellas para verificar los archivos |

## 4. Qué salió mal y cómo lo corregimos

| Defecto | Qué pasó | Corrección |
|---|---|---|
| D22 | El comando de PowerShell para actualizar las versiones de Actions leyó `pipeline.yml` sin `-Encoding utf8` y dañó los acentos ("ejecuciÃ³n automÃ¡tica" en los commits) | Se restauró el archivo desde el historial de git y se aplicó el cambio de versiones sin reescribir el texto |
| D23 | La primera versión de la caché usaba CSV, que no distingue vacío de nulo, y cambiaba algunos identificadores | Se cambió a JSON; una prueba compara la lectura con y sin caché |
| D24 | La primera medición de memoria de Oro salió inflada (48 MB) porque contaba la importación inicial de librerías | La herramienta mide la memoria en una corrida aparte, después de calentar; el valor real era unos 14 MB |

## 5. Qué aprendimos

### Ingeniería de Datos
Aprendí que optimizar empieza por medir: con `cProfile` vi que casi todo el tiempo se iba en volver a leer archivos que
nunca cambian, y una caché resolvió más que cualquier otro ajuste. También que una mejora solo cuenta si se demuestra
con números, en las mismas condiciones y sin cambiar los resultados, por eso comparé contra la etiqueta `e2` con la
misma capa Bronce y con huellas SHA-256.

### Análisis Estadístico
Entendí que para comparar tiempos hay que repetir la medición y usar la mediana, porque una sola corrida tiene ruido
(por ejemplo, diferencias de centésimas de segundo no significan nada). Además, la ficha técnica me obligó a describir
los huecos del dataset y su mecanismo, que es justo lo que necesita quien vaya a analizarlo.

### Calidad en los Sistemas de Información
Aprendí que la confiabilidad también es eficiencia: antes, un solo archivo dañado tumbaba toda la ejecución, y ahora se
aísla en cuarentena y el resto sigue. Y que publicar datos con licencia, esquema y ficha técnica es parte de la calidad,
porque evita que otras personas los usen para algo que no pueden responder.

## 6. Evidencias

- Comparativa antes/después: [`docs/E3/optimizacion.md`](E3/optimizacion.md)
- Dataset publicado: [`dataset/`](../dataset/) y Release `dataset-v1.0.0`
- Ficha técnica: [`docs/E3/datasheet.md`](E3/datasheet.md)
- Commits de la etapa: [comparación `e2...e3`](https://github.com/estrecard/Proyecto_Limones/compare/e2...e3)

## Uso de IA generativa

Se usó **Claude (Anthropic)** como asistente para perfilar el pipeline, proponer y programar las optimizaciones, la herramienta
de medición, el empaquetado del dataset y sus pruebas, y redactar borradores de la ficha técnica, la ficha de entrega y esta
relatoría, incluidos los párrafos de aprendizajes, que la autora revisó. Las mediciones de `docs/E3/optimizacion.md` se
ejecutaron en la laptop de la autora, y todo el código se ejecutó y verificó con las pruebas automáticas.
