"""Linaje y trazabilidad (E2): cada registro de la capa Oro se puede rastrear hasta su archivo de Bronce
y su fecha de captura (ingesta).

Cadena de linaje del precio semanal:
    Oro limon_semanal (mercado, calibre, semana)
      └─ archivos_bronce  → Oro sniim_diario_limpio (fecha, mercado, calibre) → ids_plata
           └─ Plata sniim.csv (id_registro, archivo_origen, fecha_captura)
                └─ Bronce data/bronze/sniim/<archivo>.html + <archivo>.meta.json (URL consultada, fecha de captura)
Las variables de clima, tipo de cambio y geografía llevan su propio archivo de Bronce en la misma fila.

Uso:
    python -m src.quality.linaje                                     # valida todo el linaje y deja logs/linaje_resumen.json
    python -m src.quality.linaje --destino "Jalisco: Mercado de Abasto de Guadalajara" --calibre "#5" --semana 2026-10-05
"""
import argparse
import json
from datetime import datetime

import pandas as pd

from src.utils import obtener_logger, ruta

logger = obtener_logger("linaje")

# columna de linaje → (carpeta de Bronce, columna de valor que respalda)
LINAJES = {
    "archivos_bronce": ("sniim", "precio"),
    "archivo_bronce_clima": ("open_meteo", "temp_media"),
    "archivo_bronce_banxico": ("banxico", "tipo_cambio"),
    "archivo_bronce_geo": ("inegi_geo", "distancia_tecoman_km"),
    "archivo_bronce_comercios": ("inegi_geo", "comercios_5km"),
}


def archivos_existentes() -> set:
    return {p.name for p in ruta("bronze").rglob("*") if p.is_file() and not p.name.endswith(".meta.json")}


def validar(oro: pd.DataFrame = None) -> dict:
    """Revisa, columna por columna, que todo valor con dato tenga linaje y que sus archivos existan en Bronce."""
    if oro is None:
        oro = pd.read_csv(ruta("gold") / "limon_semanal.csv")
    existentes = archivos_existentes()
    resumen = {"fecha": datetime.now().isoformat(timespec="seconds"), "filas_oro": len(oro), "columnas": {}}
    for col, (_, valor) in LINAJES.items():
        if col not in oro or valor not in oro:
            continue
        # Un precio imputado no viene de Bronce: su "origen" es el método (interpolación), documentado aparte
        con_dato = oro[valor].notna()
        if col == "archivos_bronce" and "origen_valor" in oro:
            con_dato &= oro["origen_valor"].eq("observado")
        lista = oro.loc[con_dato, col].fillna("").astype(str)
        sin_linaje = int((lista == "").sum())
        faltantes = sorted({a for v in lista for a in v.split(";") if a and a not in existentes})
        n = int(con_dato.sum())
        resumen["columnas"][col] = {"valores_con_dato": n, "sin_linaje": sin_linaje,
                                    "archivos_no_encontrados": len(faltantes), "ejemplos_no_encontrados": faltantes[:5],
                                    "pct_trazable": round(100 * (n - sin_linaje) / n, 2) if n else None}
    if "origen_valor" in oro:
        resumen["origen_del_precio"] = oro["origen_valor"].value_counts().to_dict()
    total = sum(c["valores_con_dato"] for c in resumen["columnas"].values())
    malos = sum(c["sin_linaje"] + c["archivos_no_encontrados"] for c in resumen["columnas"].values())
    resumen["pct_trazable_global"] = round(100 * (total - malos) / total, 2) if total else None
    (ruta("logs") / "linaje_resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Linaje: {resumen['pct_trazable_global']} % de los valores de Oro trazables hasta Bronce")
    return resumen


def rastrear(destino: str, calibre: str, semana: str) -> dict:
    """Muestra la cadena completa de un registro de Oro hasta Bronce."""
    oro = pd.read_csv(ruta("gold") / "limon_semanal.csv", parse_dates=["semana"])
    fila = oro[(oro["destino"] == destino) & (oro["calibre"] == calibre) & (oro["semana"] == pd.Timestamp(semana))]
    if fila.empty:
        raise ValueError("No existe ese registro en Oro. Revisa destino, calibre (#3, #4, #5, S/C) y semana (lunes AAAA-MM-DD).")
    f = fila.iloc[0]
    cadena = {"oro": {"destino": destino, "calibre": calibre, "semana": semana, "precio": f["precio"],
                      "origen_valor": f.get("origen_valor")}}

    diario = pd.read_csv(ruta("gold") / "sniim_diario_limpio.csv", parse_dates=["fecha"])
    dias = diario[(diario["destino"] == destino) & (diario["calibre"] == calibre) &
                  (diario["fecha"] >= pd.Timestamp(semana)) & (diario["fecha"] < pd.Timestamp(semana) + pd.Timedelta(days=7))]
    cadena["oro_diario"] = dias[["fecha", "precio_frec_original", "precio_frec_limpio", "atipico", "ids_plata"]] \
        .assign(fecha=lambda x: x["fecha"].dt.date.astype(str)).to_dict("records")

    bronce = []
    for col, (carpeta, _) in LINAJES.items():
        for archivo in str(f.get(col, "") or "").split(";"):
            if not archivo or archivo == "nan":
                continue
            meta_path = ruta("bronze") / carpeta / archivo.rsplit(".", 1)[0]
            meta_path = meta_path.with_name(meta_path.name + ".meta.json")
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            bronce.append({"variable": col, "archivo": f"data/bronze/{carpeta}/{archivo}",
                           "existe": (ruta("bronze") / carpeta / archivo).exists(),
                           "fecha_captura": meta.get("fecha_captura"), "url": meta.get("url")})
    cadena["bronce"] = bronce
    return cadena


def main():
    p = argparse.ArgumentParser(description="Valida o rastrea el linaje Oro → Bronce")
    p.add_argument("--destino")
    p.add_argument("--calibre")
    p.add_argument("--semana")
    a = p.parse_args()
    if a.destino and a.calibre and a.semana:
        print(json.dumps(rastrear(a.destino, a.calibre, a.semana), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(validar(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
