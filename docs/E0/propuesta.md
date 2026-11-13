# Propuesta del Observatorio — LimónLab Colima

**Proyecto Integrador Colegiado "Trusted Data Lab" · Entrega E0**
**Integrante:** Liza la foránea (trabajo individual) · TecNM campus Colima · Noviembre de 2026

---

## 1. Ficha del observatorio

| Campo | Definición |
|---|---|
| **Nombre** | LimónLab Colima — Observatorio del Limón de Colima |
| **Sector** | Agroalimentario: comercialización al mayoreo del limón mexicano (*Citrus aurantifolia*) con semilla |
| **Región** | Colima, con foco en la zona productora de Tecomán–Armería, y los mercados de destino del limón colimense en el país |
| **Pregunta detonadora** | ¿Cuánto costará el limón de Colima en las próximas semanas y qué explica que su precio cambie tanto entre temporadas, calibres y mercados? |
| **Cliente potencial** | Productores de limón de Tecomán y Armería que venden su fruta a empacadores e intermediarios y hoy negocian el precio con poca información |
| **Usuarios secundarios** | Empacadores, comerciantes de centrales de abasto y negocios de alimentos que compran limón con frecuencia |
| **Producto final** | Observatorio en línea con precios por mercado y calibre, comparaciones contra semanas y años anteriores, y un aviso de tendencia a 2–4 semanas |

### 1.1 Problema

El limón mexicano es uno de los cultivos más importantes de Colima, pero su precio de mayoreo es muy volátil. Cambia con la temporada de cosecha, el clima de la zona productora, el calibre de la fruta y el mercado al que se envía. Los productores se enteran de los precios de forma informal y tardía, mientras que los compradores tienen información más completa. Esta **asimetría de información** se traduce en ventas a precios desfavorables.

Existen datos públicos (precios del SNIIM, clima, tipo de cambio), pero están dispersos, en formatos distintos y sin integrar ni validar. LimónLab Colima los captura automáticamente, los somete a puertas de calidad y los convierte en indicadores útiles para decidir.

---

## 2. Entrevista de campo

La entrevista completa, con su ficha, las cinco preguntas y las respuestas, está en [`entrevista.md`](entrevista.md).

> **PENDIENTE:** completar fecha, hora de inicio, hora de fin y duración (mínimo 15 minutos), y agregar aquí el resumen de aprendizajes una vez confirmados los datos de la entrevista.

### 2.1 Aprendizajes y ajustes al observatorio

| # | Aprendizaje | Ajuste al observatorio |
|---|---|---|
| 1 | *[Pendiente]* | *[Pendiente]* |
| 2 | *[Pendiente]* | *[Pendiente]* |
| 3 | *[Pendiente]* | *[Pendiente]* |

---

## 3. Las tres preguntas analíticas

Las preguntas se formulan sobre la tabla analítica de la capa Oro (precio diario por mercado y calibre, unido con el clima de Tecomán y el tipo de cambio).

### 3.1 E1 — Variable a pronosticar

> **¿Cuál será el precio frecuente semanal ($/kg) del limón mexicano con semilla # 5 de origen Colima en los principales mercados de destino, con un horizonte de 2 a 4 semanas?**

| Elemento | Definición |
|---|---|
| Variable objetivo | `precio_frec` del SNIIM, agregado a promedio semanal |
| Serie principal | Limón c/semilla # 5, origen Colima (el calibre con más registros: 272 en octubre de 2026) |
| Horizonte | 2 a 4 semanas |
| Periodos disponibles | Enero 2023 – noviembre 2026: 47 meses, alrededor de 200 semanas |
| Candidatos de modelo | Promedio móvil y suavizamiento exponencial (línea base), SARIMA con estacionalidad anual, regresión con variables climáticas rezagadas |
| Métrica de evaluación | MAPE y RMSE sobre las últimas semanas reservadas para validación |

**Justificación:** un horizonte corto es accionable. Permite decidir si adelantar o retrasar el corte y a qué mercado enviar la fruta.

### 3.2 E2 — Factores a experimentar

> **¿Qué efecto tienen la temporada de cosecha, el calibre de la fruta y la lluvia acumulada en la zona productora sobre el precio frecuente del limón de Colima, y existe interacción entre ellos?**

| Factor | Niveles | Fuente |
|---|---|---|
| A. Temporada | Baja oferta (ene–abr) / Alta oferta (may–sep) / Transición (oct–dic) | Fecha (SNIIM) |
| B. Calibre | # 2, # 3, # 4, # 5, sin clasificación | Producto (SNIIM) |
| C. Lluvia acumulada 30 días previos | Baja / Media / Alta (terciles) | Open-Meteo |
| Covariable | Tipo de cambio FIX USD/MXN | Banxico |

**Diseño:** experimento observacional con ANOVA factorial (A × B × C), revisión de supuestos (normalidad y homocedasticidad) y, si no se cumplen, transformación logarítmica o prueba de Kruskal-Wallis. Comparaciones múltiples con Tukey HSD.

### 3.3 E3 — Grupos multivariados a comparar

> **¿Los mercados de destino del limón de Colima forman grupos distintos según su perfil de precios, es decir, su nivel, volatilidad, estacionalidad y mezcla de calibres?**

| Elemento | Definición |
|---|---|
| Unidades | Mercados de destino reportados por el SNIIM (centrales de abasto de distintos estados) |
| Variables por mercado | Precio medio, desviación estándar, coeficiente de variación, amplitud estacional (máximo/mínimo mensual), proporción por calibre, número de días con registro |
| Técnicas | Estandarización, análisis de componentes principales (PCA), clústeres jerárquico y k-means, y MANOVA para probar diferencias entre los grupos formados o entre regiones (norte, centro y occidente) |

**Justificación:** si los mercados se agrupan de forma estable, el productor puede orientar cada calibre al grupo de mercados que mejor lo paga.

---

## 4. Plan de recopilación de datos

### 4.1 Fuentes

| # | Fuente | Método | Variables | Frecuencia | Cobertura actual |
|---|---|---|---|---|---|
| F1 | **SNIIM** — Secretaría de Economía | Web scraping de la página de resultados (HTML) | Fecha, producto/calibre, calidad, origen, presentación, destino, precio mínimo, máximo y frecuente ($/kg) | Diaria (días hábiles) | Ene 2023 – nov 2026, 5 calibres, origen Colima |
| F2 | **Open-Meteo** Historical Weather API | API REST (JSON), sin clave | Precipitación, temperatura máxima, mínima y media diarias en Tecomán (18.9089, −103.8747) | Diaria | Ene 2023 – nov 2026 |
| F3 | **Banxico** SIE API, serie SF43718 | API REST (JSON) con token personal | Tipo de cambio FIX USD/MXN | Diaria (días hábiles bancarios) | Ene 2023 – nov 2026 |

Todo se guarda **crudo y sin modificar** en `data/bronze/<fuente>/`, junto a un archivo `.meta.json` con la URL consultada, la fecha de captura, el periodo y el número de registros (trazabilidad).

### 4.2 Análisis ético y legal

#### F1 — SNIIM (`http://www.economia-sniim.gob.mx`)

**robots.txt** (consultado el 12/11/2026):
```
User-agent: *
Disallow: /Analisis/
Disallow: /*.xls$
Disallow: /2010/
Disallow: /Sicia/
Disallow: /Sicia2/
Disallow: /SiciaAnt/
Disallow: /Sicia
Disallow: Sicia
# Allow: /
```

**Análisis:** el extractor solo consulta la ruta `/NUEVO/Consultas/MercadosNacionales/PreciosDeMercado/Agricolas/ResultadosConsultaFechaFrutasYHortalizas.aspx`, que **no está en ninguna regla `Disallow`**. No descarga archivos `.xls` ni entra a `/Analisis/`, `/2010/` ni `/Sicia*`. Por lo tanto, el scraping **cumple el robots.txt**.

**Términos de uso:** el SNIIM es un servicio público de la Secretaría de Economía cuyo propósito es difundir los precios de mercado. La información es pública, no contiene datos personales y se usa con fines académicos sin lucro, citando la fuente.

**Medidas de scraping responsable implementadas** (`src/ingest/sniim.py` y `config/settings.yaml`):
- Pausa de **2 segundos** entre peticiones y una sola petición por producto y mes. La carga histórica completa son 235 peticiones repartidas en unos 15 minutos.
- **User-Agent identificado:** `LimonLab-Colima/1.0 (proyecto academico TecNM Colima)`.
- Máximo **3 reintentos** con espera creciente; no se insiste si el servidor falla.
- La ejecución automática es **incremental** (solo los últimos ~35 días) y ocurre **una vez por día hábil** fuera del horario laboral.
- Se guarda una copia local de cada respuesta, así que no hace falta volver a pedir lo que ya se tiene.

#### F2 — Open-Meteo (`https://archive-api.open-meteo.com`)

**Naturaleza:** API pública diseñada para consumo programático, por lo que no aplica el scraping.

**Términos de uso** ([open-meteo.com/en/terms](https://open-meteo.com/en/terms)): el uso no comercial gratuito exige menos de 10,000 llamadas por día, 5,000 por hora y 600 por minuto; usar el servicio gratuito solo con fines no comerciales, y aceptar la licencia CC BY 4.0, que obliga a dar crédito a la fuente e indicar las modificaciones hechas a los datos.

**Cumplimiento:** el proyecto es académico y no comercial. La carga histórica completa es **una sola llamada** y la ejecución diaria es otra, muy lejos del límite. La atribución "Datos meteorológicos: Open-Meteo.com (CC BY 4.0)" se incluirá en el README y en el observatorio.

#### F3 — Banxico SIE API (`https://www.banxico.org.mx/SieAPIRest/`)

**robots.txt** (consultado el 12/11/2026, en `anterior.banxico.org.mx/robots.txt`): bloquea las rutas `/dyn`, `/dyn/` y `/ALEPH` para todos los agentes, y `/ALEPH` y `/ALEPHcgi-bin/` para rastreadores específicos (Googlebot, Slurp, msnbot, entre otros).

**Análisis:** el extractor usa la **API oficial** `/SieAPIRest/service/v1/series/...`, que no está en ninguna regla `Disallow` y que Banxico publica precisamente para el consumo automatizado mediante un token personal.

**Términos de uso:** el acceso requiere un token gratuito asociado a la usuaria, y Banxico fija límites de consultas por periodo y por día. El proyecto hace **una consulta por ejecución**, muy por debajo de esos límites.

**Seguridad del token:** se guarda en `.env` (excluido por `.gitignore`) en la computadora local y como **secreto cifrado** (`BANXICO_TOKEN`) en GitHub Actions. Nunca aparece en el código, en las URL guardadas ni en las bitácoras.

#### Consideraciones éticas generales

- **Sin datos personales:** las tres fuentes publican datos agregados de mercado, clima y finanzas.
- **Entrevista:** se pidió consentimiento para tomar notas y usar la información con fines académicos.
- **Uso de resultados:** el observatorio busca reducir la asimetría de información a favor de los productores. No se usará para especular ni para dañar a ningún actor de la cadena.
- **Transparencia:** el código, las reglas de calidad y los datos rechazados (cuarentena) son públicos en el repositorio.

---

## 5. Máquina de captura (capa Bronce)

| Requisito | Estado |
|---|---|
| Extractor ético automático | `src/pipeline.py` ejecutado por **GitHub Actions** (`.github/workflows/pipeline.yml`) de lunes a viernes a las 18:17 (hora de Colima), con botón para ejecución manual |
| Serie histórica ≥ 36 periodos | **47 periodos mensuales** (enero 2023 – noviembre 2026) en las tres fuentes; datos diarios de días hábiles |
| Datos crudos | `data/bronze/sniim/` (235 archivos HTML + metadatos), `data/bronze/open_meteo/`, `data/bronze/banxico/` |
| Antes de cada ejecución | Se corren 25 pruebas automáticas (`pytest`); si fallan, no se capturan datos |

### 5.1 Resultados de la primera carga y de las ejecuciones automáticas

Reporte `logs/calidad_20261113.json`, generado por la ejecución automática del 13/11/2026:

| Fuente | Registros evaluados | Aceptados (Plata) | Cuarentena | Advertencias | Periodo | Frescura |
|---|---|---|---|---|---|---|
| SNIIM | 19,151 | 19,150 | 1 (CQ-04: precio mínimo mayor que el frecuente) | 57 (CQ-09: salto de precio > 50 %) | 02/01/2023 – 12/11/2026 | 1 día |
| Open-Meteo | 1,408 | 1,408 | 0 | 0 | 01/01/2023 – 08/11/2026 | 5 días |
| Banxico | 971 | 971 | 0 | 0 | 02/01/2023 – 12/11/2026 | 1 día |

Bitácora de ejecuciones (`logs/ejecuciones.jsonl`): 4 ejecuciones, todas con estado **ok**, incluidas 2 ejecuciones en GitHub Actions.

---

## 6. Sistema de calidad inicial (PSP)

### 6.1 Registros abiertos
- `calidad/tiempo-liza.csv`: bitácora de tiempo por fase (planeación, diseño, entorno, codificación, pruebas y documentación).
- `calidad/defectos-liza.csv`: bitácora de defectos con tipo PSP, fase en que se inyectó, fase en que se removió y tiempo de corrección. A la fecha hay 14 defectos registrados.

### 6.2 Objetivos de calidad medibles

| # | Objetivo | Métrica y meta | Cómo se mide |
|---|---|---|---|
| OC-1 | **Datos confiables** | Tasa de aceptación Bronce → Plata **≥ 95 %** por fuente en cada ejecución | Campo `tasa_aceptacion_pct` de `logs/calidad_AAAAMMDD.json` |
| OC-2 | **Captura continua y fresca** | **≥ 90 %** de las ejecuciones automáticas del mes terminan con éxito, y el dato más reciente de cada fuente tiene **≤ 7 días** (regla CQ-10) | Historial de GitHub Actions, `logs/ejecuciones.jsonl` y campo `frescura_dias` |
| OC-3 | **Proceso de desarrollo controlado** | **100 %** de las reglas de calidad bloqueantes cubiertas por al menos una prueba automática, **0 pruebas fallando** antes de cada etiqueta de entrega, y **100 %** de los defectos registrados en la bitácora PSP | `python -m pytest`, `tests/` y `calidad/defectos-liza.csv` |

Las 12 reglas de calidad (CQ-01 a CQ-12, basadas en ISO/IEC 25012) están documentadas en [`../plan_calidad.md`](../plan_calidad.md).

---

## 7. Riesgos y limitaciones

| Riesgo | Mitigación |
|---|---|
| El SNIIM cambia su HTML | Prueba automática con una página real guardada (`tests/fixtures/`); si cambia la estructura, la prueba falla antes de capturar |
| El SNIIM rechaza peticiones desde servidores fuera de México (GitHub Actions) | El pipeline continúa con las demás fuentes y lo reporta en la bitácora; como respaldo, la ejecución puede hacerse desde la computadora local |
| El precio de central de abasto no es el precio pagado en huerta | Se declara como limitación; el observatorio muestra precios de mayoreo en destino como referencia para negociar |
| Restricciones de Windows (Control inteligente de aplicaciones) | Se usa `python -m pip` y CSV como respaldo del formato Parquet; documentado en la bitácora de defectos |

---

## 8. Referencias

- Secretaría de Economía. *Sistema Nacional de Información e Integración de Mercados (SNIIM)*. http://www.economia-sniim.gob.mx
- Open-Meteo. *Historical Weather API* y *Terms & Privacy*. https://open-meteo.com/en/terms
- Banco de México. *Sistema de Información Económica — API REST*. https://www.banxico.org.mx/SieAPIRest/
- ISO/IEC 25012:2008. *Software engineering — Data Quality Model*.
- Humphrey, W. S. (2005). *PSP: A Self-Improvement Process for Software Engineers*. Addison-Wesley.
