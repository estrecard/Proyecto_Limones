# Optimización medida del pipeline — E3

Generado automáticamente por `python -m src.quality.benchmark` el 26/11/2026 19:26.
**Antes** = código de la etiqueta `e2` · **Después** = código actual · Misma capa Bronce para las dos
(893 archivos). Entorno: Windows 10, Python 3.11.9, pandas 2.3.3, 12 CPU.

## 1. Tiempo de ejecución (segundos, reconstrucción Bronce → Plata → Oro → linaje)

Mediana de 3 repeticiones. La versión nueva tiene caché de lectura del SNIIM: la **primera** corrida
(caché vacía, como un clon nuevo del repositorio) cuesta lo mismo que antes. Las **siguientes** solo leen los archivos
nuevos, que es lo que pasa en la ejecución diaria.

| Etapa | Antes (mediana) | Después, 1.ª corrida (sin caché) | Después (mediana, con caché) | Mejora |
|---|---|---|---|---|
| Plata | 27.21 | 25.11 | 5.00 | **81.6 %** |
| Oro | 13.17 | 6.19 | 4.06 | **69.2 %** |
| Linaje | 0.29 | 0.27 | 0.27 | **6.5 %** |
| **Total** | **40.67** | **31.57** | **9.33** | **77.1 %** (×4.4 más rápido) |

## 2. Memoria pico (MB, medida con `tracemalloc`)

| Etapa | Antes | Después | Reducción |
|---|---|---|---|
| Plata | 49.7 | 55.6 | **-11.9 %** |
| Oro | 16.8 | 14.6 | **13.1 %** |
| Linaje | 4.0 | 4.0 | **0.0 %** |

`tracemalloc` mide la memoria que reserva Python (incluye los arreglos de pandas/NumPy). No incluye la memoria
interna de librerías en C como lxml, por eso es una medida comparativa entre versiones y no el total del proceso.

## 3. Errores: archivos de Bronce dañados (inyección de fallas)

Se metieron 3 archivos dañados (JSON cortado de Banxico, una página de error en lugar
de JSON de Open-Meteo y un `.meta.json` roto del SNIIM) y se ejecutó `python -m src.pipeline --solo-plata`.

| Indicador | Antes | Después |
|---|---|---|
| Estado de la ejecución | error | ok |
| Errores de etapa en la bitácora | 1 | 0 |
| ¿Se actualizó la capa Oro? | **no** | sí |
| Archivos dañados aislados en `data/quarantine/bronce_ilegible.csv` | 0 | 3 |
| Avisos (WARNING/ERROR) por corrida normal en `logs/pipeline.log` | 3.0 | 1.0 |

Errores de la versión anterior: plata: Unterminated string starting at: line 1 column 21 (char 20)

## 4. ¿Cambiaron los resultados?

Huella SHA-256 de las salidas de Plata y Oro: **7 de 7 archivos idénticos** byte por byte entre
antes y después.

| Archivo | Antes | Después |
|---|---|---|
| `data/silver/sniim.csv` | `087c1a12afd16e65` | `087c1a12afd16e65` |
| `data/silver/open_meteo.csv` | `3cb33734ff17080a` | `3cb33734ff17080a` |
| `data/silver/banxico.csv` | `7f4713f4b1fd1666` | `7f4713f4b1fd1666` |
| `data/gold/sniim_diario_limpio.csv` | `763ab90835b97798` | `763ab90835b97798` |
| `data/gold/limon_semanal.csv` | `098750889f766954` | `098750889f766954` |
| `data/gold/limon_semanal_nacional.csv` | `05060eeb0828803b` | `05060eeb0828803b` |
| `data/gold/parametros_normalizacion.json` | `b648100c7963408f` | `b648100c7963408f` |

## 5. Qué se optimizó

| # | Cambio | Archivo | Efecto |
|---|---|---|---|
| O1 | Caché de lectura del SNIIM: cada HTML de Bronce (inmutable) se interpreta con BeautifulSoup una sola vez y sus renglones se guardan en `data/cache/sniim_renglones.json` | `src/transform/silver.py` | Tiempo de Plata |
| O2 | Agregaciones vectorizadas en Oro: linaje (`unir_unicos_por_grupo`), moda, mediana móvil y relleno por serie, sin funciones `lambda` que creaban una Serie por cada uno de los ~15 mil grupos | `src/transform/gold.py` | Tiempo de Oro |
| O3 | Oro lee de Plata solo las columnas que usa (`usecols`) y Plata libera la caché conforme la convierte | `gold.py`, `silver.py` | Memoria |
| O4 | Tolerancia a archivos de Bronce dañados: se registran en cuarentena y el resto continúa | `silver.py` | Errores |
| O5 | El aviso de pyarrow se muestra una vez por ejecución y no una por fuente | `silver.py` | Ruido en bitácora |
