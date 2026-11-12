"""Ingesta de Open-Meteo Historical Weather API: clima diario de Tecomán, Colima, hacia la capa Bronce.

No requiere token. Los datos de reanálisis (ERA5) tienen unos días de retraso,
por eso la fecha final por defecto es hoy menos 5 días.

Uso:
    python -m src.ingest.open_meteo                      # desde fecha_inicio_historico hasta hace 5 días
    python -m src.ingest.open_meteo --inicio 2025-01-01 --fin 2025-01-31
"""
import argparse
import json
from datetime import date, timedelta

from src.utils import RAIZ, cargar_config, guardar_bronce, obtener_logger, peticion_con_reintentos

logger = obtener_logger("open_meteo")
RETRASO_DIAS = 5


def extraer(inicio: date, fin: date):
    """Descarga el clima diario del periodo y lo guarda crudo en data/bronze/open_meteo/."""
    cfg_total = cargar_config()
    cfg = cfg_total["fuentes"]["open_meteo"]
    params = {
        "latitude": cfg["latitud"],
        "longitude": cfg["longitud"],
        "start_date": inicio.isoformat(),
        "end_date": fin.isoformat(),
        "daily": ",".join(cfg["variables_diarias"]),
        "timezone": cfg_total["proyecto"]["zona_horaria"],
    }

    logger.info(f"Consultando clima de {cfg['ubicacion']} del {inicio} al {fin}")
    resp = peticion_con_reintentos(cfg["url"], params=params, logger=logger)

    # Validación mínima de estructura antes de guardar
    cuerpo = resp.json()
    if "daily" not in cuerpo or "time" not in cuerpo["daily"]:
        raise ValueError(f"Respuesta inesperada de Open-Meteo: {json.dumps(cuerpo)[:300]}")
    dias = len(cuerpo["daily"]["time"])

    archivo = guardar_bronce(
        fuente="open_meteo",
        contenido=resp.text,
        extension="json",
        metadatos={
            "url": resp.url,
            "ubicacion": cfg["ubicacion"],
            "latitud": cfg["latitud"],
            "longitud": cfg["longitud"],
            "periodo_inicio": inicio.isoformat(),
            "periodo_fin": fin.isoformat(),
            "registros": dias,
            "status_http": resp.status_code,
        },
    )
    logger.info(f"Guardados {dias} días en {archivo.relative_to(RAIZ)}")
    return archivo


def main():
    cfg = cargar_config()
    parser = argparse.ArgumentParser(description="Ingesta Open-Meteo → Bronce")
    parser.add_argument("--inicio", default=cfg["proyecto"]["fecha_inicio_historico"], help="AAAA-MM-DD")
    parser.add_argument("--fin", default=(date.today() - timedelta(days=RETRASO_DIAS)).isoformat(), help="AAAA-MM-DD")
    args = parser.parse_args()
    extraer(date.fromisoformat(args.inicio), date.fromisoformat(args.fin))


if __name__ == "__main__":
    main()