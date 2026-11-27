"""Publicación del dataset curado (E3): capa Oro → carpeta dataset/ lista para terceros.

Genera una versión CONGELADA (fecha de corte fija en config/settings.yaml → publicacion) con:
  - limon_semanal.csv            panel semanal por mercado y calibre (precio + clima + tipo de cambio + geografía + linaje)
  - limon_semanal_nacional.csv   precio semanal nacional por calibre (mediana entre mercados)
  - mercados_geo.csv             los 18 mercados con ubicación, población, distancia a Tecomán y comercios cercanos
  - datapackage.json             metadatos estándar Frictionless Data Package: licencia, fuentes, esquema de
                                 cada columna (tipo y descripción), llave primaria, tamaño y huella SHA-256
  - LICENSE.md y README.md       licencia CC BY 4.0, atribución obligatoria de las fuentes y forma de citar
Y un .zip en dist/ para adjuntarlo como "Release" en GitHub.

Reglas: cero datos personales (se revisa), toda columna publicada debe tener descripción (si falta, se detiene).

Uso:
    python -m src.publicacion.dataset
"""
import hashlib
import json
import shutil
import zipfile
from datetime import date, timedelta

import pandas as pd

from src.utils import RAIZ, cargar_config, obtener_logger, ruta

logger = obtener_logger("publicacion")

LICENCIA = {"name": "CC-BY-4.0", "title": "Creative Commons Attribution 4.0 International",
            "path": "https://creativecommons.org/licenses/by/4.0/"}
FUENTES = [
    {"title": "SNIIM — Sistema Nacional de Información e Integración de Mercados, Secretaría de Economía",
     "path": "http://www.economia-sniim.gob.mx"},
    {"title": "Open-Meteo Historical Weather API (CC BY 4.0)", "path": "https://open-meteo.com/"},
    {"title": "Banco de México — Sistema de Información Económica (SIE), serie SF43718", "path": "https://www.banxico.org.mx/SieAPIRest/"},
    {"title": "INEGI — Catálogo Único de Claves Geoestadísticas y DENUE", "path": "https://www.inegi.org.mx/"},
]
# Columnas técnicas que NO se publican (se pueden recalcular o solo sirven dentro del pipeline)
NO_PUBLICAR_SUFIJOS = ("_minmax", "_z")
NO_PUBLICAR = {"licencia_geo"}
# Nombres de columna que delatarían datos personales: si aparecen, la publicación se detiene
PROHIBIDAS = {"nombre", "razon_social", "telefono", "correo", "correo_e", "email", "sitio_internet", "calle", "domicilio"}

DESCRIPCIONES = {
    # identificación
    "destino": "Central de abasto del SNIIM (estado: nombre del mercado) donde se registró el precio",
    "producto": "Producto del SNIIM: limón con semilla de Colima por calibre (# 2 a # 5 o sin clasificación)",
    "calibre": "Calibre abreviado: #2, #3, #4, #5 o S/C (sin clasificación)",
    "semana": "Lunes de la semana (ISO, semanas de lunes a domingo)",
    "estado": "Estado de la república donde está el mercado",
    # precio
    "precio": "Precio frecuente promedio de la semana en pesos por kilogramo (MXN/kg), ya limpio de atípicos; imputado si origen_valor = imputado",
    "precio_min": "Precio mínimo reportado en la semana (MXN/kg)",
    "precio_max": "Precio máximo reportado en la semana (MXN/kg)",
    "precio_mediana": "Mediana del precio semanal entre los mercados que reportaron ese calibre (MXN/kg)",
    "mercados": "Número de mercados que reportaron ese calibre en la semana",
    "dias_reportados": "Días de la semana con publicación del SNIIM para esa serie (0 si no hubo)",
    "atipicos_corregidos": "Días de la semana cuyo precio se marcó como atípico (z robusto e IQR) y se reemplazó por la tendencia local",
    "imputado": "Verdadero si el precio de la semana se rellenó por interpolación lineal (huecos de hasta 2 semanas)",
    "origen_valor": "Linaje del precio: observado (viene del SNIIM), imputado (interpolado) o sin_dato (hueco largo, no se imputa)",
    # clima
    "lluvia_semana_mm": "Lluvia acumulada en la semana en Tecomán, Colima (mm), Open-Meteo",
    "lluvia_30d_mm": "Lluvia acumulada en los 30 días previos al cierre de la semana en Tecomán (mm)",
    "temp_media": "Temperatura media de la semana en Tecomán (°C)",
    "temp_max": "Temperatura máxima de la semana en Tecomán (°C)",
    "temp_min": "Temperatura mínima de la semana en Tecomán (°C)",
    # tipo de cambio
    "tipo_cambio": "Tipo de cambio FIX pesos por dólar, promedio de la semana (días sin publicación con el último valor vigente)",
    # geografía
    "lat": "Latitud de la localidad del mercado (grados, WGS84), INEGI",
    "lon": "Longitud de la localidad del mercado (grados, WGS84), INEGI",
    "poblacion": "Población total de la localidad del mercado según el Catálogo Único del INEGI",
    "distancia_tecoman_km": "Distancia en línea recta de Tecomán (origen del limón) al mercado, en km (EPSG:6372)",
    "fruterias_5km": "Comercios al por menor de frutas y verduras registrados en el DENUE a 5 km de la localidad",
    "mayoristas_5km": "Comercios al por mayor de frutas y verduras registrados en el DENUE a 5 km de la localidad",
    "comercios_5km": "Suma de fruterías y mayoristas de frutas y verduras a 5 km (indicador relativo, no censo)",
    "ciudad": "Ciudad del mercado usada para ubicarlo",
    "cve_ent": "Clave INEGI de la entidad federativa (2 dígitos)",
    "cvegeo": "Clave geoestadística INEGI de la localidad (9 dígitos)",
    "localidad_inegi": "Nombre oficial de la localidad en el Catálogo Único del INEGI",
    # jerarquías y discretización
    "mes": "Mes de la semana (1-12)",
    "trimestre": "Trimestre de la semana (1-4)",
    "anio": "Año de la semana",
    "temporada": "Temporada del ciclo del limón en Colima: Baja oferta (ene-abr), Alta oferta (may-sep), Transición (oct-dic)",
    "region": "Región del país del mercado (Noroeste, Norte, Centro-Norte, Occidente, Golfo-Sureste)",
    "tamano": "Tamaño del limón según el calibre: Chico, Mediano, Grande o Sin clasificar",
    "lluvia_30d_nivel": "Tercil de lluvia de 30 días: Baja, Media o Alta",
    "precio_nivel": "Tercil del precio semanal: Bajo, Medio o Alto",
    # linaje
    "archivos_bronce": "Linaje: archivos de la capa Bronce (HTML del SNIIM) de los que sale el precio, separados por ';'",
    "fecha_captura": "Linaje: fecha y hora en que se descargó del SNIIM el dato más reciente de la semana",
    "archivo_bronce_clima": "Linaje: archivo(s) de Bronce de Open-Meteo de los que sale el clima de la semana",
    "fecha_captura_clima": "Linaje: fecha y hora de descarga del clima",
    "archivo_bronce_banxico": "Linaje: archivo(s) de Bronce de Banxico de los que sale el tipo de cambio",
    "fecha_captura_banxico": "Linaje: fecha y hora de descarga del tipo de cambio",
    "archivo_bronce_geo": "Linaje: archivo de Bronce del INEGI con la ubicación de la localidad",
    "archivo_bronce_comercios": "Linaje: archivo de Bronce del INEGI (DENUE, anonimizado) con los comercios cercanos",
    "fecha_captura_geo": "Linaje: fecha y hora de descarga de la ubicación",
    "archivo_bronce_ciudad": "Linaje: archivo de Bronce del INEGI con la ubicación de la localidad",
    "fecha_captura_ciudad": "Linaje: fecha y hora de descarga de la ubicación",
}
LLAVES = {"limon_semanal": ["destino", "producto", "semana"],
          "limon_semanal_nacional": ["producto", "semana"],
          "mercados_geo": ["destino"]}


def tipo_frictionless(serie: pd.Series, nombre: str) -> str:
    if nombre == "semana":
        return "date"
    if nombre.startswith("fecha_captura"):
        return "datetime"
    if pd.api.types.is_bool_dtype(serie):
        return "boolean"
    if pd.api.types.is_integer_dtype(serie):
        return "integer"
    if pd.api.types.is_float_dtype(serie):
        return "number"
    return "string"


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def preparar_tablas(cfg_pub: dict) -> dict:
    oro = ruta("gold")
    corte = date.fromisoformat(str(cfg_pub["corte"]))
    ultima_semana = pd.Timestamp(corte - timedelta(days=6))  # solo semanas completas (lunes a domingo) hasta el corte
    tablas = {}
    for nombre in ["limon_semanal", "limon_semanal_nacional"]:
        t = pd.read_csv(oro / f"{nombre}.csv", parse_dates=["semana"], encoding="utf-8-sig",
                        dtype={"cve_ent": str, "cvegeo": str})
        t = t[t["semana"] <= ultima_semana]
        tablas[nombre] = t.sort_values(LLAVES[nombre]).reset_index(drop=True)
    geo = oro / "mercados_geo.csv"
    if geo.exists():
        tablas["mercados_geo"] = pd.read_csv(geo, encoding="utf-8-sig", dtype={"cve_ent": str, "cvegeo": str})
    for nombre, t in tablas.items():
        quitar = [c for c in t.columns if c.endswith(NO_PUBLICAR_SUFIJOS) or c in NO_PUBLICAR]
        tablas[nombre] = t.drop(columns=quitar)
    return tablas


def revisar(tablas: dict):
    for nombre, t in tablas.items():
        personales = PROHIBIDAS & {c.lower() for c in t.columns}
        if personales:
            raise ValueError(f"{nombre}: columnas con posibles datos personales {personales}: no se publica")
        sin_desc = [c for c in t.columns if c not in DESCRIPCIONES]
        if sin_desc:
            raise ValueError(f"{nombre}: columnas sin descripción en DESCRIPCIONES: {sin_desc}")
        if t.duplicated(LLAVES[nombre]).any():
            raise ValueError(f"{nombre}: la llave primaria {LLAVES[nombre]} tiene duplicados")


def publicar() -> dict:
    cfg = cargar_config()
    cfg_pub = cfg["publicacion"]
    tablas = preparar_tablas(cfg_pub)
    revisar(tablas)

    salida = RAIZ / "dataset"
    if salida.exists():
        shutil.rmtree(salida)
    salida.mkdir()
    recursos = []
    for nombre, t in tablas.items():
        archivo = salida / f"{nombre}.csv"
        t.to_csv(archivo, index=False, encoding="utf-8", date_format="%Y-%m-%d")
        recursos.append({
            "name": nombre, "path": archivo.name, "format": "csv", "mediatype": "text/csv", "encoding": "utf-8",
            "bytes": archivo.stat().st_size, "hash": f"sha256:{sha256(archivo)}", "filas": len(t),
            "schema": {"fields": [{"name": c, "type": tipo_frictionless(t[c], c), "description": DESCRIPCIONES[c]}
                                  for c in t.columns],
                       "primaryKey": LLAVES[nombre], "missingValues": [""]},
        })
    semanas = tablas["limon_semanal"]["semana"]
    paquete = {
        "profile": "tabular-data-package",
        "name": "limonlab-colima-precios-limon",
        "title": "LimónLab Colima — Precios semanales del limón de Colima en centrales de abasto, con clima, tipo de cambio y geografía",
        "version": cfg_pub["version"],
        "created": pd.Timestamp.now().isoformat(timespec="seconds"),
        "temporal": {"inicio": str(semanas.min().date()), "fin": str((semanas.max() + timedelta(days=6)).date()),
                     "corte": str(cfg_pub["corte"])},
        "licenses": [LICENCIA],
        "sources": FUENTES,
        "contributors": [{"title": "Estrella Elizabeth Cárdenas Cuevas", "role": "author",
                          "organization": "Tecnológico Nacional de México, campus Colima"}],
        "homepage": "https://github.com/estrecard/Proyecto_Limones",
        "keywords": ["limón", "Colima", "precios", "SNIIM", "centrales de abasto", "series de tiempo", "México"],
        "datasheet": "https://github.com/estrecard/Proyecto_Limones/blob/main/docs/E3/datasheet.md",
        "resources": recursos,
    }
    (salida / "datapackage.json").write_text(json.dumps(paquete, indent=2, ensure_ascii=False), encoding="utf-8")
    (salida / "LICENSE.md").write_text(texto_licencia(), encoding="utf-8")
    (salida / "README.md").write_text(texto_readme(paquete), encoding="utf-8")

    dist = RAIZ / "dist"
    dist.mkdir(exist_ok=True)
    zip_path = dist / f"limonlab_colima_dataset_v{cfg_pub['version']}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(salida.iterdir()):
            z.write(p, f"limonlab_colima_dataset_v{cfg_pub['version']}/{p.name}")
    logger.info(f"Dataset v{cfg_pub['version']} (corte {cfg_pub['corte']}): "
                + ", ".join(f"{r['name']} {r['filas']} filas" for r in recursos) + f" → dataset/ y {zip_path.name}")
    return paquete


def texto_licencia() -> str:
    return """# Licencia del dataset

**LimónLab Colima — dataset curado** © 2026 Estrella Elizabeth Cárdenas Cuevas, publicado bajo
**Creative Commons Atribución 4.0 Internacional (CC BY 4.0)**: https://creativecommons.org/licenses/by/4.0/deed.es

Puedes **copiar, redistribuir, transformar y usar** los datos para cualquier fin, incluso comercial, siempre que:

1. **Des crédito** a este dataset (ver "Cómo citar" en el README) e indiques si hiciste cambios.
2. **Conserves la atribución de las fuentes originales**, que también la exigen:
   - Precios: SNIIM, Secretaría de Economía (información pública).
   - Clima: "Weather data by Open-Meteo.com" (CC BY 4.0).
   - Tipo de cambio: Banco de México, SIE (serie SF43718).
   - Geografía: "Fuente: INEGI, Catálogo Único de Claves Geoestadísticas y Directorio Estadístico Nacional
     de Unidades Económicas (DENUE)" (Términos de Libre Uso de la Información del INEGI).

Los datos se entregan **"tal cual"**, sin garantía. Sus limitaciones están en la ficha técnica (`docs/E3/datasheet.md`).
El código del repositorio no está cubierto por esta licencia de datos.
"""


def texto_readme(p: dict) -> str:
    filas = "\n".join(f"| `{r['path']}` | {r['filas']} | {len(r['schema']['fields'])} | "
                      f"{', '.join(r['schema']['primaryKey'])} | `{r['hash'][7:23]}…` |" for r in p["resources"])
    return f"""# {p['title']}

**Versión {p['version']}** · periodo {p['temporal']['inicio']} a {p['temporal']['fin']} · licencia **CC BY 4.0**
· ficha técnica: [datasheet.md]({p['datasheet']})

| Archivo | Filas | Columnas | Llave primaria | SHA-256 |
|---|---|---|---|---|
{filas}

El esquema completo (tipo y descripción de cada columna) está en `datapackage.json`
(formato estándar [Frictionless Data Package](https://specs.frictionlessdata.io/data-package/)).
Los archivos van en UTF-8 sin BOM; en Excel ábrelos con *Datos → Desde texto/CSV* eligiendo UTF-8.

## Cargar los datos

```python
import pandas as pd
semanal = pd.read_csv("limon_semanal.csv", parse_dates=["semana"])
nacional = pd.read_csv("limon_semanal_nacional.csv", parse_dates=["semana"])
```

## Cómo citar

Cárdenas Cuevas, E. E. (2026). *LimónLab Colima: precios semanales del limón de Colima en centrales de abasto*
(versión {p['version']}) [Conjunto de datos]. https://github.com/estrecard/Proyecto_Limones

Y conserva la atribución de las fuentes indicada en `LICENSE.md`.
"""


if __name__ == "__main__":
    publicar()
