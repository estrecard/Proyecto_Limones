"""Puertas de calidad (ISO/IEC 25012) del plan docs/plan_calidad.md.

Cada regla recibe un DataFrame y devuelve una Serie booleana: True = el registro FALLA la regla.
- Reglas BLOQUEANTES: el registro va a cuarentena.
- Reglas de ADVERTENCIA: el registro pasa a Plata, marcado en la columna 'advertencias'.
"""
from dataclasses import dataclass
from datetime import date
from typing import Callable

import pandas as pd

from src.utils import cargar_config

CAL = cargar_config()["calidad"]
TRAZABILIDAD = ["fuente", "fecha_captura", "archivo_origen"]


@dataclass
class Regla:
    codigo: str
    dimension: str
    tipo: str  # "bloqueante" | "advertencia"
    descripcion: str
    evaluar: Callable[[pd.DataFrame], pd.Series]


# ----------------------------------------------------------------------------- reglas genéricas
def cq01_completitud(columnas):
    return Regla("CQ-01", "Completitud", "bloqueante",
                 f"Campos obligatorios no nulos: {', '.join(columnas)}",
                 lambda df: df[columnas].isna().any(axis=1))


def cq02_fecha_valida():
    def evaluar(df):
        hoy = pd.Timestamp(date.today())
        return df["fecha"].isna() | (df["fecha"] > hoy)
    return Regla("CQ-02", "Exactitud sintáctica", "bloqueante", "Fecha válida y no futura", evaluar)


def cq05_unicidad(llave):
    return Regla("CQ-05", "Unicidad", "bloqueante",
                 f"Sin duplicados por llave ({' + '.join(llave)}); se conserva el primero",
                 lambda df: df.duplicated(subset=llave, keep="first"))


def cq12_trazabilidad():
    return Regla("CQ-12", "Trazabilidad", "bloqueante",
                 "Cada registro conserva fuente, fecha_captura y archivo_origen",
                 lambda df: df[TRAZABILIDAD].isna().any(axis=1))


# ----------------------------------------------------------------------------- reglas SNIIM
def cq03_rango_precio():
    def evaluar(df):
        cols = ["precio_min", "precio_max", "precio_frec"]
        fuera = (df[cols] < CAL["precio_min_kg"]) | (df[cols] > CAL["precio_max_kg"])
        return fuera.any(axis=1)
    return Regla("CQ-03", "Exactitud semántica", "bloqueante",
                 f"{CAL['precio_min_kg']} <= precio $/kg <= {CAL['precio_max_kg']}", evaluar)


def cq04_consistencia_precios():
    return Regla("CQ-04", "Consistencia", "bloqueante",
                 "precio_min <= precio_frec <= precio_max",
                 lambda df: ~((df["precio_min"] <= df["precio_frec"]) & (df["precio_frec"] <= df["precio_max"])))


def cq09_variacion_diaria():
    def evaluar(df):
        orden = df.sort_values("fecha")
        grupo = orden.groupby(["producto", "destino", "presentacion"])["precio_frec"]
        variacion = (orden["precio_frec"] / grupo.shift(1) - 1).abs()
        return (variacion > CAL["variacion_diaria_max"]).reindex(df.index).fillna(False)
    return Regla("CQ-09", "Credibilidad", "advertencia",
                 f"Variación diaria del precio frecuente <= {CAL['variacion_diaria_max']:.0%}", evaluar)


def cq11_conformidad(productos_validos, origen_valido):
    def evaluar(df):
        producto_ok = df["producto"].isin(productos_validos)
        origen_ok = df["origen"] == origen_valido
        destino_ok = df["destino"].fillna("").str.contains(":", regex=False)
        return ~(producto_ok & origen_ok & destino_ok)
    return Regla("CQ-11", "Conformidad", "bloqueante",
                 "Producto y origen del catálogo; destino con formato 'Estado: Mercado'", evaluar)


# ----------------------------------------------------------------------------- reglas Open-Meteo
def cq06_rango_clima():
    def evaluar(df):
        t = df[["temp_min", "temp_media", "temp_max"]]
        return (df["precipitacion_mm"] < 0) | ((t < CAL["temperatura_min"]) | (t > CAL["temperatura_max"])).any(axis=1)
    return Regla("CQ-06", "Exactitud semántica", "bloqueante",
                 f"precipitación >= 0; {CAL['temperatura_min']} <= temperatura <= {CAL['temperatura_max']} °C", evaluar)


def cq07_consistencia_temperaturas():
    return Regla("CQ-07", "Consistencia", "bloqueante", "temp_min <= temp_media <= temp_max",
                 lambda df: ~((df["temp_min"] <= df["temp_media"]) & (df["temp_media"] <= df["temp_max"])))


# ----------------------------------------------------------------------------- reglas Banxico
def cq08_rango_tipo_cambio():
    return Regla("CQ-08", "Exactitud semántica", "bloqueante",
                 f"{CAL['tipo_cambio_min']} <= tipo de cambio <= {CAL['tipo_cambio_max']} MXN/USD",
                 lambda df: (df["tipo_cambio"] < CAL["tipo_cambio_min"]) | (df["tipo_cambio"] > CAL["tipo_cambio_max"]))


# ----------------------------------------------------------------------------- catálogo por fuente
def reglas_de(fuente: str) -> list:
    cfg = cargar_config()["fuentes"]
    if fuente == "sniim":
        return [
            cq12_trazabilidad(),
            cq01_completitud(["fecha", "producto", "destino", "precio_min", "precio_max", "precio_frec"]),
            cq02_fecha_valida(),
            cq11_conformidad(list(cfg["sniim"]["productos"].values()), cfg["sniim"]["origen"]),
            cq03_rango_precio(),
            cq04_consistencia_precios(),
            cq05_unicidad(["fecha", "producto", "destino", "presentacion"]),
            cq09_variacion_diaria(),
        ]
    if fuente == "open_meteo":
        return [
            cq12_trazabilidad(),
            cq01_completitud(["fecha", "precipitacion_mm", "temp_max", "temp_min", "temp_media"]),
            cq02_fecha_valida(),
            cq06_rango_clima(),
            cq07_consistencia_temperaturas(),
            cq05_unicidad(["fecha"]),
        ]
    if fuente == "banxico":
        return [
            cq12_trazabilidad(),
            cq01_completitud(["fecha", "tipo_cambio"]),
            cq02_fecha_valida(),
            cq08_rango_tipo_cambio(),
            cq05_unicidad(["fecha"]),
        ]
    raise ValueError(f"Fuente desconocida: {fuente}")


# ----------------------------------------------------------------------------- motor
def aplicar_puertas(df: pd.DataFrame, reglas: list):
    """Evalúa todas las reglas. Devuelve (aceptados, cuarentena, resumen_por_regla).
    Un registro que falla varias reglas bloqueantes lista todos los códigos."""
    df = df.copy()
    fallas = pd.Series([[] for _ in range(len(df))], index=df.index)
    avisos = pd.Series([[] for _ in range(len(df))], index=df.index)
    resumen = []

    for r in reglas:
        # Unicidad y advertencias se evalúan solo entre los registros que siguen siendo válidos
        # (así un dato ya rechazado no "cuenta" como duplicado ni como precio de referencia)
        base = df[fallas.str.len() == 0] if (r.codigo == "CQ-05" or r.tipo == "advertencia") else df
        mascara = r.evaluar(base).reindex(df.index).fillna(False).astype(bool)
        destino = fallas if r.tipo == "bloqueante" else avisos
        for i in df.index[mascara]:
            destino[i] = destino[i] + [r.codigo]
        resumen.append({"codigo": r.codigo, "dimension": r.dimension, "tipo": r.tipo,
                        "descripcion": r.descripcion, "registros_que_fallan": int(mascara.sum())})

    rechazados = fallas.str.len() > 0
    descripciones = {r.codigo: r.descripcion for r in reglas}

    cuarentena = df[rechazados].copy()
    cuarentena["regla_fallida"] = fallas[rechazados].str.join(";")
    cuarentena["motivo"] = fallas[rechazados].apply(lambda cs: " | ".join(descripciones[c] for c in cs))
    cuarentena["fecha_rechazo"] = pd.Timestamp.now().isoformat(timespec="seconds")

    aceptados = df[~rechazados].copy()
    aceptados["advertencias"] = avisos[~rechazados].str.join(";")
    return aceptados, cuarentena, resumen