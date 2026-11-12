# Catálogo de fuentes de datos

## F1 — SNIIM (Sistema Nacional de Información e Integración de Mercados)

| Atributo | Valor |
|---|---|
| Responsable | Secretaría de Economía |
| Sitio | http://www.economia-sniim.gob.mx |
| Sección | Mercados nacionales → Precios de mercado → Agrícolas → Frutas y hortalizas |
| Método | **Web scraping** (no tiene API oficial) |
| Formato | Tabla HTML |
| Frecuencia | Diaria (días hábiles) |
| Granularidad | Fecha × central de abasto × producto × presentación × origen |
| Campos esperados | fecha, central de abasto, producto, presentación, origen, precio mínimo, precio máximo, precio frecuente, observaciones |
| Unidad | $ por kg (o por caja o arpilla; se normaliza en Plata) |
| Filtro del proyecto | Producto = limón con semilla; origen = Colima |
| Licencia | Información pública gubernamental |
| Riesgos | Cambios en el HTML, tiempos de respuesta altos, presentaciones heterogéneas |

## F2 — Open-Meteo Historical Weather API

| Atributo | Valor |
|---|---|
| Responsable | Open-Meteo (reanálisis ERA5 / ERA5-Land) |
| Endpoint | `https://archive-api.open-meteo.com/v1/archive` |
| Método | **API REST**, sin clave |
| Formato | JSON |
| Frecuencia | Diaria |
| Ubicación | Tecomán, Colima (lat 18.9089, lon −103.8747) |
| Variables | `precipitation_sum`, `temperature_2m_max`, `temperature_2m_min`, `temperature_2m_mean` |
| Zona horaria | `America/Mexico_City` |
| Licencia | CC BY 4.0, uso no comercial gratuito |

Ejemplo de petición:

```
https://archive-api.open-meteo.com/v1/archive?latitude=18.9089&longitude=-103.8747&start_date=2023-01-01&end_date=2023-01-31&daily=precipitation_sum,temperature_2m_max,temperature_2m_min,temperature_2m_mean&timezone=America/Mexico_City
```

## F3 — Banxico SIE API

| Atributo | Valor |
|---|---|
| Responsable | Banco de México |
| Endpoint | `https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF43718/datos/{inicio}/{fin}` |
| Método | **API REST** con token (cabecera `Bmx-Token`) |
| Token | Gratuito: https://www.banxico.org.mx/SieAPIRest/service/v1/token |
| Serie | `SF43718`, tipo de cambio pesos por dólar E.U.A., FIX |
| Formato | JSON (fecha `dd/mm/aaaa`, dato como texto) |
| Frecuencia | Diaria (días hábiles bancarios) |
| Particularidad | Los días sin publicación vienen como `"N/E"` y se tratan en Plata |

## Llave de integración (capa Oro)

Todas las fuentes se unen por **fecha** (`AAAA-MM-DD`). El SNIIM agrega la **central de abasto**. El clima y el tipo de cambio se replican para todas las centrales de un mismo día.