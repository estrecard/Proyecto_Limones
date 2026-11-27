# Ficha técnica del dataset (Datasheet for Datasets)

**LimónLab Colima — Precios semanales del limón de Colima en centrales de abasto, con clima, tipo de cambio y geografía**

| | |
|---|---|
| Versión | **1.0.0** (congelada; corte 22/11/2026) |
| Periodo | 2 de enero de 2023 a 22 de noviembre de 2026 (203 semanas) |
| Licencia | **CC BY 4.0**, con atribución obligatoria de las fuentes ([`dataset/LICENSE.md`](../../dataset/LICENSE.md)) |
| Archivos | [`dataset/`](../../dataset/): 3 CSV, `datapackage.json` (esquema estándar Frictionless), `README.md`, `LICENSE.md` |
| Descarga | GitHub Release `dataset-v1.0.0` del repositorio https://github.com/estrecard/Proyecto_Limones |
| Autora y contacto | Estrella Elizabeth Cárdenas Cuevas · TecNM campus Colima · *issues* del repositorio |

Estructura basada en Gebru, T. et al. (2021). *Datasheets for Datasets*. Communications of the ACM, 64(12), 86-92.

---

## 1. Motivación

**¿Para qué se creó?** Para el **Observatorio del Limón de Colima**, que tiene que responder a productores
y compradores de Tecomán: *¿a qué precio se está vendiendo el limón de Colima en las centrales de abasto del país,
cómo cambia con la temporada y el clima, y qué precio esperar en las próximas 2 a 4 semanas?*

Los precios del SNIIM existen, pero no se pueden usar directamente:
- vienen en páginas HTML separadas por mes y calibre,
- un mismo día trae varias presentaciones,
- tienen huecos,
- traen observaciones en texto libre,
- no están unidos con el clima de la zona productora ni con el tipo de cambio.

Este dataset resuelve eso y deja cada valor **rastreable hasta su archivo original**.

**¿Quién lo creó y con qué financiamiento?** Estrella Elizabeth Cárdenas Cuevas, como proyecto integrador
"Trusted Data Lab" de Ingeniería de Datos, Análisis Estadístico y Calidad en los Sistemas de Información
(TecNM campus Colima, 2026). Sin financiamiento externo.

## 2. Composición

**¿Qué representa cada registro?**

| Archivo | Un registro es… | Filas | Columnas | Llave primaria |
|---|---|---|---|---|
| `limon_semanal.csv` | una **semana** (lunes a domingo) de un **mercado** y un **calibre** | 3,448 | 42 | `destino`, `producto`, `semana` |
| `limon_semanal_nacional.csv` | una semana de un calibre, con la **mediana entre mercados** | 708 | 13 | `producto`, `semana` |
| `mercados_geo.csv` | un **mercado** (central de abasto del SNIIM) | 18 | 15 | `destino` |

El tipo y la descripción de cada columna están en [`dataset/datapackage.json`](../../dataset/datapackage.json).

**Cobertura**
- **Mercados:** 16 centrales de abasto de 13 estados (Norte 5, Noroeste 3, Centro-Norte 3, Occidente 3 y Golfo-Sureste 2), con 19 series mercado × calibre.
- **Calibres:** #5 (2,243 semanas), sin clasificación (812), #3 (256) y #4 (137). El calibre #2 no tiene series suficientes.
- **Precio semanal:** mediana de 24.00 MXN/kg, rango de 9.33 a 74.66 MXN/kg y media de 25.33 (desviación estándar de 8.29).

**¿Es una muestra?** Sí. Solo incluye los mercados que **el SNIIM monitorea y que reciben limón de Colima**.
No representa a todo el país; por ejemplo, **la Ciudad de México no tiene registros** de limón con origen Colima.
Dos mercados de `mercados_geo.csv` no aparecen en el panel semanal porque sus series son demasiado cortas
(menos semanas que el mínimo para modelar).

**¿Hay datos faltantes?** Sí, y están marcados:

| `origen_valor` | Semanas | % | Significado |
|---|---|---|---|
| `observado` | 3,296 | 95.6 % | El SNIIM publicó al menos un precio esa semana |
| `imputado` | 11 | 0.3 % | Hueco de 1 o 2 semanas rellenado por interpolación lineal (`imputado = True`) |
| `sin_dato` | 141 | 4.1 % | Hueco más largo: **no se inventa** el precio y la celda queda vacía |

Los huecos **no son al azar**: dependen del día de la semana y aparecen más cuando el precio venía bajo
(prueba χ² y Mann-Whitney en [`docs/E1/reporte_limpieza.md`](../E1/reporte_limpieza.md)).

**¿Contiene datos personales o sensibles?** **No.**
- Son precios de mercado agregados, clima, tipo de cambio y ubicación de ciudades.
- Los comercios del DENUE solo aparecen como **conteos** por zona. Los nombres, razones sociales, teléfonos, correos y domicilios se eliminaron antes de guardar cualquier archivo (ver [`docs/etica-datos.md`](../etica-datos.md)).
- La publicación se detiene sola si aparece una columna con nombre de dato personal.

**¿Hay relaciones entre registros?** Sí:
- `limon_semanal` se une con `mercados_geo` por `destino`.
- `limon_semanal_nacional` resume `limon_semanal` por `producto` y `semana`.

## 3. Proceso de recolección

| Fuente | Cómo se obtuvo | Frecuencia | Variables |
|---|---|---|---|
| **SNIIM**, Secretaría de Economía | *Scraping* de la página de resultados, con permiso de su robots.txt; origen Colima, 5 calibres, precio por kg | Diaria (GitHub Actions, de lunes a viernes) | Precio mínimo, máximo y frecuente; presentación; mercado |
| **Open-Meteo** (Historical Weather API) | API REST | Diaria | Lluvia y temperatura en Tecomán, Colima |
| **Banco de México**, SIE serie SF43718 | API REST con token | Diaria | Tipo de cambio FIX |
| **INEGI**: Catálogo Único y API del DENUE | API REST (DENUE con token), con caché | Una captura (22/11/2026) | Coordenadas y población de la localidad; comercios de frutas y verduras a 5 km |

- Cada descarga se guarda **sin modificar** en la capa Bronce, junto con un `.meta.json` que registra la URL, la fecha y hora de captura y los parámetros.
- Antes de cada consulta se revisa el robots.txt: dos fuentes (Nominatim y Overpass) se descartaron porque lo prohibían.
- No intervino ninguna persona como sujeto de estudio y no se requirió consentimiento, porque no hay datos de personas.

## 4. Preprocesamiento, limpieza y etiquetado

Este es el flujo completo del pipeline (código en `src/`):

1. **Bronce → Plata** con una puerta de calidad Pandera de 12 reglas (CQ-01 a CQ-12): tipos, rangos, consistencia `precio_min ≤ precio_frec ≤ precio_max`, duplicados y fechas válidas.
   - Lo que falla va a cuarentena con su motivo. Aceptación: SNIIM 99.99 % (1 registro rechazado), Open-Meteo 100 %, Banxico 100 %.
2. **Consolidación**: varias presentaciones del mismo día se resuelven con la **mediana** del precio frecuente (todas ya vienen en $/kg).
3. **Atípicos**: el precio es "pegajoso" (el 76.7 % de los residuos son cero).
   - Se separa la tendencia local con una mediana móvil de 15 días hábiles y se usa el residuo **relativo**, con escala común entre series.
   - Un valor es atípico si lo marcan el z robusto (> 3.5) **y** el IQR. Solo se corrigen los aislados (2 días o menos); los cambios de nivel persistentes se respetan.
   - En esta versión se corrigieron 5 días y quedan marcados en `atipicos_corregidos`.
4. **Reducción**: se agrega por semana (de unos 15 mil registros diarios a 3,448 semanales).
5. **Imputación**: interpolación lineal **solo** en huecos interiores de 2 semanas o menos. El tipo de cambio de fines de semana y festivos toma el último valor vigente (LOCF).
6. **Integración y etiquetado**:
   - Se unen clima, tipo de cambio y geografía.
   - Se agregan jerarquías: semana → mes → trimestre → año → temporada; mercado → estado → región; calibre → tamaño.
   - Se agregan los terciles de precio y lluvia.
7. **Linaje**: cada fila conserva los archivos de Bronce y la fecha de captura de cada fuente. Al publicar, el 100 % de los valores observados era trazable (`logs/linaje_resumen.json`).

**No se publican:**
- Las columnas normalizadas (`*_minmax`, `*_z`), porque dependen del periodo. Sus parámetros están en `data/gold/parametros_normalizacion.json`.
- Las columnas técnicas internas del pipeline.

**¿Se guardan los datos crudos?** Sí. La capa Bronce completa está en el repositorio (`data/bronze/`), así que cualquier
paso se puede repetir con `python -m src.pipeline --solo-plata`.

## 5. Usos

**Usos recomendados ✅**
- Analizar la **estacionalidad** del precio del limón de Colima y su relación con la lluvia en la zona productora.
- **Pronosticar** el precio semanal nacional por calibre (`limon_semanal_nacional.csv`) a 2-4 semanas, por ejemplo con modelos ARIMA o SARIMAX con lluvia y tipo de cambio como variables exógenas.
- **Comparar mercados**: diferencias de precio por región, distancia a Tecomán y comercio cercano.
- Enseñar ingeniería de datos y series de tiempo con datos reales mexicanos que traen su linaje y su ficha técnica.

**Usos NO recomendados ❌**
- **Fijar precios individuales o negociar con un comerciante específico.** Son precios de referencia al mayoreo en
  central de abasto, **no** el precio que recibe el productor en la huerta ni el precio al consumidor.
- **Generalizar a todo México** o a la Ciudad de México: solo hay 16 mercados y no están todos los del país.
- Usar `comercios_5km` como **censo** del comercio: es un indicador relativo del DENUE que no incluye tianguis ni negocios informales.
- Usar `distancia_tecoman_km` como costo de flete: es distancia **en línea recta**, no por carretera.
- Tratar las semanas `sin_dato` como precio cero, o las `imputado` como observadas: filtra por `origen_valor`.
- Usar el clima de Tecomán como clima del mercado destino: es el clima de la **zona productora**.

**Riesgos de mal uso.** Un pronóstico mal interpretado podría llevar a un productor a vender antes o después de lo conveniente.
Por eso el observatorio publica los pronósticos con su intervalo de incertidumbre, y esta ficha marca las limitaciones.

## 6. Distribución

- **Dónde:** en la carpeta [`dataset/`](../../dataset/) del repositorio público y como archivo `.zip` en el GitHub Release `dataset-v1.0.0`.
- **Formato:** CSV en UTF-8, con fechas en formato ISO (`AAAA-MM-DD`) y los metadatos en `datapackage.json` (Frictionless Data Package, *tabular-data-package*).
- **Integridad:** cada archivo trae su huella SHA-256 en `datapackage.json`.
- **Licencia:** CC BY 4.0. Las fuentes permiten la redistribución con atribución: la información pública del SNIIM; Open-Meteo con CC BY 4.0; Banxico citando la fuente; e INEGI con sus Términos de Libre Uso.

## 7. Mantenimiento

- **Responsable:** la autora. Los errores se reportan como *issue* en el repositorio.
- **Versiones:**
  - El pipeline actualiza la capa Oro todos los días hábiles, pero el dataset publicado es una **versión congelada**.
  - Para generar una versión nueva se cambian `publicacion.version` y `publicacion.corte` en `config/settings.yaml` y se ejecuta `python -m src.publicacion.dataset`.
  - Se usa versionado semántico: cambio de columnas = versión mayor; más semanas = versión menor; correcciones = parche.
- **Las últimas semanas pueden cambiar entre versiones:**
  - La detección de atípicos usa una ventana centrada, así que los días cercanos al corte se recalculan cuando llegan datos nuevos.
  - Open-Meteo publica con unos 5 días de retraso, así que el clima de la última semana puede estar incompleto.
- **Versiones anteriores:** quedan disponibles en sus Releases y etiquetas de git.
