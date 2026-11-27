# Declaración de ética y legalidad de datos — LimónLab Colima

**Proyecto:** Trusted Data Lab · Observatorio del Limón de Colima
**Responsable:** Estrella Elizabeth Cárdenas Cuevas (Liza la foránea) · modalidad individual
**Última revisión:** 21/11/2026

Este documento declara, para cada fuente del observatorio, con qué base legal y bajo qué condiciones se usan los datos,
qué riesgos de privacidad y sesgo tienen, y cómo se mitigan. Se revisa en cada entrega y antes de agregar una fuente nueva.

## 1. Principios del observatorio

1. **Solo datos públicos y agregados.** Precios de mercado, clima, tipo de cambio y ubicación de ciudades y comercios.
2. **Cero datos personales.** No se capturan nombres, teléfonos, correos ni perfiles de personas físicas. Si una fuente
   los trae, se eliminan **en memoria, antes de escribir la capa Bronce** (Ley Federal de Protección de Datos Personales
   en Posesión de los Particulares).
3. **robots.txt y términos de uso se respetan siempre.** Si un sitio prohíbe el acceso automatizado, no se usa
   (ver §3.4: se descartaron Nominatim y Overpass por esta razón).
4. **Extractor identificado y moderado.** User-Agent con el nombre del proyecto, pausa mínima de 2 s entre peticiones
   al mismo dominio, reintentos con espera creciente y caché para no repetir consultas.
5. **Uso académico y sin fines de lucro.** Si el observatorio se comercializara, se revisarían de nuevo las licencias (Open-Meteo tiene condiciones distintas para uso comercial).
6. **Transparencia.** Código, reglas de calidad, cuarentena y linaje son públicos en el repositorio.

## 2. Resumen por fuente

| Fuente | Tipo de acceso | Base legal / licencia | robots.txt | Datos personales | Sesgo principal |
|---|---|---|---|---|---|
| SNIIM (Secretaría de Economía) | Scraping de página de resultados | Información pública gubernamental difundida por el propio servicio | Permite la ruta usada | No contiene | Cobertura desigual de mercados; huecos no aleatorios (MNAR) |
| Open-Meteo | API REST sin llave | CC BY 4.0, uso no comercial gratuito | No aplica (API) | No contiene | Reanálisis en malla; un solo punto (Tecomán) |
| Banxico SIE | API REST con token | Servicio oficial del Banco de México con token personal | La API no está bloqueada | No contiene | Ninguno relevante (dato oficial nacional) |
| **INEGI: Catálogo Único + DENUE** (*fuente especializada E2*) | API REST (Catálogo sin token; DENUE con token gratuito) | Términos de Libre Uso de la Información del INEGI (citar la fuente) | Revisado automáticamente antes de cada consulta | **El DENUE sí trae** nombres, razón social, teléfonos y correos: se eliminan antes de guardar | Registro por periodos: faltan negocios informales y nuevos |

## 3. Detalle por fuente

### 3.1 SNIIM — precios al mayoreo del limón

- **Término de uso / base legal:** el SNIIM es un servicio público de la Secretaría de Economía cuyo propósito es difundir precios de mercado. No exige registro ni token. Se cita la fuente en el repositorio y en el tablero.
- **robots.txt** (revisado el 12/11/2026): bloquea `/Analisis/`, `/*.xls$`, `/2010/` y `/Sicia*`. El extractor solo consulta `/NUEVO/Consultas/MercadosNacionales/PreciosDeMercado/Agricolas/ResultadosConsultaFechaFrutasYHortalizas.aspx`, que **no está bloqueada**.
- **Carga:** 1 petición por calibre y mes, con 2 s de pausa. En modo incremental diario son unas 10 peticiones.
- **Privacidad:** solo precios, presentaciones y nombres de mercados públicos.
- **Sesgos conocidos y mitigación:**
  - Solo aparecen los mercados que el SNIIM monitorea; **no hay registros de limón de Colima en CDMX**. *Mitigación:* las conclusiones se limitan a los 18 mercados observados y se dice explícitamente.
  - Los huecos **no son al azar** (dependen del día de la semana y aparecen cuando el precio venía bajo, ver `docs/E1/reporte_limpieza.md`). *Mitigación:* no se imputan huecos largos; cada valor lleva `origen_valor` (observado, imputado o sin dato).
  - El precio es de **central de abasto**, no el que recibe el productor en huerta. *Mitigación:* se declara como limitación en el tablero y en los reportes.

### 3.2 Open-Meteo — clima diario de Tecomán

- **Términos de uso:** el plan gratuito es para uso **no comercial**, con límites de 10,000 llamadas al día, 5,000 por hora y 600 por minuto, y licencia **CC BY 4.0** (dar crédito e indicar modificaciones). Fuente: https://open-meteo.com/en/terms
- **Carga:** 1 llamada por ejecución.
- **Atribución:** "Datos meteorológicos: Open-Meteo.com (CC BY 4.0)" en el README y el tablero. Las modificaciones (agregación semanal, lluvia acumulada de 30 días) se documentan en el reporte de limpieza.
- **Sesgos y mitigación:** es un **reanálisis** en malla, no una estación física, y representa un solo punto (Tecomán) para toda la zona limonera. *Mitigación:* se usa como indicador regional, no como medición exacta, y se declara en las conclusiones.

### 3.3 Banxico SIE — tipo de cambio FIX

- **Términos de uso:** API oficial que requiere un token personal gratuito, con límites de consultas por periodo y por día. El proyecto hace **1 consulta por ejecución**.
- **robots.txt** (revisado el 12/11/2026): bloquea `/dyn` y `/ALEPH`. La ruta de la API (`/SieAPIRest/`) **no está bloqueada**.
- **Seguridad del token:** se guarda en `.env` (excluido por `.gitignore`) y como secreto cifrado `BANXICO_TOKEN` en GitHub Actions. Nunca aparece en el código, en las URL guardadas en Bronce ni en las bitácoras.
- **Privacidad y sesgo:** dato oficial nacional, sin datos personales.

### 3.4 INEGI: Catálogo Único de Claves Geoestadísticas y API del DENUE (fuente especializada geoespacial, E2)

**Qué se obtiene:**
- Del **Catálogo Único** (sin token): clave geoestadística, nombre oficial, latitud, longitud y población de Tecomán y de las 16 localidades donde están los mercados.
- Del **DENUE** (token gratuito): las fruterías (comercio al por menor de frutas y verduras) y los mayoristas de frutas y verduras en un radio de 5 km de cada localidad. Es el máximo que permite la API.

#### Historia de la decisión: dos fuentes descartadas por su robots.txt

| Fecha | Fuente evaluada | Qué dice su robots.txt | Decisión |
|---|---|---|---|
| 21/11/2026 | Nominatim (geocodificador de OpenStreetMap) | Prohíbe `/search`, `/details` y `/reverse` | Descartada **en el diseño** |
| 21/11/2026 | Overpass API (`overpass-api.de`) | `User-agent: *` · `Disallow: /api/`. La API vive en `/api/interpreter` | Descartada **por el propio pipeline**: `permitido_por_robots()` lanzó `PermissionError` en la primera ejecución y no se hizo ninguna consulta |

La revisión automática de robots.txt detuvo una fuente que en el diseño se había dado por buena. El pipeline no confía en la memoria de quien lo programa: verifica cada vez.
Por la regla del proyecto ("si un sitio lo prohíbe, se busca otra fuente. No se negocia") **no se buscaron servidores espejo** de Overpass para darle la vuelta a la prohibición. Se cambió a una fuente oficial mexicana.

#### Condiciones de uso
- **Licencia:** la información del INEGI se publica bajo los **Términos de Libre Uso de la Información del INEGI**. Permiten copiar, distribuir y adaptar los datos, siempre que se cite la fuente. La atribución es "Fuente: INEGI, Catálogo Único de Claves Geoestadísticas y Directorio Estadístico Nacional de Unidades Económicas (DENUE)". Aparece en el mapa, en el README, en la columna `licencia_geo` de Oro y en el `.meta.json` de cada captura.
- **robots.txt:** el extractor lo **revisa automáticamente antes de cada consulta** a `gaia.inegi.org.mx` y a `www.inegi.org.mx` (`src/utils.py → permitido_por_robots`). Si lo prohíbe, lanza `PermissionError` y no consulta. Cada captura guarda `robots_permitido: true` como evidencia.
- **Carga:** unas 34 consultas **una sola vez** (17 localidades y 17 búsquedas de comercios), con 2 s de pausa, guardadas en **caché** en Bronce. La ejecución diaria de GitHub Actions no consulta al INEGI si la caché existe. Para refrescar se usa `python -m src.ingest.inegi_geo --refrescar`, como máximo una vez al mes.
- **Seguridad del token del DENUE:**
  - Dónde vive: en `.env`, excluido por `.gitignore`, y como secreto cifrado `DENUE_TOKEN` en GitHub Actions.
  - Por qué hace falta cuidarlo: la API lo pide **dentro de la URL**, así que antes de guardar cualquier cosa se sustituye por `<DENUE_TOKEN>`, tanto en el `.meta.json` como en los mensajes de error.
  - Cómo se comprueba: una prueba automática verifica que el token no llegue a Bronce.

#### Privacidad (riesgo real)
El DENUE publica, de cada establecimiento, **nombre, razón social, domicilio, teléfono, correo y sitio web**. En los negocios pequeños, la razón social suele ser el nombre de una **persona física**.

**Mitigación:** la función `anonimizar()` (`src/ingest/inegi_geo.py`) elimina todo lo demás **en memoria, antes de escribir Bronce**, y conserva solo:
- `denue_id`,
- `categoria` (`fruteria` o `mayorista`),
- `estrato` (rango de personal ocupado),
- `lat` y `lon`.

También descarta los establecimientos que contienen la palabra "frutas" pero no son comercio de frutas y verduras (por ejemplo, juguerías). Una prueba automática (`tests/test_e2.py`) verifica que ningún nombre, teléfono, correo ni domicilio llegue al disco.

#### Mapa base
El fondo del mapa (calles) son mosaicos de OpenStreetMap que **carga el navegador de quien abre el mapa**. El pipeline no descarga nada de OSM. Se muestra la atribución "© OpenStreetMap contributors" que exige su licencia.

#### Sesgos conocidos y mitigación

| Sesgo | Efecto | Mitigación |
|---|---|---|
| El DENUE se actualiza por periodos y puede no incluir negocios nuevos o informales (puestos de tianguis) | `comercios_5km` subestima la oferta real | Se usa como indicador **relativo** entre mercados y se reporta como "establecimientos registrados en el DENUE", no como censo |
| Ubicación a nivel **localidad**, no de la central de abasto exacta | Error de algunos km en la distancia | La distancia se reporta redondeada a 0.1 km y se declara como aproximada. Dos mercados de la misma ciudad (Guadalajara y Aguascalientes) comparten punto |
| Distancia en **línea recta**, no por carretera | Subestima el recorrido real del flete | Se usa como variable comparativa entre mercados, no para calcular costos |
| Radio de 5 km (límite de la API): en ciudades grandes no cubre toda la zona urbana | Las ciudades extensas parecen tener menos comercio del que tienen | Se acompaña de la **población** de la localidad (Catálogo Único) para comparar con contexto |
| Buffers que se traslapan (Torreón y Gómez Palacio están a pocos km) | Un comercio cuenta para los dos mercados | Es correcto para "comercios a 5 km". Los duplicados dentro de una misma consulta van a cuarentena (GEO-03) |

## 4. Uso secundario y responsabilidad

- Los datos se usan para **informar a productores y compradores** sobre precios y tendencias; no para perfilar personas ni empresas individuales.
- El observatorio **no publica** precios individuales de comerciantes identificables; el SNIIM ya publica promedios por mercado.
- Toda conclusión se acompaña de su incertidumbre y de las limitaciones de esta sección.

### Publicación del dataset curado (E3)

- El dataset de [`dataset/`](../dataset/) se publica bajo **CC BY 4.0**. Es compatible con las fuentes porque todas permiten redistribuir citando: SNIIM (información pública), Open-Meteo (CC BY 4.0), Banxico (citando la fuente) e INEGI (Términos de Libre Uso). La atribución de cada una se repite en `dataset/LICENSE.md`.
- No contiene datos personales: los comercios del DENUE solo aparecen como conteos. El generador **se detiene** si una columna tiene nombre de dato personal.
- La ficha técnica ([`docs/E3/datasheet.md`](E3/datasheet.md)) declara los **usos no recomendados** para evitar interpretaciones dañinas (por ejemplo, tomarlo como precio al productor).

## 5. Referencias

- INEGI — API del DENUE: https://www.inegi.org.mx/servicios/api_denue.html
- INEGI — Catálogo Único de Claves Geoestadísticas (servicio web): https://www.inegi.org.mx/servicios/catalogounico/
- INEGI — Términos de Libre Uso de la Información: https://www.inegi.org.mx/inegi/terminos.html
- OpenStreetMap — Copyright and License (mapa base): https://www.openstreetmap.org/copyright
- Nominatim Usage Policy (fuente descartada): https://operations.osmfoundation.org/policies/nominatim/
- Overpass API (fuente descartada): https://overpass-api.de/robots.txt
- Open-Meteo — Terms & Privacy: https://open-meteo.com/en/terms
- Banxico SIE API: https://www.banxico.org.mx/SieAPIRest/
- SNIIM: http://www.economia-sniim.gob.mx
