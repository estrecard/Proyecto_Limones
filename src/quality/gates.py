"""Puerta de calidad automática con Pandera (ISO/IEC 25012) — reglas CQ-01 a CQ-12 de docs/plan_calidad.md.

Cada fuente tiene un esquema Pandera (columnas, tipos, nulos, rangos y reglas entre columnas).
La validación se hace en modo "lazy": Pandera junta TODAS las fallas con el índice del registro,
y con eso cada registro inválido se envía a cuarentena con el código y el motivo de cada regla
que no cumplió. Nunca se borra nada en silencio.

- Reglas BLOQUEANTES → cuarentena.
- CQ-09 (advertencia) → el registro pasa a Plata marcado en la columna 'advertencias'.
"""
import re
from datetime import date

import pandas as pd

try:  # Pandera >= 0.24 recomienda el submódulo pandas
    import pandera.pandas as pa
except ImportError:  # versiones anteriores
    import pandera as pa
from pandera.errors import SchemaErrors

from src.utils import cargar_config

CAL = cargar_config()["calidad"]
TRAZABILIDAD = ["fuente", "fecha_captura", "archivo_origen"]

DESCRIPCIONES = {
    "CQ-01": "Completitud: campo obligatorio vacío",
    "CQ-02": "Exactitud sintáctica: fecha inválida o futura",
    "CQ-03": f"Exactitud semántica: precio fuera de [{CAL['precio_min_kg']}, {CAL['precio_max_kg']}] $/kg",
    "CQ-04": "Consistencia: no se cumple precio_min <= precio_frec <= precio_max",
    "CQ-05": "Unicidad: registro duplicado (se conserva el primero)",
    "CQ-06": f"Exactitud semántica: lluvia < 0 o temperatura fuera de [{CAL['temperatura_min']}, {CAL['temperatura_max']}] °C",
    "CQ-07": "Consistencia: no se cumple temp_min <= temp_media <= temp_max",
    "CQ-08": f"Exactitud semántica: tipo de cambio fuera de [{CAL['tipo_cambio_min']}, {CAL['tipo_cambio_max']}]",
    "CQ-09": f"Credibilidad: variación diaria del precio frecuente > {CAL['variacion_diaria_max']:.0%}",
    "CQ-11": "Conformidad: producto, origen o destino fuera del catálogo",
    "CQ-12": "Trazabilidad: falta fuente, fecha_captura o archivo_origen",
    "CQ-ESQ": "Esquema: tipo de dato inválido (no se pudo convertir)",
}
DIMENSION = {"CQ-01": "Completitud", "CQ-02": "Exactitud sintáctica", "CQ-03": "Exactitud semántica",
             "CQ-04": "Consistencia", "CQ-05": "Unicidad", "CQ-06": "Exactitud semántica",
             "CQ-07": "Consistencia", "CQ-08": "Exactitud semántica", "CQ-09": "Credibilidad",
             "CQ-11": "Conformidad", "CQ-12": "Trazabilidad", "CQ-ESQ": "Conformidad de esquema"}


def regla(codigo, funcion, element_wise=False):
    """Crea un Check de Pandera identificado con el código de la regla."""
    return pa.Check(funcion, element_wise=element_wise, name=codigo, error=f"{codigo}: {DESCRIPCIONES[codigo]}")


def es_fecha(x):
    return isinstance(x, (pd.Timestamp, date))


def no_futura(x):
    return pd.Timestamp(x) <= pd.Timestamp(date.today())


def texto(checks=()):
    return pa.Column(None, nullable=False,
                     checks=[regla("CQ-ESQ", lambda x: isinstance(x, str), element_wise=True), *checks])


def numero(checks=()):
    return pa.Column(float, nullable=False, coerce=True, checks=list(checks))


def columnas_trazabilidad():
    return {c: texto() for c in TRAZABILIDAD}


# ----------------------------------------------------------------------------- esquemas por fuente
def esquema_sniim():
    cfg = cargar_config()["fuentes"]["sniim"]
    productos = list(cfg["productos"].values())
    en_rango = lambda s: s.between(CAL["precio_min_kg"], CAL["precio_max_kg"])
    return {
        "esquema": pa.DataFrameSchema(
            {
                "fecha": pa.Column(None, nullable=False, checks=[
                    regla("CQ-02", es_fecha, element_wise=True), regla("CQ-02", no_futura, element_wise=True)]),
                "producto": texto(checks=[regla("CQ-11", lambda s: s.isin(productos))]),
                "origen": texto(checks=[regla("CQ-11", lambda s: s == cfg["origen"])]),
                "destino": texto(checks=[regla("CQ-11", lambda s: s.str.contains(":", regex=False))]),
                "presentacion": pa.Column(None, nullable=True),
                "precio_min": numero([regla("CQ-03", en_rango)]),
                "precio_max": numero([regla("CQ-03", en_rango)]),
                "precio_frec": numero([regla("CQ-03", en_rango)]),
                **columnas_trazabilidad(),
            },
            checks=[regla("CQ-04", lambda df: (df["precio_min"] <= df["precio_frec"]) & (df["precio_frec"] <= df["precio_max"]))],
            strict=False,  # Plata conserva columnas adicionales (calidad, sección, observaciones...)
            name="sniim",
        ),
        "llave": ["fecha", "producto", "destino", "presentacion"],
        "advertencias": cq09_variacion_diaria,
    }


def esquema_open_meteo():
    temp = lambda s: s.between(CAL["temperatura_min"], CAL["temperatura_max"])
    return {
        "esquema": pa.DataFrameSchema(
            {
                "fecha": pa.Column(None, nullable=False, checks=[
                    regla("CQ-02", es_fecha, element_wise=True), regla("CQ-02", no_futura, element_wise=True)]),
                "precipitacion_mm": numero([regla("CQ-06", lambda s: s >= 0)]),
                "temp_min": numero([regla("CQ-06", temp)]),
                "temp_media": numero([regla("CQ-06", temp)]),
                "temp_max": numero([regla("CQ-06", temp)]),
                **columnas_trazabilidad(),
            },
            checks=[regla("CQ-07", lambda df: (df["temp_min"] <= df["temp_media"]) & (df["temp_media"] <= df["temp_max"]))],
            strict=False,
            name="open_meteo",
        ),
        "llave": ["fecha"],
        "advertencias": None,
    }


def esquema_banxico():
    return {
        "esquema": pa.DataFrameSchema(
            {
                "fecha": pa.Column(None, nullable=False, checks=[
                    regla("CQ-02", es_fecha, element_wise=True), regla("CQ-02", no_futura, element_wise=True)]),
                "tipo_cambio": numero([regla("CQ-08", lambda s: s.between(CAL["tipo_cambio_min"], CAL["tipo_cambio_max"]))]),
                **columnas_trazabilidad(),
            },
            strict=False,
            name="banxico",
        ),
        "llave": ["fecha"],
        "advertencias": None,
    }


def reglas_de(fuente: str) -> dict:
    esquemas = {"sniim": esquema_sniim, "open_meteo": esquema_open_meteo, "banxico": esquema_banxico}
    if fuente not in esquemas:
        raise ValueError(f"Fuente desconocida: {fuente}")
    return esquemas[fuente]()


# ----------------------------------------------------------------------------- advertencia CQ-09
def cq09_variacion_diaria(df: pd.DataFrame) -> pd.Series:
    orden = df.sort_values("fecha")
    grupo = orden.groupby(["producto", "destino", "presentacion"], dropna=False)["precio_frec"]
    variacion = (orden["precio_frec"] / grupo.shift(1) - 1).abs()
    return (variacion > CAL["variacion_diaria_max"]).reindex(df.index).fillna(False)


# ----------------------------------------------------------------------------- motor
def codigo_de_falla(columna, check) -> str:
    """Traduce una falla de Pandera al código de regla del plan de calidad."""
    m = re.search(r"CQ-(\d+|ESQ)", str(check))
    if m:
        return m.group(0)
    if str(check) == "not_nullable":
        if columna in TRAZABILIDAD:
            return "CQ-12"
        if columna == "fecha":
            return "CQ-02"
        return "CQ-01"
    return "CQ-ESQ"  # coerce_dtype u otra falla de tipo


def fallas_por_registro(df: pd.DataFrame, esquema) -> dict:
    """Valida con Pandera (lazy) y devuelve {índice: {códigos de reglas que falló}}."""
    try:
        esquema.validate(df, lazy=True)
        return {}
    except SchemaErrors as err:
        fc = err.failure_cases
        sin_indice = fc[fc["index"].isna()]
        if len(sin_indice):  # falla de estructura (ej. falta una columna completa): no es un problema de registros
            raise RuntimeError(f"Error de esquema en {esquema.name}:\n{sin_indice[['column', 'check']].to_string()}")
        fallas = {}
        for _, f in fc.iterrows():
            fallas.setdefault(f["index"], set()).add(codigo_de_falla(f["column"], f["check"]))
        return fallas


def aplicar_puertas(df: pd.DataFrame, reglas: dict):
    """Aplica la puerta de calidad. Devuelve (aceptados, cuarentena, resumen_por_regla)."""
    df = df.reset_index(drop=True).copy()
    esquema = reglas["esquema"]

    # 1) Esquema, tipos, nulos, rangos y reglas entre columnas
    fallas = fallas_por_registro(df, esquema)

    # 2) Unicidad, evaluada solo entre los registros que siguen siendo válidos
    validos = df.drop(index=list(fallas))
    unicidad = pa.DataFrameSchema(checks=[regla("CQ-05", lambda d: ~d.duplicated(subset=reglas["llave"], keep="first"))])
    for i, cods in fallas_por_registro(validos, unicidad).items():
        fallas.setdefault(i, set()).update(cods)

    rechazados = df.index.isin(list(fallas))
    cuarentena = df[rechazados].copy()
    cuarentena["regla_fallida"] = [";".join(sorted(fallas[i])) for i in cuarentena.index]
    cuarentena["motivo"] = [" | ".join(DESCRIPCIONES[c] for c in sorted(fallas[i])) for i in cuarentena.index]
    cuarentena["fecha_rechazo"] = pd.Timestamp.now().isoformat(timespec="seconds")

    # 3) Advertencias (no bloquean): CQ-09
    aceptados = df[~rechazados].copy()
    aceptados["advertencias"] = ""
    if reglas["advertencias"] is not None and len(aceptados):
        aceptados.loc[reglas["advertencias"](aceptados), "advertencias"] = "CQ-09"

    conteo = {}
    for cods in fallas.values():
        for c in cods:
            conteo[c] = conteo.get(c, 0) + 1
    if len(aceptados):
        conteo["CQ-09"] = int((aceptados["advertencias"] == "CQ-09").sum())
    resumen = [{"codigo": c, "dimension": DIMENSION[c], "tipo": "advertencia" if c == "CQ-09" else "bloqueante",
                "descripcion": DESCRIPCIONES[c], "registros_que_fallan": n} for c, n in sorted(conteo.items())]
    return aceptados, cuarentena, resumen
