"""Ingesta de Banxico SIE (API REST): tipo de cambio FIX USD/MXN (serie SF43718) hacia la capa Bronce.

Uso:
    python -m src.ingest.banxico                         # desde fecha_inicio_historico hasta hoy
    python -m src.ingest.banxico --inicio 2025-01-01 --fin 2025-01-31
"""
import argparse
import json
import os
from datetime import date

from dotenv import load_dotenv

from src.utils import RAIZ, cargar_config, guardar_bronce, obtener_logger, peticion_con_reintentos

logger = obtener_logger("banxico")


def obtener_token(nombre_variable: str) -> str:
    """Lee el token desde el archivo .env (nunca escrito en el código)."""
    load_dotenv(RAIZ / ".env")
    token = os.getenv(nombre_variable, "").strip()
    if not token or token == "pega_aqui_tu_token":
        raise RuntimeError(
            f"No encontré el token en .env. Revisa que exista la línea {nombre_variable}=tu_token"
        )
    return token


def extraer(inicio: date, fin: date):
    """Descarga la serie del periodo indicado y la guarda cruda en data/bronze/banxico/."""
    cfg = cargar_config()["fuentes"]["banxico"]
    token = obtener_token(cfg["token_env"])
    url = cfg["url"].format(serie=cfg["serie"], inicio=inicio.isoformat(), fin=fin.isoformat())

    logger.info(f"Consultando serie {cfg['serie']} del {inicio} al {fin}")
    resp = peticion_con_reintentos(url, headers={"Bmx-Token": token, "Accept": "application/json"}, logger=logger)

    # Validación mínima de estructura antes de guardar (la limpieza real se hace en Plata)
    cuerpo = resp.json()
    try:
        datos = cuerpo["bmx"]["series"][0].get("datos", [])
    except (KeyError, IndexError, TypeError):
        raise ValueError(f"Respuesta inesperada de Banxico: {json.dumps(cuerpo)[:300]}")

    archivo = guardar_bronce(
        fuente="banxico",
        contenido=resp.text,
        extension="json",
        metadatos={
            "url": url,  # la URL no contiene el token (va en la cabecera)
            "serie": cfg["serie"],
            "periodo_inicio": inicio.isoformat(),
            "periodo_fin": fin.isoformat(),
            "registros": len(datos),
            "status_http": resp.status_code,
        },
    )
    logger.info(f"Guardados {len(datos)} registros en {archivo.relative_to(RAIZ)}")
    return archivo


def main():
    cfg = cargar_config()
    parser = argparse.ArgumentParser(description="Ingesta Banxico SIE → Bronce")
    parser.add_argument("--inicio", default=cfg["proyecto"]["fecha_inicio_historico"], help="AAAA-MM-DD")
    parser.add_argument("--fin", default=date.today().isoformat(), help="AAAA-MM-DD")
    args = parser.parse_args()
    extraer(date.fromisoformat(args.inicio), date.fromisoformat(args.fin))


if __name__ == "__main__":
    main()