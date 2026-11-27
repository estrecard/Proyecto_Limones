"""Capa Plata: lee Bronce, tipifica y normaliza cada fuente, aplica las puertas de calidad
y escribe los datos aceptados en data/silver/ y los rechazados en data/quarantine/.
Genera además el reporte de métricas de calidad en logs/calidad_AAAAMMDD.json.

Optimizaciones E3 (medidas en docs/E3/optimizacion.md):
  - CACHÉ DE LECTURA DEL SNIIM: Bronce es inmutable, así que cada HTML se interpreta una sola vez
    y sus renglones se guardan en data/cache/sniim_renglones.json. En cada ejecución solo se leen
    los archivos nuevos (antes se volvían a interpretar los ~700 HTML con BeautifulSoup).
  - TOLERANCIA A ARCHIVOS DAÑADOS: si un archivo de Bronce no se puede leer, se registra en
    data/quarantine/bronce_ilegible.csv y se continúa con los demás (antes tumbaba toda la capa Plata
    y, con ella, la capa Oro).

Uso:
    python -m src.transform.silver
"""
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src.ingest.sniim import leer_tabla
from src.quality.gates import aplicar_puertas, reglas_de
from src.utils import RAIZ, cargar_config, obtener_logger, ruta

logger = obtener_logger("silver")


# ----------------------------------------------------------------------------- lectura de Bronce
VERSION_LECTOR_SNIIM = 1          # súbelo si cambia leer_tabla(): la caché se reconstruye sola
ILEGIBLES = []                    # archivos de Bronce que no se pudieron leer en esta ejecución
_AVISOS = set()                   # para no repetir el mismo aviso en cada fuente


def avisar_una_vez(clave: str, mensaje: str):
    if clave not in _AVISOS:
        _AVISOS.add(clave)
        logger.warning(mensaje)


def ilegible(fuente: str, archivo: str, error: Exception):
    """Un archivo de Bronce dañado no detiene el pipeline: se anota y se sigue con los demás."""
    ILEGIBLES.append({"fuente": fuente, "archivo": archivo, "error": f"{type(error).__name__}: {error}"[:300],
                      "fecha_rechazo": datetime.now().isoformat(timespec="seconds")})
    logger.error(f"{fuente}: archivo de Bronce ilegible, se omite y se registra en cuarentena -> {archivo}")


def archivos_bronce(fuente: str):
    """Devuelve pares (archivo_crudo, metadatos) de una fuente."""
    carpeta = ruta("bronze") / fuente
    for meta_path in sorted(carpeta.glob("*.meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            crudo = carpeta / meta["archivo"]
        except (ValueError, KeyError, UnicodeDecodeError) as e:
            ilegible(fuente, meta_path.name, e)
            continue
        if crudo.exists():
            yield crudo, meta


def numero(serie: pd.Series) -> pd.Series:
    """Convierte texto a número; lo que no se pueda (ej. 'N/E') queda vacío (NaN)."""
    return pd.to_numeric(serie.astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")


def leer_banxico() -> pd.DataFrame:
    filas = []
    for crudo, meta in archivos_bronce("banxico"):
        try:
            datos = json.loads(crudo.read_text(encoding="utf-8"))["bmx"]["series"][0].get("datos", [])
        except (ValueError, KeyError, IndexError, TypeError, UnicodeDecodeError) as e:
            ilegible("banxico", crudo.name, e)
            continue
        for d in datos:
            filas.append({"fecha_texto": d.get("fecha"), "tipo_cambio_texto": d.get("dato"),
                          "fuente": "banxico", "fecha_captura": meta["fecha_captura"], "archivo_origen": crudo.name})
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["fecha"] = pd.to_datetime(df["fecha_texto"], format="%d/%m/%Y", errors="coerce")
    df["tipo_cambio"] = numero(df["tipo_cambio_texto"])
    return df


def leer_open_meteo() -> pd.DataFrame:
    partes = []
    for crudo, meta in archivos_bronce("open_meteo"):
        try:
            d = json.loads(crudo.read_text(encoding="utf-8"))["daily"]
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as e:
            ilegible("open_meteo", crudo.name, e)
            continue
        p = pd.DataFrame({
            "fecha_texto": d.get("time"),
            "precipitacion_mm": d.get("precipitation_sum"),
            "temp_max": d.get("temperature_2m_max"),
            "temp_min": d.get("temperature_2m_min"),
            "temp_media": d.get("temperature_2m_mean"),
        })
        p["fuente"], p["fecha_captura"], p["archivo_origen"] = "open_meteo", meta["fecha_captura"], crudo.name
        partes.append(p)
    if not partes:
        return pd.DataFrame()
    df = pd.concat(partes, ignore_index=True)
    df["fecha"] = pd.to_datetime(df["fecha_texto"], format="%Y-%m-%d", errors="coerce")
    for c in ["precipitacion_mm", "temp_max", "temp_min", "temp_media"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def ruta_cache_sniim() -> Path:
    carpeta = RAIZ / "data" / "cache"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / "sniim_renglones.json"


def cargar_cache_sniim() -> dict:
    """{archivo_de_bronce: [renglones tal como los devuelve leer_tabla]}. JSON conserva vacío ("") y nulo (null)."""
    p = ruta_cache_sniim()
    if not p.exists():
        return {}
    try:
        cache = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        logger.warning("Caché del SNIIM dañada: se reconstruye desde Bronce")
        return {}
    if cache.get("version_lector") != VERSION_LECTOR_SNIIM:
        logger.info("Caché del SNIIM de otra versión del lector: se reconstruye")
        return {}
    return cache["archivos"]


def leer_sniim(usar_cache: bool = True) -> pd.DataFrame:
    """Lee los HTML del SNIIM. Con caché, solo interpreta los archivos que no se habían leído antes."""
    cache = cargar_cache_sniim() if usar_cache else {}
    n_nuevos, presentes = 0, []
    for crudo, meta in archivos_bronce("sniim"):
        if crudo.name not in cache:
            try:
                cache[crudo.name] = leer_tabla(crudo.read_text(encoding="utf-8"))["renglones"]
                n_nuevos += 1
            except Exception as e:  # HTML dañado o con otra estructura
                ilegible("sniim", crudo.name, e)
                continue
        presentes.append((crudo.name, meta))
    if usar_cache and n_nuevos:
        ruta_cache_sniim().write_text(json.dumps({"version_lector": VERSION_LECTOR_SNIIM, "archivos": cache},
                                                 ensure_ascii=False), encoding="utf-8")
    logger.info(f"SNIIM: {len(presentes)} archivos de Bronce ({len(presentes) - n_nuevos} desde caché, "
                f"{n_nuevos} interpretados)")
    # Memoria (E3): cada archivo se saca de la caché conforme se convierte, para no tener todo duplicado
    filas = []
    for nombre, meta in presentes:
        extra = {"producto_id": meta.get("producto_id"), "fuente": "sniim",
                 "fecha_captura": meta["fecha_captura"], "archivo_origen": nombre}
        filas.extend({**r, **extra} for r in cache.pop(nombre))
    del cache
    df = pd.DataFrame(filas)
    del filas
    if df.empty:
        return df
    df = df.rename(columns={"fecha": "fecha_texto"})
    df["fecha"] = pd.to_datetime(df["fecha_texto"], format="%d/%m/%Y", errors="coerce")
    for c in ["precio_min", "precio_max", "precio_frec"]:
        df[c] = numero(df[c])
    for c in ["producto", "calidad", "origen", "presentacion", "destino", "observaciones"]:
        df[c] = df[c].astype("string").str.strip().str.replace(r"\s+", " ", regex=True).replace("", pd.NA)
    df["estado_destino"] = df["destino"].str.split(":").str[0].str.strip()
    return df


LECTORES = {"banxico": leer_banxico, "open_meteo": leer_open_meteo, "sniim": leer_sniim}
LLAVES = {"banxico": ["fecha_texto"], "open_meteo": ["fecha_texto"],
          "sniim": ["fecha_texto", "producto", "destino", "presentacion"]}


# ----------------------------------------------------------------------------- proceso
def consolidar_capturas(df: pd.DataFrame, llave: list):
    """Si un mismo dato se descargó en varias capturas (re-descargas), se conserva la más reciente.
    Esto NO es un error de calidad: es la actualización normal de Bronce."""
    antes = len(df)
    ultima = df.groupby(llave, dropna=False)["fecha_captura"].transform("max")
    df = df[df["fecha_captura"] == ultima]  # duplicados dentro de la misma captura siguen: los detecta CQ-05
    return df, antes - len(df)


def metricas(df_bronce, df_evaluado, aceptados, cuarentena, resumen, reemplazados):
    total = len(df_evaluado)
    completitud = (df_evaluado.notna().mean() * 100).round(2).to_dict() if total else {}
    ultima = aceptados["fecha"].max() if len(aceptados) else None
    return {
        "registros_bronce": len(df_bronce),
        "reemplazados_por_captura_mas_reciente": reemplazados,
        "registros_evaluados": total,
        "registros_plata": len(aceptados),
        "registros_cuarentena": len(cuarentena),
        "tasa_aceptacion_pct": round(100 * len(aceptados) / total, 2) if total else 0,
        "registros_con_advertencia": int((aceptados["advertencias"] != "").sum()) if len(aceptados) else 0,
        "fecha_min": str(aceptados["fecha"].min().date()) if len(aceptados) else None,
        "fecha_max": str(ultima.date()) if ultima is not None else None,
        "frescura_dias": (date.today() - ultima.date()).days if ultima is not None else None,
        "completitud_pct": completitud,
        "reglas": resumen,
    }


def procesar(fuente: str) -> dict:
    df = LECTORES[fuente]()
    if df.empty:
        logger.warning(f"{fuente}: no hay datos en Bronce")
        return {"registros_bronce": 0}

    df_consolidado, reemplazados = consolidar_capturas(df, LLAVES[fuente])
    # Linaje: identificador estable de cada registro (fuente + archivo de Bronce + llave del dato)
    columnas_id = ["archivo_origen"] + LLAVES[fuente]
    df_consolidado = df_consolidado.assign(id_registro=(
        fuente + "-" + pd.util.hash_pandas_object(df_consolidado[columnas_id].astype(str), index=False)
        .astype("uint64").map("{:016x}".format)).values)
    aceptados, cuarentena, resumen = aplicar_puertas(df_consolidado, reglas_de(fuente))

    # Plata: se quitan columnas de texto crudo auxiliares y se ordena
    auxiliares = [c for c in aceptados.columns if c.endswith("_texto")]
    aceptados = aceptados.drop(columns=auxiliares).sort_values("fecha").reset_index(drop=True)
    try:
        aceptados.to_parquet(ruta("silver") / f"{fuente}.parquet", index=False)
    except ImportError:
        avisar_una_vez("pyarrow", "pyarrow no está instalado: se omiten los .parquet (los .csv sí se escriben)")
    aceptados.to_csv(ruta("silver") / f"{fuente}.csv", index=False, encoding="utf-8-sig")
    cuarentena.to_csv(ruta("quarantine") / f"{fuente}_cuarentena.csv", index=False, encoding="utf-8-sig")

    m = metricas(df, df_consolidado, aceptados, cuarentena, resumen, reemplazados)
    cal = cargar_config()["calidad"]
    if m["frescura_dias"] is not None and m["frescura_dias"] > cal["frescura_max_dias"]:
        logger.warning(f"{fuente}: CQ-10 Actualidad — el dato más reciente tiene {m['frescura_dias']} días")
    m["cq10_actualidad_ok"] = m["frescura_dias"] is not None and m["frescura_dias"] <= cal["frescura_max_dias"]

    logger.info(f"{fuente:<11} Evaluados {m['registros_evaluados']:>6} | Plata {m['registros_plata']:>6} | "
                f"Cuarentena {m['registros_cuarentena']:>5} | Aceptación {m['tasa_aceptacion_pct']:>6}%")
    for r in resumen:
        if r["registros_que_fallan"]:
            logger.info(f"    {r['codigo']} ({r['tipo']}): {r['registros_que_fallan']} registros — {r['descripcion']}")
    return m


def main():
    ILEGIBLES.clear()
    _AVISOS.clear()   # cada ejecución avisa una vez de cada cosa
    reporte = {"fecha_ejecucion": datetime.now().isoformat(timespec="seconds"), "fuentes": {}}
    for fuente in ["sniim", "open_meteo", "banxico"]:
        reporte["fuentes"][fuente] = procesar(fuente)
    # Archivos de Bronce dañados: se reportan, no detienen la ejecución
    pd.DataFrame(ILEGIBLES, columns=["fuente", "archivo", "error", "fecha_rechazo"]).to_csv(
        ruta("quarantine") / "bronce_ilegible.csv", index=False, encoding="utf-8-sig")
    reporte["bronce_ilegible"] = len(ILEGIBLES)
    salida = ruta("logs") / f"calidad_{date.today():%Y%m%d}.json"
    salida.write_text(json.dumps(reporte, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info(f"Reporte de calidad: {salida.relative_to(RAIZ)}")
    return reporte


if __name__ == "__main__":
    main()