"""Fuente especializada GEOESPACIAL (E2): servicios web del INEGI → capa Bronce.

Dos servicios oficiales y abiertos del INEGI:
  1. Catálogo Único de Claves Geoestadísticas (wscatgeo v2, sin token):
     latitud, longitud y población de la localidad de cada central de abasto y de Tecomán (origen del limón).
  2. API del DENUE (Directorio Estadístico Nacional de Unidades Económicas, con token gratuito):
     fruterías (comercio al por menor de frutas y verduras) y mayoristas de frutas y verduras
     en un radio de 5 km (máximo que permite la API) alrededor de cada ciudad.

Por qué INEGI y no OpenStreetMap: el robots.txt de overpass-api.de prohíbe /api/ (revisado el 21/11/2026,
el pipeline lo detectó solo y se detuvo). Regla del proyecto: si un sitio lo prohíbe, se busca otra fuente.

Ética y reglas de uso (ver docs/etica-datos.md):
  - Se revisa robots.txt antes de cada consulta; si lo prohíbe, NO se consulta.
  - User-Agent que identifica el proyecto, pausa entre consultas y reintentos con espera creciente.
  - CACHÉ: cada consulta se guarda en Bronce y no se repite (las ubicaciones casi no cambian).
    Para refrescar: --refrescar (máximo una vez al mes).
  - CERO DATOS PERSONALES: el DENUE trae nombre, razón social (a veces el nombre de una persona física),
    teléfono, correo, sitio web y domicilio. Se eliminan EN MEMORIA, antes de escribir Bronce:
    solo quedan id, categoría, tamaño (estrato) y coordenadas.
  - El token del DENUE vive en .env / secreto de GitHub; NUNCA se escribe en Bronce ni en los logs.

Uso:
    python -m src.ingest.inegi_geo               # descarga solo lo que no está en caché
    python -m src.ingest.inegi_geo --refrescar   # vuelve a consultar todo
"""
import argparse
import json
import os
import re
import time
import unicodedata
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from src.utils import RAIZ, cargar_config, guardar_bronce, obtener_logger, permitido_por_robots, ruta

logger = obtener_logger("inegi_geo")
FUENTE = "inegi_geo"
CATEGORIAS = {"por menor de frutas y verduras": "fruteria", "por mayor de frutas y verduras": "mayorista"}


def clave(texto: str) -> str:
    """'Ciudad Obregón' → 'ciudad_obregon' (para nombrar archivos y comparar nombres sin acentos)."""
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def minusculas(d: dict) -> dict:
    return {str(k).lower(): v for k, v in d.items()}


def lista_de_registros(cuerpo) -> list:
    """Los servicios devuelven una lista o un objeto con la lista dentro (ej. {'datos': [...]})."""
    if isinstance(cuerpo, list):
        return [x for x in cuerpo if isinstance(x, dict)]
    if isinstance(cuerpo, dict):
        for v in cuerpo.values():
            if isinstance(v, list) and all(isinstance(x, dict) for x in v):
                return v
    return []


def numero(valor):
    try:
        return float(str(valor).replace(",", ""))
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------- privacidad
def anonimizar(registros: list) -> list:
    """Deja SOLO lo necesario para el análisis espacial. Se ejecuta antes de guardar nada en disco."""
    limpios = []
    for r in map(minusculas, registros):
        actividad = str(r.get("clase_actividad", "")).lower()
        categoria = next((c for texto, c in CATEGORIAS.items() if texto in actividad), None)
        lat, lon = numero(r.get("latitud")), numero(r.get("longitud"))
        if categoria and lat is not None and lon is not None:
            limpios.append({"denue_id": str(r.get("id") or r.get("clee")), "categoria": categoria,
                            "estrato": r.get("estrato"), "lat": lat, "lon": lon})
    return limpios


def localidades_limpias(registros: list) -> list:
    """De cada localidad se guardan claves, nombre oficial, coordenadas y población (dato público agregado)."""
    campos = ["cvegeo", "cve_ent", "cve_mun", "cve_loc", "nomgeo", "ambito", "latitud", "longitud", "pob_total"]
    return [{c: r.get(c) for c in campos} for r in map(minusculas, registros)]


# ----------------------------------------------------------------------------- red
def ocultar(texto: str, token: str) -> str:
    return texto.replace(token, "<DENUE_TOKEN>") if token else texto


def consultar(url: str, cfg: dict, token: str = ""):
    """GET respetando robots.txt, con reintentos; el token nunca aparece en los mensajes."""
    if not permitido_por_robots(url, cfg["user_agent"]):
        raise PermissionError(f"robots.txt no permite consultar {ocultar(url, token)}: se debe buscar otra fuente")
    ultimo = None
    for intento in range(1, cfg["reintentos"] + 1):
        try:
            r = requests.get(url, headers={"User-Agent": cfg["user_agent"]}, timeout=60)
            r.raise_for_status()
            time.sleep(cfg["pausa_entre_peticiones_seg"])  # cortesía con el servidor
            return r.json()
        except (requests.RequestException, ValueError) as e:
            ultimo = RuntimeError(ocultar(str(e), token))
            logger.warning(f"Intento {intento}/{cfg['reintentos']} falló: {ultimo}")
            if intento < cfg["reintentos"]:
                time.sleep(cfg["pausa_entre_peticiones_seg"] * 2 ** intento)
    raise ultimo


def token_denue() -> str:
    load_dotenv(RAIZ / ".env")
    t = os.getenv("DENUE_TOKEN", "").strip()
    return "" if t.startswith("pega_aqui") else t


# ----------------------------------------------------------------------------- Bronce
def en_cache(tipo: str, nombre: str) -> bool:
    return any((ruta("bronze") / FUENTE).glob(f"{FUENTE}_{tipo}_{clave(nombre)}_*.meta.json"))


def guardar(tipo: str, nombre: str, registros: list, url_publica: str, extra: dict, cfg: dict):
    return guardar_bronce(
        fuente=FUENTE, contenido=json.dumps({"registros": registros}, ensure_ascii=False, indent=1),
        extension="json", etiqueta=f"{tipo}_{clave(nombre)}",
        metadatos={"url": url_publica, "tipo_consulta": tipo, "lugar": nombre, "registros": len(registros),
                   "robots_permitido": True, "licencia": cfg["licencia"], "anonimizado": tipo == "comercios",
                   **extra})


def lugares(cfg: dict) -> dict:
    """Ciudades únicas a ubicar: el origen (Tecomán) y las de los mercados → clave de entidad."""
    l = {cfg["origen"]["ciudad"]: cfg["origen"]["cve_ent"]}
    for m in cfg["mercados"].values():
        l[m["ciudad"]] = m["cve_ent"]
    return l


def elegir_localidad(registros: list, ciudad: str, cve_ent: str):
    """La localidad con más población de esa entidad cuyo nombre contiene el buscado."""
    cand = [r for r in registros if str(r.get("cve_ent")).zfill(2) == cve_ent
            and clave(ciudad) in clave(r.get("nomgeo")) and numero(r.get("latitud")) is not None]
    return max(cand, key=lambda r: numero(r.get("pob_total")) or 0) if cand else None


def extraer(refrescar: bool = False):
    cfg = cargar_config()["fuentes"][FUENTE]
    token = token_denue()
    if not token:
        logger.warning("No hay DENUE_TOKEN en .env: se ubican las ciudades, pero no se descargan comercios")
    for ciudad, cve_ent in lugares(cfg).items():
        # 1) Localidad (coordenadas y población) — Catálogo Único, sin token
        if refrescar or not en_cache("ciudad", ciudad):
            registros = []
            for texto in dict.fromkeys([ciudad, clave(ciudad).replace("_", " ")]):  # con acentos y sin acentos
                url = f"{cfg['url_localidades']}/{quote(texto)}"
                registros = localidades_limpias(lista_de_registros(consultar(url, cfg)))
                registros = [r for r in registros if str(r.get("cve_ent")).zfill(2) == cve_ent]
                if registros:
                    break
            if not elegir_localidad(registros, ciudad, cve_ent):
                logger.warning(f"INEGI no encontró la localidad '{ciudad}' en la entidad {cve_ent}")
            guardar("ciudad", ciudad, registros, url, {"cve_ent": cve_ent}, cfg)
            logger.info(f"Localidad {ciudad}: {len(registros)} coincidencia(s) en la entidad {cve_ent}")
        # 2) Comercios alrededor — DENUE, con token
        if token and (refrescar or not en_cache("comercios", ciudad)):
            punto = ubicacion_en_bronce(ciudad)
            if punto is None:
                continue
            ruta_api = f"{cfg['condicion_denue']}/{punto['lat']},{punto['lon']}/{cfg['radio_comercios_m']}"
            cuerpo = consultar(f"{cfg['url_denue']}/{ruta_api}/{token}", cfg, token)
            registros = anonimizar(lista_de_registros(cuerpo))
            guardar("comercios", ciudad, registros, f"{cfg['url_denue']}/{ruta_api}/<DENUE_TOKEN>",
                    {"radio_m": cfg["radio_comercios_m"], "centro": punto}, cfg)
            logger.info(f"Comercios de frutas y verduras cerca de {ciudad}: {len(registros)}")
    logger.info("INEGI listo (lo que ya estaba en caché no se volvió a consultar)")


def ubicacion_en_bronce(ciudad: str):
    """Coordenadas de la ciudad según la captura más reciente en Bronce."""
    metas = sorted((ruta("bronze") / FUENTE).glob(f"{FUENTE}_ciudad_{clave(ciudad)}_*.meta.json"))
    if not metas:
        return None
    meta = json.loads(metas[-1].read_text(encoding="utf-8"))
    cfg_ent = meta.get("cve_ent", "")
    registros = json.loads((metas[-1].parent / meta["archivo"]).read_text(encoding="utf-8"))["registros"]
    mejor = elegir_localidad(registros, ciudad, cfg_ent) if cfg_ent else None
    if mejor is None:
        return None
    return {"lat": numero(mejor["latitud"]), "lon": numero(mejor["longitud"]), "cvegeo": mejor.get("cvegeo"),
            "nomgeo": mejor.get("nomgeo"), "pob_total": numero(mejor.get("pob_total")),
            "archivo": meta["archivo"], "fecha_captura": meta["fecha_captura"]}


def main():
    parser = argparse.ArgumentParser(description="Ingesta INEGI (Catálogo Único + DENUE) → Bronce")
    parser.add_argument("--refrescar", action="store_true", help="ignora la caché y vuelve a consultar")
    extraer(parser.parse_args().refrescar)


if __name__ == "__main__":
    main()
