"""Utilidades comunes del pipeline: configuración, rutas, bitácora, peticiones HTTP y guardado en Bronce."""
import json
import logging
import time
import urllib.robotparser
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

# Carpeta raíz del proyecto (Proyecto_Limones), sin importar desde dónde se ejecute
RAIZ = Path(__file__).resolve().parents[1]


def cargar_config() -> dict:
    """Lee config/settings.yaml y lo devuelve como diccionario."""
    with open(RAIZ / "config" / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ruta(clave: str) -> Path:
    """Devuelve la ruta absoluta de una capa (bronze, silver, gold, quarantine, logs) y la crea si no existe."""
    p = RAIZ / cargar_config()["rutas"][clave]
    p.mkdir(parents=True, exist_ok=True)
    return p


def obtener_logger(nombre: str) -> logging.Logger:
    """Bitácora que escribe en pantalla y en logs/pipeline.log."""
    logger = logging.getLogger(nombre)
    if logger.handlers:  # evita duplicar mensajes si se llama dos veces
        return logger
    logger.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    consola = logging.StreamHandler()
    consola.setFormatter(formato)
    archivo = logging.FileHandler(ruta("logs") / "pipeline.log", encoding="utf-8")
    archivo.setFormatter(formato)
    logger.addHandler(consola)
    logger.addHandler(archivo)
    return logger


def peticion_con_reintentos(url, params=None, headers=None, reintentos=3, pausa=2, timeout=60, logger=None):
    """GET con reintentos y espera creciente (2 s, 4 s, 8 s...). Lanza el último error si todos fallan."""
    ultimo_error = None
    for intento in range(1, reintentos + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            ultimo_error = e
            if logger:
                logger.warning(f"Intento {intento}/{reintentos} falló: {e}")
            if intento < reintentos:
                time.sleep(pausa * (2 ** (intento - 1)))
    raise ultimo_error


_ROBOTS = {}


def permitido_por_robots(url: str, user_agent: str) -> bool:
    """Lee (una vez por dominio) el robots.txt del sitio y dice si la ruta está permitida.
    Regla del proyecto: si el sitio lo prohíbe, NO se consulta y se busca otra fuente."""
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _ROBOTS:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": user_agent}, timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])  # sin robots.txt = todo permitido
        except requests.RequestException:
            rp.parse([])
        _ROBOTS[base] = rp
    return _ROBOTS[base].can_fetch(user_agent, url)


def post_con_reintentos(url, data=None, headers=None, reintentos=3, pausa=2, timeout=120, logger=None):
    """POST con reintentos y espera creciente; también espera si el servidor responde 429 (saturado)."""
    ultimo_error = None
    for intento in range(1, reintentos + 1):
        try:
            resp = requests.post(url, data=data, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            ultimo_error = e
            if logger:
                logger.warning(f"Intento {intento}/{reintentos} falló: {e}")
            if intento < reintentos:
                time.sleep(pausa * (2 ** intento))
    raise ultimo_error


def guardar_bronce(fuente: str, contenido: str, extension: str, metadatos: dict, etiqueta: str = "") -> Path:
    """Guarda la respuesta cruda SIN modificar en data/bronze/<fuente>/ y, junto a ella,
    un archivo .meta.json con la trazabilidad (fuente, URL, fecha de captura, parámetros).
    La etiqueta opcional (ej. producto y mes) evita que dos descargas del mismo segundo se pisen."""
    carpeta = ruta("bronze") / fuente
    carpeta.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{fuente}_{etiqueta}_{marca}" if etiqueta else f"{fuente}_{marca}"
    archivo = carpeta / f"{base}.{extension}"
    archivo.write_text(contenido, encoding="utf-8")

    meta = {
        "fuente": fuente,
        "archivo": archivo.name,
        "fecha_captura": datetime.now().isoformat(timespec="seconds"),
        **metadatos,
    }
    (carpeta / f"{base}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return archivo