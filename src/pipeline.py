"""Orquestador de LimónLab Colima: Ingesta (Bronce) → Puertas de calidad (Plata / Cuarentena).

Modos:
    python -m src.pipeline                      # incremental: solo lo reciente (para la ejecución diaria)
    python -m src.pipeline --historico          # todo desde fecha_inicio_historico (tarda ~15 min por el SNIIM)
    python -m src.pipeline --solo-plata         # no descarga nada; solo reconstruye Plata desde Bronce
    python -m src.pipeline --fuentes banxico open_meteo   # solo algunas fuentes

Si una fuente falla, el pipeline continúa con las demás y al final termina con código de error 1,
para que GitHub Actions marque la ejecución en rojo.
"""
import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta

from src.ingest import banxico, open_meteo, sniim
from src.transform import silver
from src.utils import cargar_config, obtener_logger, ruta

logger = obtener_logger("pipeline")

FUENTES = {"sniim": sniim, "open_meteo": open_meteo, "banxico": banxico}

# Días hacia atrás que se vuelven a descargar en modo incremental
# (cubre correcciones tardías de las fuentes y días que hayan fallado antes)
VENTANA_INCREMENTAL = {"sniim": 35, "open_meteo": 40, "banxico": 35}


def periodo(fuente: str, historico: bool):
    hoy = date.today()
    fin = hoy - timedelta(days=open_meteo.RETRASO_DIAS) if fuente == "open_meteo" else hoy
    if historico:
        inicio = date.fromisoformat(cargar_config()["proyecto"]["fecha_inicio_historico"])
    else:
        inicio = fin - timedelta(days=VENTANA_INCREMENTAL[fuente])
    return inicio, fin


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pipeline LimónLab Colima")
    parser.add_argument("--historico", action="store_true", help="descarga todo el periodo histórico")
    parser.add_argument("--solo-plata", action="store_true", help="omite la ingesta; solo reconstruye Plata")
    parser.add_argument("--fuentes", nargs="+", choices=list(FUENTES), default=list(FUENTES))
    args = parser.parse_args(argv)

    inicio_ejecucion = time.time()
    bitacora = {"fecha_ejecucion": datetime.now().isoformat(timespec="seconds"),
                "modo": "solo-plata" if args.solo_plata else ("historico" if args.historico else "incremental"),
                "ingesta": {}, "errores": []}
    logger.info(f"===== Inicio del pipeline (modo {bitacora['modo']}) =====")

    # 1. Ingesta → Bronce
    if not args.solo_plata:
        for nombre in args.fuentes:
            ini, fin = periodo(nombre, args.historico)
            logger.info(f"--- Ingesta {nombre}: {ini} a {fin}")
            try:
                FUENTES[nombre].extraer(ini, fin)
                bitacora["ingesta"][nombre] = {"estado": "ok", "inicio": str(ini), "fin": str(fin)}
            except Exception as e:  # una fuente caída no detiene a las demás
                logger.error(f"Falló la ingesta de {nombre}: {e}")
                bitacora["ingesta"][nombre] = {"estado": "error", "detalle": str(e)}
                bitacora["errores"].append(f"ingesta {nombre}: {e}")

    # 2. Bronce → Plata (con puertas de calidad)
    logger.info("--- Capa Plata y puertas de calidad")
    try:
        reporte = silver.main()
        bitacora["plata"] = {f: {k: m.get(k) for k in ("registros_plata", "registros_cuarentena", "tasa_aceptacion_pct")}
                             for f, m in reporte["fuentes"].items()}
    except Exception as e:
        logger.error(f"Falló la capa Plata: {e}")
        bitacora["errores"].append(f"plata: {e}")

    # 3. Bitácora de la ejecución
    bitacora["duracion_seg"] = round(time.time() - inicio_ejecucion, 1)
    bitacora["estado"] = "error" if bitacora["errores"] else "ok"
    salida = ruta("logs") / "ejecuciones.jsonl"
    with open(salida, "a", encoding="utf-8") as f:
        f.write(json.dumps(bitacora, ensure_ascii=False) + "\n")

    logger.info(f"===== Fin: {bitacora['estado'].upper()} en {bitacora['duracion_seg']} s =====")
    return 1 if bitacora["errores"] else 0


if __name__ == "__main__":
    sys.exit(main())