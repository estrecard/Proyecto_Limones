"""Capa Oro: limpieza estadística, integración de fuentes y preparación para el modelado (Entrega E1).

Etapas (cada una deja evidencia en docs/E1/reporte_limpieza.md):
  1. Resolución de conflictos de esquema del SNIIM (varias presentaciones el mismo día, nombres, texto libre)
  2. Diagnóstico de valores faltantes (MCAR / MAR / MNAR)
  3. Detección y tratamiento de atípicos y ruido (Z-score robusto con MAD e IQR sobre residuos)
  4. Reducción de datos (selección de variables y agregación diaria → semanal)
  5. Imputación justificada (interpolación de huecos cortos; LOCF para el tipo de cambio)
  6. Integración de las tres fuentes por semana
  7. Discretización y jerarquías conceptuales (tiempo, geografía, calibre, lluvia, precio)
  8. Normalización y estandarización (Min-Max y Z-score)

Uso:
    python -m src.transform.gold
"""
import json
import re
from datetime import datetime

import numpy as np
import pandas as pd

from src.utils import RAIZ, obtener_logger, ruta

logger = obtener_logger("gold")

# ----------------------------------------------------------------------------- parámetros (justificados en el reporte)
VENTANA_RUIDO = 15        # días hábiles (~3 semanas) para la mediana móvil que separa tendencia de ruido
UMBRAL_Z_ROBUSTO = 3.5    # Iglewicz y Hoaglin (1993): |z modificado| > 3.5 = atípico
FACTOR_IQR = 1.5          # regla de Tukey
MAX_DIAS_RUIDO = 2        # una desviación que dura más días seguidos es un cambio de nivel real, no ruido
HUECO_MAX_SEMANAS = 2     # huecos interiores de hasta 2 semanas se interpolan; más largos se dejan vacíos
MIN_SEMANAS_SERIE = 26    # series con menos de medio año de datos no se usan en la tabla semanal

# Jerarquías conceptuales
REGION = {
    "Baja California Sur": "Noroeste", "Sonora": "Noroeste", "Sinaloa": "Noroeste",
    "Chihuahua": "Norte", "Coahuila": "Norte", "Durango": "Norte", "Nuevo León": "Norte",
    "Aguascalientes": "Centro-Norte", "San Luis Potosí": "Centro-Norte", "Zacatecas": "Centro-Norte",
    "Jalisco": "Occidente", "Colima": "Occidente",
    "Veracruz": "Golfo-Sureste", "Tabasco": "Golfo-Sureste",
}
TAMANO = {
    "Limón c/semilla # 2": "Chico", "Limón c/semilla # 3": "Mediano",
    "Limón c/semilla # 4": "Grande", "Limón c/semilla # 5": "Grande",
    "Limón c/semilla sin clasificación": "Sin clasificar",
}
CALIBRE = {
    "Limón c/semilla # 2": "#2", "Limón c/semilla # 3": "#3", "Limón c/semilla # 4": "#4",
    "Limón c/semilla # 5": "#5", "Limón c/semilla sin clasificación": "S/C",
}


def temporada(mes: int) -> str:
    """Ciclo del limón en Colima: poca fruta en invierno-primavera, mucha con las lluvias."""
    if mes in (1, 2, 3, 4):
        return "Baja oferta (ene-abr)"
    if mes in (5, 6, 7, 8, 9):
        return "Alta oferta (may-sep)"
    return "Transición (oct-dic)"


def tendencia_observacion(texto) -> str:
    """Normaliza el texto libre de 'observaciones' a una categoría (corrige errores como 'A LA ALAZA')."""
    if pd.isna(texto):
        return "Sin observación"
    t = str(texto).upper()
    if re.search(r"ALA?ZA|ESCASEZ|DEMANDA", t):
        return "Alza"
    if re.search(r"BAJA|INGRESO", t):
        return "Baja"
    return "Otra"


# ----------------------------------------------------------------------------- 1. conflictos de esquema SNIIM
def consolidar_sniim(s: pd.DataFrame, rep: dict) -> pd.DataFrame:
    """Un registro por (fecha, mercado, calibre). Cuando el mercado reporta el mismo día varias
    presentaciones (caja de 20 kg, arpilla de 15 kg, kilogramo...), todas ya vienen en $/kg (PreciosPorId=2),
    así que se resuelve con la MEDIANA del precio frecuente (robusta a una presentación extrema)."""
    s = s.copy()
    s["destino"] = s["destino"].str.replace('"', "", regex=False).str.strip()
    s["tendencia_obs"] = s["observaciones"].apply(tendencia_observacion)
    llave = ["fecha", "destino", "producto"]
    n_por_llave = s.groupby(llave).size()
    rep["conflictos"] = {
        "registros_plata": len(s),
        "llaves_unicas": int(len(n_por_llave)),
        "llaves_con_varias_presentaciones": int((n_por_llave > 1).sum()),
        "presentaciones": s["presentacion"].value_counts().to_dict(),
        "observaciones_texto_distintos": int(s["observaciones"].nunique()),
        "observaciones_categorias": s["tendencia_obs"].value_counts().to_dict(),
    }
    d = (s.groupby(llave)
         .agg(precio_frec=("precio_frec", "median"), precio_min=("precio_min", "min"),
              precio_max=("precio_max", "max"), n_presentaciones=("presentacion", "nunique"),
              tendencia_obs=("tendencia_obs", lambda x: x.mode().iat[0]),
              estado=("estado_destino", "first"))
         .reset_index())
    d["calibre"] = d["producto"].map(CALIBRE)
    return d


# ----------------------------------------------------------------------------- 2. diagnóstico de faltantes
def diagnosticar_faltantes(d: pd.DataFrame, rep: dict) -> pd.DataFrame:
    """Construye el panel completo (día hábil × serie activa) y estudia el mecanismo de los huecos."""
    calendario = pd.DatetimeIndex(sorted(d["fecha"].unique()))  # días en que el SNIIM publicó algo
    partes = []
    for (dest, prod), g in d.groupby(["destino", "producto"]):
        dias = calendario[(calendario >= g["fecha"].min()) & (calendario <= g["fecha"].max())]
        p = pd.DataFrame({"fecha": dias, "destino": dest, "producto": prod})
        partes.append(p)
    panel = pd.concat(partes).merge(d, on=["fecha", "destino", "producto"], how="left")
    panel["faltante"] = panel["precio_frec"].isna()
    panel["mes"] = panel["fecha"].dt.month
    panel["temporada"] = panel["mes"].apply(temporada)
    panel["dia_semana"] = panel["fecha"].dt.dayofweek.map(
        {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"})

    # ¿Depende el faltante de variables observadas? (si sí, NO es MCAR)
    por_temporada = panel.groupby("temporada")["faltante"].mean().mul(100).round(2)
    por_dia = panel.groupby("dia_semana")["faltante"].mean().mul(100).round(2)
    por_serie = (panel.groupby(["destino", "producto"])["faltante"].mean().mul(100).round(1)
                 .sort_values(ascending=False))

    pruebas = {}
    try:
        from scipy.stats import chi2_contingency, mannwhitneyu
        for var in ["temporada", "dia_semana"]:
            tabla = pd.crosstab(panel[var], panel["faltante"])
            chi2, p, gl, _ = chi2_contingency(tabla)
            pruebas[var] = {"chi2": round(float(chi2), 2), "gl": int(gl), "p_valor": float(p)}
        # ¿El precio cercano al hueco es distinto? (indicio de MNAR: no se reporta cuando el precio es extremo)
        panel = panel.sort_values(["destino", "producto", "fecha"])
        panel["precio_previo"] = panel.groupby(["destino", "producto"])["precio_frec"].ffill().shift(1)
        a = panel.loc[panel["faltante"], "precio_previo"].dropna()
        b = panel.loc[~panel["faltante"], "precio_previo"].dropna()
        u, p = mannwhitneyu(a, b)
        pruebas["precio_previo"] = {"mediana_antes_de_hueco": float(a.median()),
                                    "mediana_sin_hueco": float(b.median()), "p_valor": float(p)}
    except ImportError:
        logger.warning("scipy no disponible: el diagnóstico se reporta solo de forma descriptiva")

    rep["faltantes"] = {
        "dias_habiles_calendario": int(len(calendario)),
        "celdas_panel": int(len(panel)),
        "faltantes": int(panel["faltante"].sum()),
        "pct_faltante": round(100 * panel["faltante"].mean(), 2),
        "pct_por_temporada": por_temporada.to_dict(),
        "pct_por_dia_semana": por_dia.to_dict(),
        "series_mas_incompletas": {f"{k[0]} | {k[1]}": v for k, v in por_serie.head(6).items()},
        "pruebas": pruebas,
        "faltantes_otras_fuentes": {
            "open_meteo": "0 días faltantes (serie diaria completa)",
            "banxico": "fines de semana y festivos: el FIX no se publica (faltante estructural)",
        },
    }
    return panel


# ----------------------------------------------------------------------------- 3. atípicos y ruido
def tratar_atipicos(d: pd.DataFrame, rep: dict) -> pd.DataFrame:
    """El precio tiene una estacionalidad fuerte: un umbral global marcaría como 'atípico' todo febrero.
    Por eso se separa la tendencia local (mediana móvil de 15 días hábiles) y se buscan atípicos en el RESIDUO.

    Además el precio es 'pegajoso': se repite igual muchos días, así que la mayoría de los residuos son 0
    y, serie por serie, la MAD y el IQR valen 0 (dividir entre 0 o marcar cualquier cambio).
    Solución: residuo RELATIVO (%), y la escala (MAD e IQR) se estima con los residuos distintos de 0
    de todas las series juntas (al ser porcentajes son comparables entre mercados y calibres)."""
    d = d.sort_values(["destino", "producto", "fecha"]).copy()
    grupo = d.groupby(["destino", "producto"])["precio_frec"]
    d["tendencia_local"] = grupo.transform(lambda x: x.rolling(VENTANA_RUIDO, center=True, min_periods=5).median())
    d["residuo_pct"] = (d["precio_frec"] - d["tendencia_local"]) / d["tendencia_local"]

    se_mueve = d["residuo_pct"].abs() > 1e-9
    base = d.loc[se_mueve, "residuo_pct"]
    mediana = base.median()
    mad = (base - mediana).abs().median()
    q1, q3 = base.quantile([0.25, 0.75])
    iqr = q3 - q1
    lim_inf, lim_sup = q1 - FACTOR_IQR * iqr, q3 + FACTOR_IQR * iqr

    # Método 1: Z-score robusto (Iglewicz y Hoaglin): z = 0.6745 (x - mediana) / MAD
    d["z_robusto"] = 0.6745 * (d["residuo_pct"] - mediana) / mad
    d["atipico_z"] = se_mueve & (d["z_robusto"].abs() > UMBRAL_Z_ROBUSTO)
    # Método 2: IQR de Tukey
    d["atipico_iqr"] = se_mueve & ((d["residuo_pct"] < lim_inf) | (d["residuo_pct"] > lim_sup))

    # Tratamiento: solo se corrige lo que AMBOS métodos marcan (evidencia más fuerte) y además es AISLADO
    # (≤ 2 días seguidos). Si la desviación persiste más días, es un cambio de nivel real: se marca pero no se toca.
    ambos = d["atipico_z"] & d["atipico_iqr"]
    racha = ambos.groupby([d["destino"], d["producto"], (~ambos).cumsum()]).transform("sum")
    d["atipico_persistente"] = ambos & (racha > MAX_DIAS_RUIDO)
    d["atipico"] = ambos & ~d["atipico_persistente"]
    d["precio_frec_original"] = d["precio_frec"]
    d["precio_frec_limpio"] = np.where(d["atipico"], d["tendencia_local"], d["precio_frec"])

    ejemplos = (d[d["atipico"]]
                .reindex(columns=["fecha", "destino", "calibre", "precio_frec", "tendencia_local", "z_robusto"])
                .sort_values("z_robusto", key=abs, ascending=False).head(8))
    rep["atipicos"] = {
        "registros": len(d),
        "pct_residuo_cero": round(100 * (1 - se_mueve.mean()), 1),
        "residuos_distintos_de_cero": int(se_mueve.sum()),
        "mediana_pct": round(100 * float(mediana), 2), "mad_pct": round(100 * float(mad), 2),
        "limites_iqr_pct": [round(100 * float(lim_inf), 1), round(100 * float(lim_sup), 1)],
        "umbral_z_pct": round(100 * float(mediana + UMBRAL_Z_ROBUSTO * mad / 0.6745), 1),
        "marcados_z_robusto": int(d["atipico_z"].sum()),
        "marcados_iqr": int(d["atipico_iqr"].sum()),
        "marcados_ambos": int(ambos.sum()),
        "persistentes_no_corregidos": int(d["atipico_persistente"].sum()),
        "marcados_ambos_corregidos": int(d["atipico"].sum()),
        "pct_corregidos": round(100 * d["atipico"].mean(), 2),
        "ejemplos": ejemplos.assign(fecha=ejemplos["fecha"].dt.strftime("%d/%m/%Y")).round(2).to_dict("records"),
    }
    return d


# ----------------------------------------------------------------------------- 4-5. reducción e imputación
def semanal_sniim(d: pd.DataFrame, rep: dict) -> pd.DataFrame:
    """Reducción por agregación: de ~19 mil registros diarios a una serie semanal por mercado y calibre.
    La semana es el horizonte que pidió el cliente (pronóstico a 2-4 semanas)."""
    d = d.copy()
    d["semana"] = d["fecha"].dt.to_period("W-SUN").dt.start_time
    w = (d.groupby(["destino", "producto", "semana"])
         .agg(precio=("precio_frec_limpio", "mean"), precio_min=("precio_min", "min"),
              precio_max=("precio_max", "max"), dias_reportados=("fecha", "nunique"),
              atipicos_corregidos=("atipico", "sum"), estado=("estado", "first"), calibre=("calibre", "first"))
         .reset_index())

    # Panel semanal completo dentro del periodo activo de cada serie → aquí aparecen los huecos
    partes = []
    for (dest, prod), g in w.groupby(["destino", "producto"]):
        semanas = pd.date_range(g["semana"].min(), g["semana"].max(), freq="W-MON")
        partes.append(g.set_index("semana").reindex(semanas).rename_axis("semana").reset_index()
                      .assign(destino=dest, producto=prod))
    w = pd.concat(partes, ignore_index=True)
    w["estado"] = w.groupby(["destino", "producto"])["estado"].transform(lambda x: x.ffill().bfill())
    w["calibre"] = w.groupby(["destino", "producto"])["calibre"].transform(lambda x: x.ffill().bfill())
    faltan_antes = int(w["precio"].isna().sum())

    # Imputación: interpolación lineal SOLO en huecos interiores de hasta 2 semanas
    w["imputado"] = False
    for clave, g in w.groupby(["destino", "producto"]):
        interp = g["precio"].interpolate(method="linear", limit=HUECO_MAX_SEMANAS, limit_area="inside")
        # 'limit' rellena los primeros N de un hueco largo; se revierte para huecos > N
        hueco = g["precio"].isna()
        largo_hueco = hueco.groupby((~hueco).cumsum()).transform("sum")
        interp[hueco & (largo_hueco > HUECO_MAX_SEMANAS)] = np.nan
        w.loc[g.index, "imputado"] = hueco & interp.notna()
        w.loc[g.index, "precio"] = interp
    w["dias_reportados"] = w["dias_reportados"].fillna(0).astype(int)
    w["atipicos_corregidos"] = w["atipicos_corregidos"].fillna(0).astype(int)

    # Selección: series demasiado cortas no sirven para modelar
    largo = w.dropna(subset=["precio"]).groupby(["destino", "producto"]).size()
    validas = largo[largo >= MIN_SEMANAS_SERIE].index
    descartadas = largo[largo < MIN_SEMANAS_SERIE]
    w = w.set_index(["destino", "producto"]).loc[validas].reset_index()

    rep["reduccion"] = {
        "registros_diarios": len(d),
        "registros_semanales": len(w),
        "factor_reduccion": round(len(d) / max(len(w), 1), 1),
        "series_validas": len(validas),
        "series_descartadas": {f"{k[0]} | {k[1]}": int(v) for k, v in descartadas.items()},
        "variables_eliminadas_constantes": ["calidad (siempre 'Primera')", "origen (siempre 'Colima')",
                                            "seccion (siempre 'Frutas')", "fuente"],
        "variables_eliminadas_tecnicas": ["fecha_captura", "archivo_origen", "producto_id", "advertencias"],
    }
    rep["imputacion"] = {
        "semanas_vacias_antes": faltan_antes,
        "imputadas_interpolacion": int(w["imputado"].sum()),
        "vacias_despues": int(w["precio"].isna().sum()),
    }
    return w


def semanal_clima(o: pd.DataFrame) -> pd.DataFrame:
    o = o.sort_values("fecha").set_index("fecha")
    o["lluvia_30d_mm"] = o["precipitacion_mm"].rolling("30D").sum()
    w = o.resample("W-SUN").agg({"precipitacion_mm": "sum", "temp_media": "mean", "temp_max": "max",
                                 "temp_min": "min", "lluvia_30d_mm": "last"})
    w.index = w.index.to_period("W-SUN").start_time
    return w.rename(columns={"precipitacion_mm": "lluvia_semana_mm"}).rename_axis("semana").reset_index()


def semanal_dolar(b: pd.DataFrame, rep: dict) -> pd.DataFrame:
    """El FIX no se publica en fines de semana ni festivos. El valor vigente es el último publicado,
    así que se usa LOCF (última observación hacia adelante) en el calendario diario y luego se promedia por semana."""
    b = b.sort_values("fecha").set_index("fecha")["tipo_cambio"]
    diario = b.reindex(pd.date_range(b.index.min(), b.index.max(), freq="D"))
    rep["imputacion"]["tipo_cambio_dias_locf"] = int(diario.isna().sum())
    diario = diario.ffill()
    w = diario.resample("W-SUN").mean()
    w.index = w.index.to_period("W-SUN").start_time
    return w.rename("tipo_cambio").rename_axis("semana").reset_index()


# ----------------------------------------------------------------------------- 6-8. integración, discretización, normalización
def integrar(w: pd.DataFrame, clima: pd.DataFrame, dolar: pd.DataFrame, rep: dict) -> pd.DataFrame:
    t = w.merge(clima, on="semana", how="left").merge(dolar, on="semana", how="left")
    rep["integracion"] = {
        "filas": len(t),
        "semanas_sin_clima": int(t["temp_media"].isna().sum()),
        "semanas_sin_tipo_cambio": int(t["tipo_cambio"].isna().sum()),
    }
    return t


def discretizar(t: pd.DataFrame, rep: dict) -> pd.DataFrame:
    t = t.copy()
    # Jerarquía de tiempo: semana → mes → trimestre → año ; y temporada del ciclo del limón
    t["mes"] = t["semana"].dt.month
    t["trimestre"] = t["semana"].dt.quarter
    t["anio"] = t["semana"].dt.year
    t["temporada"] = t["mes"].apply(temporada)
    # Jerarquía geográfica: mercado → estado → región
    t["region"] = t["estado"].map(REGION).fillna("Otra")
    # Jerarquía de producto: calibre → tamaño
    t["tamano"] = t["producto"].map(TAMANO)
    # Discretización por cuantiles (terciles): lluvia y precio
    t["lluvia_30d_nivel"] = pd.qcut(t["lluvia_30d_mm"].rank(method="first"), 3, labels=["Baja", "Media", "Alta"])
    t["precio_nivel"] = pd.qcut(t["precio"], 3, labels=["Bajo", "Medio", "Alto"])
    rep["discretizacion"] = {
        "lluvia_30d_cortes_mm": [round(float(x), 1) for x in t["lluvia_30d_mm"].quantile([1 / 3, 2 / 3])],
        "precio_cortes_kg": [round(float(x), 2) for x in t["precio"].quantile([1 / 3, 2 / 3])],
        "regiones": t.groupby("region")["destino"].nunique().to_dict(),
        "temporadas": t["temporada"].value_counts().to_dict(),
    }
    return t


def normalizar(t: pd.DataFrame, rep: dict):
    """Min-Max lleva cada variable a [0, 1] (útil para comparar en un tablero);
    Z-score la centra en 0 con desviación 1 (útil para modelos y PCA en E3)."""
    t = t.copy()
    params = {}
    for c in ["precio", "lluvia_30d_mm", "lluvia_semana_mm", "temp_media", "tipo_cambio"]:
        x = t[c]
        mn, mx, mu, sd = x.min(), x.max(), x.mean(), x.std()
        t[f"{c}_minmax"] = (x - mn) / (mx - mn)
        t[f"{c}_z"] = (x - mu) / sd
        params[c] = {"min": round(float(mn), 4), "max": round(float(mx), 4),
                     "media": round(float(mu), 4), "desv_std": round(float(sd), 4)}
    rep["normalizacion"] = params
    return t, params


def serie_nacional(t: pd.DataFrame) -> pd.DataFrame:
    """Variable objetivo de la E1 (pronóstico): precio semanal por calibre = mediana entre mercados."""
    n = (t.dropna(subset=["precio"]).groupby(["producto", "calibre", "semana"])
         .agg(precio_mediana=("precio", "median"), mercados=("destino", "nunique")).reset_index())
    extra = t.drop_duplicates("semana")[["semana", "lluvia_semana_mm", "lluvia_30d_mm", "temp_media",
                                          "temp_max", "tipo_cambio", "mes", "anio", "temporada"]]
    return n.merge(extra, on="semana", how="left")


# ----------------------------------------------------------------------------- reporte
def tabla_md(d: dict, col1="Concepto", col2="Valor") -> str:
    filas = "\n".join(f"| {k} | {v} |" for k, v in d.items())
    return f"| {col1} | {col2} |\n|---|---|\n{filas}"


def escribir_reporte(rep: dict):
    f, a, r, i, c = rep["faltantes"], rep["atipicos"], rep["reduccion"], rep["imputacion"], rep["conflictos"]
    pr = f.get("pruebas", {})

    def p(nombre):
        return f"{pr[nombre]['p_valor']:.3g}" if nombre in pr else "n/d"

    lineas = []
    if "temporada" in pr:
        lineas.append(f"- **Temporada:** p = {p('temporada')} → " + (
            "el porcentaje de faltantes **sí** cambia con la temporada." if pr["temporada"]["p_valor"] < 0.05 else
            "el porcentaje de faltantes **no** cambia de forma significativa entre temporadas."))
    if "dia_semana" in pr:
        lineas.append(f"- **Día de la semana:** p = {p('dia_semana')} → " + (
            "los faltantes **dependen del día** (algunos mercados no reportan ciertos días). La falta depende de una variable "
            "observada, así que el mecanismo **no es MCAR** sino **MAR**." if pr["dia_semana"]["p_valor"] < 0.05 else
            "no hay diferencia por día de la semana."))
    if "precio_previo" in pr:
        pp = pr["precio_previo"]
        lineas.append(f"- **Precio antes del hueco:** p = {p('precio_previo')}, mediana {pp['mediana_antes_de_hueco']:.2f} vs "
                      f"{pp['mediana_sin_hueco']:.2f} $/kg → " + (
            "los huecos aparecen cuando el precio venía **más bajo**: indicio de **MNAR** (el limón de Colima deja de llegar "
            "a ese mercado cuando no conviene enviarlo). Por eso los huecos largos **no se imputan**." if pp["p_valor"] < 0.05 else
            "el precio no difiere antes de un hueco: no hay evidencia de MNAR."))
    lineas.append("- **Conclusión:** los faltantes **no son MCAR**. Los huecos cortos se tratan como MAR (se pueden interpolar) "
                  "y los huecos largos como posible MNAR (se dejan vacíos y se documentan).")
    interpretacion = "\n".join(lineas)

    ejemplos = "\n".join(
        f"| {e['fecha']} | {e['destino']} | {e['calibre']} | {e['precio_frec']} | {e['tendencia_local']} | {e['z_robusto']} |"
        for e in a["ejemplos"])
    texto = f"""# Reporte de limpieza y preprocesamiento — E1

*Generado automáticamente por `src/transform/gold.py` el {rep['fecha']}.*

## 1. Resolución de conflictos de esquema (SNIIM)

El mismo día, mercado y calibre puede aparecer en varias presentaciones (caja de 20 kg, arpilla de 15 kg, kilogramo...).
Como todos los precios se pidieron en **$/kg calculado**, las presentaciones son comparables y se consolidan con la **mediana**.

{tabla_md({"Registros en Plata": c["registros_plata"], "Llaves únicas (fecha, mercado, calibre)": c["llaves_unicas"],
           "Llaves con varias presentaciones": c["llaves_con_varias_presentaciones"],
           "Textos distintos en 'observaciones'": c["observaciones_texto_distintos"],
           "Categorías después de normalizar": c["observaciones_categorias"]})}

Otras resoluciones: comillas eliminadas de los nombres de mercado; texto libre de observaciones normalizado
con expresiones regulares (corrige errores como "A LA ALAZA" o "a la alza") a *Alza / Baja / Otra*.

## 2. Valores faltantes: diagnóstico del mecanismo

Se construyó el panel completo **día hábil × serie (mercado, calibre)** dentro del periodo activo de cada serie.

{tabla_md({"Días hábiles con publicación del SNIIM": f["dias_habiles_calendario"], "Celdas del panel": f["celdas_panel"],
           "Celdas faltantes": f"{f['faltantes']} ({f['pct_faltante']} %)"})}

**Faltantes por temporada (%):** {f["pct_por_temporada"]}

**Faltantes por día de la semana (%):** {f["pct_por_dia_semana"]}

**Pruebas:**
- Independencia faltante × temporada (χ²): p = {p("temporada")}
- Independencia faltante × día de la semana (χ²): p = {p("dia_semana")}
- Precio previo a un hueco vs. sin hueco (Mann-Whitney): p = {p("precio_previo")}
  {f"(mediana {pr['precio_previo']['mediana_antes_de_hueco']:.2f} vs {pr['precio_previo']['mediana_sin_hueco']:.2f} $/kg)" if "precio_previo" in pr else ""}

**Interpretación:**
{interpretacion}
- Series más incompletas: {f["series_mas_incompletas"]}

**Otras fuentes:** Open-Meteo: {f["faltantes_otras_fuentes"]["open_meteo"]}. Banxico: {f["faltantes_otras_fuentes"]["banxico"]}.

## 3. Imputación justificada

| Caso | Mecanismo | Tratamiento | Justificación |
|---|---|---|---|
| Huecos interiores ≤ {HUECO_MAX_SEMANAS} semanas en la serie semanal | MAR (festivos, días sin reporte) | Interpolación lineal | El precio cambia de forma gradual; un hueco corto se aproxima bien con sus vecinos |
| Huecos > {HUECO_MAX_SEMANAS} semanas | Probable MNAR (el limón de Colima no llegó a ese mercado) | **No se imputa**, queda vacío | Inventar semanas sin comercio sesgaría el modelo |
| Tipo de cambio en fines de semana y festivos | Estructural | LOCF (último valor publicado) | El FIX publicado sigue vigente hasta la siguiente publicación |

{tabla_md({"Semanas vacías antes de imputar": i["semanas_vacias_antes"], "Semanas imputadas (interpolación)": i["imputadas_interpolacion"],
           "Semanas que quedan vacías (huecos largos)": i["vacias_despues"], "Días de tipo de cambio rellenados con LOCF": i.get("tipo_cambio_dias_locf", "n/d")})}

Cada valor imputado queda marcado en la columna `imputado` de la capa Oro.

## 4. Atípicos y ruido

El precio del limón es muy estacional: una regla global marcaría como "atípico" todo febrero. Por eso se calcula una
**tendencia local** (mediana móvil centrada de {VENTANA_RUIDO} días hábiles por serie) y los métodos se aplican al
**residuo relativo** = (precio − tendencia) / tendencia.

**Hallazgo:** el precio es "pegajoso" — el **{a["pct_residuo_cero"]} %** de los residuos es exactamente 0 porque el mismo
precio se repite varios días. Serie por serie, la MAD y el IQR valen 0, lo que hace inútiles ambos métodos
(el Z robusto divide entre 0 y el IQR marcaría cualquier cambio de precio). Por eso la escala se estima con los
**{a["residuos_distintos_de_cero"]} residuos distintos de 0, juntando todas las series** (al ser porcentajes son comparables):
mediana = {a["mediana_pct"]} %, MAD = {a["mad_pct"]} %.

- **Z-score robusto** (Iglewicz y Hoaglin, 1993): z = 0.6745·(x − mediana)/MAD; atípico si |z| > {UMBRAL_Z_ROBUSTO} (equivale a desviarse más de ~{a["umbral_z_pct"]} % de la tendencia).
- **IQR de Tukey**: atípico fuera de [{a["limites_iqr_pct"][0]} %, {a["limites_iqr_pct"][1]} %].

**Tratamiento:** solo se corrige lo que **ambos** métodos marcan **y es aislado** (≤ {MAX_DIAS_RUIDO} días seguidos): eso es ruido
(error de captura o una venta puntual). Si la desviación se sostiene más días, es un **cambio de nivel real** del mercado:
se marca en `atipico_persistente` pero **no se modifica**. El valor corregido va en `precio_frec_limpio` y el original
se conserva en `precio_frec_original` (nada se borra).

{tabla_md({"Registros diarios evaluados": a["registros"], "Marcados por Z robusto": a["marcados_z_robusto"],
           "Marcados por IQR": a["marcados_iqr"], "Marcados por ambos": a["marcados_ambos"],
           "Persistentes (cambio de nivel, no se corrigen)": a["persistentes_no_corregidos"],
           "Aislados (ruido, corregidos)": f"{a['marcados_ambos_corregidos']} ({a['pct_corregidos']} %)"})}

Ejemplos de valores corregidos:

| Fecha | Mercado | Calibre | Precio reportado | Tendencia local | Z robusto |
|---|---|---|---|---|---|
{ejemplos}

## 5. Reducción de datos

- **Agregación:** de {r["registros_diarios"]} registros diarios a {r["registros_semanales"]} registros semanales (factor {r["factor_reduccion"]}×). La semana es el horizonte que necesita el cliente.
- **Selección de variables:** se eliminan las constantes {r["variables_eliminadas_constantes"]} y las técnicas {r["variables_eliminadas_tecnicas"]} (se conservan en Plata para trazabilidad).
- **Selección de series:** {r["series_validas"]} series con al menos {MIN_SEMANAS_SERIE} semanas; descartadas por cortas: {r["series_descartadas"] or "ninguna"}.

## 6. Integración de fuentes heterogéneas

| Conflicto | SNIIM | Open-Meteo | Banxico | Resolución |
|---|---|---|---|---|
| Formato de fecha | `dd/mm/aaaa` (texto) | `aaaa-mm-dd` | `dd/mm/aaaa` | Conversión explícita a `datetime` con formato fijo (Plata) |
| Tipo de los valores | Texto (`"20.00"`) | Número | Texto, con `"N/E"` | Conversión a número; lo no convertible queda vacío y lo atrapa la puerta de calidad |
| Calendario | Días hábiles | Todos los días | Días hábiles bancarios | Agregación a **semana (lunes a domingo)**; LOCF diario para el tipo de cambio |
| Granularidad | Mercado × calibre × presentación | Un punto (Tecomán) | Nacional | Clima y tipo de cambio se replican para todos los mercados de la semana |
| Unidades | $/kg calculado | mm, °C | MXN/USD | Se documentan en el nombre de la columna (`_mm`, `_kg`) |
| Llave | (fecha, mercado, calibre) | fecha | fecha | Llave común: `semana` |

{tabla_md({"Filas integradas": rep["integracion"]["filas"], "Semanas sin clima": rep["integracion"]["semanas_sin_clima"],
           "Semanas sin tipo de cambio": rep["integracion"]["semanas_sin_tipo_cambio"]})}

Las semanas sin clima corresponden a la semana más reciente: Open-Meteo publica el reanálisis con ~5 días de retraso,
así que esos valores se completan solos en la siguiente ejecución automática.

## 7. Discretización y jerarquías conceptuales

| Jerarquía | Niveles |
|---|---|
| Tiempo | semana → mes → trimestre → año; y **temporada** del ciclo del limón (baja oferta ene-abr, alta oferta may-sep, transición oct-dic) |
| Geografía | mercado → estado → **región** {rep["discretizacion"]["regiones"]} |
| Producto | calibre (#3, #4, #5, S/C) → **tamaño** (Mediano, Grande, Sin clasificar) |

Discretización por terciles:
- `lluvia_30d_nivel`: Baja / Media / Alta, cortes en {rep["discretizacion"]["lluvia_30d_cortes_mm"]} mm.
- `precio_nivel`: Bajo / Medio / Alto, cortes en {rep["discretizacion"]["precio_cortes_kg"]} $/kg.

## 8. Normalización y estandarización

Para cada variable continua se agregan dos columnas: `_minmax` = (x − min)/(max − min) en [0, 1] y `_z` = (x − media)/desv.

| Variable | Mín | Máx | Media | Desv. estándar |
|---|---|---|---|---|
""" + "\n".join(f"| {k} | {v['min']} | {v['max']} | {v['media']} | {v['desv_std']} |" for k, v in rep["normalizacion"].items()) + """

Los parámetros se guardan en `data/gold/parametros_normalizacion.json`. **Nota para el modelado (E1/E3):** al entrenar un modelo,
los parámetros deben recalcularse solo con el periodo de entrenamiento para no filtrar información del futuro.

## 9. Salidas en la capa Oro

| Archivo | Contenido |
|---|---|
| `data/gold/sniim_diario_limpio.csv` | Precio diario consolidado con banderas de atípico y valor original |
| `data/gold/limon_semanal.csv` | Tabla analítica: mercado × calibre × semana + clima + tipo de cambio + jerarquías + normalización |
| `data/gold/limon_semanal_nacional.csv` | Variable objetivo para el pronóstico: mediana semanal por calibre + covariables |
| `data/gold/parametros_normalizacion.json` | Parámetros Min-Max y Z-score |
"""
    destino = RAIZ / "docs" / "E1"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "reporte_limpieza.md").write_text(texto, encoding="utf-8")


# ----------------------------------------------------------------------------- principal
def main():
    plata = ruta("silver")
    s = pd.read_csv(plata / "sniim.csv", parse_dates=["fecha"])
    o = pd.read_csv(plata / "open_meteo.csv", parse_dates=["fecha"])
    b = pd.read_csv(plata / "banxico.csv", parse_dates=["fecha"])
    rep = {"fecha": datetime.now().strftime("%d/%m/%Y %H:%M")}

    d = consolidar_sniim(s, rep)
    diagnosticar_faltantes(d, rep)
    d = tratar_atipicos(d, rep)
    w = semanal_sniim(d, rep)
    t = integrar(w, semanal_clima(o), semanal_dolar(b, rep), rep)
    t = discretizar(t, rep)
    t, params = normalizar(t, rep)
    nacional = serie_nacional(t)

    oro = ruta("gold")
    d.to_csv(oro / "sniim_diario_limpio.csv", index=False, encoding="utf-8-sig")
    t.to_csv(oro / "limon_semanal.csv", index=False, encoding="utf-8-sig")
    nacional.to_csv(oro / "limon_semanal_nacional.csv", index=False, encoding="utf-8-sig")
    (oro / "parametros_normalizacion.json").write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")
    (ruta("logs") / "gold_resumen.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    escribir_reporte(rep)
    logger.info(f"Oro: {len(d)} diarios, {len(t)} semanales, {nacional['producto'].nunique()} series nacionales. "
                f"Atípicos corregidos: {rep['atipicos']['marcados_ambos_corregidos']}. "
                f"Imputadas: {rep['imputacion']['imputadas_interpolacion']}. Reporte: docs/E1/reporte_limpieza.md")
    return rep


if __name__ == "__main__":
    main()
