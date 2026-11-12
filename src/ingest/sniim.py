"""Ingesta del SNIIM (web scraping): precios al mayoreo del limón de origen Colima hacia la capa Bronce.

Pide la página de resultados directamente por URL (sin llenar el formulario), mes por mes
y producto por producto. Guarda cada HTML crudo en data/bronze/sniim/ con su .meta.json.

Uso:
    python -m src.ingest.sniim --inicio 2026-10-01 --fin 2026-10-31     # prueba corta
    python -m src.ingest.sniim                                           # todo el histórico
"""
import argparse
import re
import time
from datetime import date, timedelta

from bs4 import BeautifulSoup

from src.utils import RAIZ, cargar_config, guardar_bronce, obtener_logger, peticion_con_reintentos

logger = obtener_logger("sniim")


# ----------------------------------------------------------------------------- lectura del HTML
def leer_tabla(html: str) -> dict:
    """Extrae del HTML de resultados el encabezado (producto, calidad, origen),
    la paginación y los renglones de precios. Se usa aquí para contar registros
    y después en la capa Plata para construir la tabla limpia."""
    soup = BeautifulSoup(html, "lxml")

    # Encabezado: Producto | Calidad | Origen (tabla tblDatosGenerales)
    encabezado = {"producto": None, "calidad": None, "origen": None}
    tabla_gral = soup.find("table", id="tblDatosGenerales")
    if tabla_gral:
        for tr in tabla_gral.find_all("tr"):
            celdas = [td.get_text(strip=True) for td in tr.find_all("td", class_="DatTAB2")]
            if len(celdas) == 3 and all(celdas):
                encabezado = dict(zip(["producto", "calidad", "origen"], celdas))
                break

    # Paginación: "Página  1 de  1"
    paginas = 1
    pag = soup.find(id="lblPaginacion")
    if pag:
        m = re.search(r"de\s+(\d+)", pag.get_text())
        if m:
            paginas = int(m.group(1))

    # Renglones de datos (tabla tblResultados, celdas con clase Datos2)
    columnas = ["fecha", "presentacion", "destino", "precio_min", "precio_max", "precio_frec", "observaciones"]
    renglones = []
    seccion = None
    tabla = soup.find("table", id="tblResultados")
    if tabla:
        for tr in tabla.find_all("tr"):
            sec = tr.find("td", class_="encabACT2")
            if sec:  # renglón separador, por ejemplo "Frutas"
                seccion = sec.get_text(strip=True)
                continue
            celdas = tr.find_all("td", class_="Datos2")
            if len(celdas) == len(columnas):
                fila = dict(zip(columnas, [td.get_text(strip=True) for td in celdas]))
                fila["seccion"] = seccion
                renglones.append({**encabezado, **fila})

    return {"encabezado": encabezado, "paginas": paginas, "renglones": renglones}


# ----------------------------------------------------------------------------- descarga
def meses(inicio: date, fin: date):
    """Divide el periodo en tramos mensuales (para no pedir tablas enormes)."""
    actual = inicio
    while actual <= fin:
        siguiente_mes = (actual.replace(day=1) + timedelta(days=32)).replace(day=1)
        tramo_fin = min(siguiente_mes - timedelta(days=1), fin)
        yield actual, tramo_fin
        actual = siguiente_mes


def descargar_tramo(cfg: dict, producto_id: int, producto: str, inicio: date, fin: date):
    """Pide un producto en un tramo de fechas y guarda el HTML crudo en Bronce."""
    params = {
        "fechaInicio": inicio.strftime("%d/%m/%Y"),
        "fechaFinal": fin.strftime("%d/%m/%Y"),
        "ProductoId": producto_id,
        "OrigenId": cfg["origen_id"],
        "Origen": cfg["origen"],
        "DestinoId": -1,
        "Destino": "Todos",
        "PreciosPorId": cfg["precios_por_id"],
        "RegistrosPorPagina": cfg["registros_por_pagina"],
    }
    resp = peticion_con_reintentos(
        cfg["url_resultados"],
        params=params,
        headers={"User-Agent": cfg["user_agent"]},
        reintentos=cfg["reintentos"],
        logger=logger,
    )
    if "charset" not in resp.headers.get("Content-Type", "").lower():
        resp.encoding = "utf-8"
    html = resp.text

    tabla = leer_tabla(html)
    n = len(tabla["renglones"])
    if tabla["paginas"] > 1:
        logger.warning(f"{producto} {inicio}: hay {tabla['paginas']} páginas; sube registros_por_pagina en settings.yaml")

    archivo = guardar_bronce(
        fuente="sniim",
        contenido=html,
        extension="html",
        etiqueta=f"{producto_id}_{inicio:%Y%m}",
        metadatos={
            "url": resp.url,
            "producto_id": producto_id,
            "producto": producto,
            "origen": cfg["origen"],
            "periodo_inicio": inicio.isoformat(),
            "periodo_fin": fin.isoformat(),
            "registros": n,
            "paginas": tabla["paginas"],
            "status_http": resp.status_code,
        },
    )
    logger.info(f"{producto:<38} {inicio} a {fin}: {n:>3} registros -> {archivo.name}")
    return n


def extraer(inicio: date, fin: date):
    cfg = cargar_config()["fuentes"]["sniim"]
    total = 0
    for producto_id, producto in cfg["productos"].items():
        for t_inicio, t_fin in meses(inicio, fin):
            total += descargar_tramo(cfg, producto_id, producto, t_inicio, t_fin)
            time.sleep(cfg["pausa_entre_peticiones_seg"])  # cortesía con el servidor
    logger.info(f"SNIIM terminado: {total} registros en total")
    return total


def main():
    cfg = cargar_config()
    parser = argparse.ArgumentParser(description="Ingesta SNIIM (scraping) → Bronce")
    parser.add_argument("--inicio", default=cfg["proyecto"]["fecha_inicio_historico"], help="AAAA-MM-DD")
    parser.add_argument("--fin", default=date.today().isoformat(), help="AAAA-MM-DD")
    args = parser.parse_args()
    extraer(date.fromisoformat(args.inicio), date.fromisoformat(args.fin))


if __name__ == "__main__":
    main()