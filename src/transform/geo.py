"""Capa geoespacial (E2): Bronce INEGI → puerta Pandera → Plata → GeoPandas → Oro + mapa.

1. Lee de Bronce las localidades (Catálogo Único) y los comercios de frutas y verduras (DENUE) del INEGI.
2. Puerta de calidad (Pandera): coordenadas dentro de México, categorías válidas, sin duplicados.
   Lo que falla va a data/quarantine/geo_*_cuarentena.csv con su motivo.
3. GeoPandas:
   - Reproyección de EPSG:4326 (grados) a EPSG:6372 (metros) para medir bien.
   - Distancia en línea recta de Tecomán (origen del limón) a cada mercado.
   - Buffer de 5 km alrededor de cada mercado y UNIÓN ESPACIAL (sjoin) con los comercios:
     cuántas fruterías y mayoristas de frutas y verduras hay en esa zona (indicador de demanda local).
4. Oro: data/gold/mercados_geo.csv y .geojson (con linaje: archivo de Bronce y fecha de captura).
5. Mapa interactivo: dashboard/mapa_mercados.html (Folium), con la fuente INEGI y la atribución del mapa base.

Uso:
    python -m src.transform.geo
"""
import json

import pandas as pd

try:
    import pandera.pandas as pa
except ImportError:
    import pandera as pa
from pandera.errors import SchemaErrors

from src.ingest.inegi_geo import FUENTE, clave, ubicacion_en_bronce
from src.utils import RAIZ, cargar_config, obtener_logger, ruta

logger = obtener_logger("geo")
LAT_MX, LON_MX = (14.0, 33.0), (-118.5, -86.5)   # caja que contiene a México


# ----------------------------------------------------------------------------- Bronce → tablas
def leer_comercios(cfg: dict) -> pd.DataFrame:
    filas = []
    for ciudad in {m["ciudad"] for m in cfg["mercados"].values()}:
        metas = sorted((ruta("bronze") / FUENTE).glob(f"{FUENTE}_comercios_{clave(ciudad)}_*.meta.json"))
        if not metas:
            continue
        meta = json.loads(metas[-1].read_text(encoding="utf-8"))
        for e in json.loads((metas[-1].parent / meta["archivo"]).read_text(encoding="utf-8"))["registros"]:
            filas.append({**e, "ciudad_consulta": ciudad, "archivo_origen": meta["archivo"],
                          "fecha_captura": meta["fecha_captura"]})
    return pd.DataFrame(filas)


def leer_lugares(cfg: dict) -> pd.DataFrame:
    filas = []
    destinos = {**{d: m for d, m in cfg["mercados"].items()},
                "ORIGEN: " + cfg["origen"]["nombre"]: cfg["origen"]}
    for destino, m in destinos.items():
        p = ubicacion_en_bronce(m["ciudad"])
        filas.append({"destino": destino, "ciudad": m["ciudad"], "cve_ent": m["cve_ent"],
                      "cvegeo": p["cvegeo"] if p else None, "localidad_inegi": p["nomgeo"] if p else None,
                      "poblacion": p["pob_total"] if p else None,
                      "tipo": "origen" if destino.startswith("ORIGEN") else "mercado",
                      "lat": p["lat"] if p else None, "lon": p["lon"] if p else None,
                      "archivo_bronce_ciudad": p["archivo"] if p else None,
                      "fecha_captura_ciudad": p["fecha_captura"] if p else None})
    return pd.DataFrame(filas)


# ----------------------------------------------------------------------------- puerta de calidad
def texto():
    return pa.Column(None, nullable=False, checks=pa.Check(lambda x: isinstance(x, str), element_wise=True,
                                                           name="GEO-00", error="GEO-00: se esperaba texto"))


def esquema_lugares():
    return pa.DataFrameSchema({
        "destino": texto(),
        "lat": pa.Column(float, nullable=False, coerce=True, checks=pa.Check(
            lambda s: s.between(*LAT_MX), name="GEO-01", error="GEO-01: latitud fuera de México")),
        "lon": pa.Column(float, nullable=False, coerce=True, checks=pa.Check(
            lambda s: s.between(*LON_MX), name="GEO-01", error="GEO-01: longitud fuera de México")),
        "archivo_bronce_ciudad": texto(),
    }, strict=False, name="geo_lugares")


def esquema_comercios():
    return pa.DataFrameSchema({
        "denue_id": texto(),
        "categoria": pa.Column(None, nullable=False, checks=pa.Check(
            lambda s: s.isin(["fruteria", "mayorista"]), name="GEO-02", error="GEO-02: categoría no válida")),
        "lat": pa.Column(float, nullable=False, coerce=True, checks=pa.Check(
            lambda s: s.between(*LAT_MX), name="GEO-01", error="GEO-01: latitud fuera de México")),
        "lon": pa.Column(float, nullable=False, coerce=True, checks=pa.Check(
            lambda s: s.between(*LON_MX), name="GEO-01", error="GEO-01: longitud fuera de México")),
        "archivo_origen": texto(),
    }, strict=False, name="geo_comercios")


def validar(df: pd.DataFrame, esquema, nombre: str, llave=None):
    """Valida con Pandera (lazy). Los inválidos y los duplicados van a cuarentena con su motivo."""
    df = df.reset_index(drop=True)
    motivos = {}
    try:
        esquema.validate(df, lazy=True)
    except SchemaErrors as err:
        for _, f in err.failure_cases.iterrows():
            if pd.notna(f["index"]):
                motivos.setdefault(f["index"], set()).add(str(f["check"]))
    if llave:  # un mismo comercio puede caer en el radio de dos ciudades cercanas (ej. Torreón y Gómez Palacio)
        dup = df.drop(index=list(motivos)).duplicated(subset=llave + ["ciudad_consulta"], keep="first")
        for i in dup[dup].index:
            motivos.setdefault(i, set()).add("GEO-03: duplicado en la misma consulta")
    malos = df.index.isin(list(motivos))
    cuarentena = df[malos].assign(regla_fallida=[" | ".join(sorted(motivos[i])) for i in df.index[malos]],
                                  fecha_rechazo=pd.Timestamp.now().isoformat(timespec="seconds"))
    cuarentena.to_csv(ruta("quarantine") / f"{nombre}_cuarentena.csv", index=False, encoding="utf-8-sig")
    return df[~malos].copy(), len(cuarentena)


# ----------------------------------------------------------------------------- GeoPandas
def construir():
    import geopandas as gpd  # librería compilada: se importa aquí para que el resto del pipeline no dependa de ella

    cfg = cargar_config()["fuentes"][FUENTE]
    lugares, rech_l = validar(leer_lugares(cfg), esquema_lugares(), "geo_lugares")
    crudos = leer_comercios(cfg)
    if crudos.empty:  # sin token del DENUE todavía: se calculan distancias, los conteos quedan vacíos
        logger.warning("No hay comercios del DENUE en Bronce: los conteos de comercios quedan vacíos")
        crudos = pd.DataFrame(columns=["denue_id", "categoria", "estrato", "lat", "lon", "ciudad_consulta",
                                       "archivo_origen", "fecha_captura"])
        comercios, rech_c = crudos, 0
    else:
        comercios, rech_c = validar(crudos, esquema_comercios(), "geo_comercios", llave=["denue_id"])
    lugares.to_csv(ruta("silver") / "geo_lugares.csv", index=False, encoding="utf-8-sig")
    comercios.to_csv(ruta("silver") / "geo_comercios.csv", index=False, encoding="utf-8-sig")

    crs = cfg["crs_metrico"]
    g = gpd.GeoDataFrame(lugares, geometry=gpd.points_from_xy(lugares["lon"], lugares["lat"]), crs="EPSG:4326").to_crs(crs)
    if not (g["tipo"] == "origen").any():
        raise RuntimeError("No se encontró la ubicación de Tecomán en Bronce: ejecuta python -m src.ingest.inegi_geo")
    origen = g.loc[g["tipo"] == "origen", "geometry"].iloc[0]
    mercados = g[g["tipo"] == "mercado"].copy()
    mercados["distancia_tecoman_km"] = (mercados.geometry.distance(origen) / 1000).round(1)

    # Unión espacial: comercios dentro de un buffer de 5 km alrededor de cada mercado
    zonas = mercados[["destino", "geometry"]].copy()
    zonas["geometry"] = zonas.geometry.buffer(cfg["radio_comercios_m"])
    unicos = comercios.drop_duplicates(["denue_id"])  # un comercio cuenta una vez aunque lo traigan 2 consultas
    puntos = gpd.GeoDataFrame(unicos, geometry=gpd.points_from_xy(unicos["lon"].astype(float),
                                                                 unicos["lat"].astype(float)),
                              crs="EPSG:4326").to_crs(crs)
    union = gpd.sjoin(puntos, zonas, how="inner", predicate="within")
    conteo = union.groupby(["destino", "categoria"]).size().unstack(fill_value=0)
    consultadas = set(comercios["ciudad_consulta"])  # ciudades con captura del DENUE (las demás quedan vacías)
    for c in ["fruteria", "mayorista"]:
        n = mercados["destino"].map(conteo[c] if c in conteo else {}).fillna(0)
        mercados[f"{c}s_5km"] = n.where(mercados["ciudad"].isin(consultadas))  # NaN = sin captura
    mercados["comercios_5km"] = mercados["fruterias_5km"] + mercados["mayoristas_5km"]

    # Linaje: de qué archivo de Bronce salió la ubicación y los comercios de cada mercado
    arch = comercios.groupby("ciudad_consulta")["archivo_origen"].first()
    mercados["archivo_bronce_comercios"] = mercados["ciudad"].map(arch)
    mercados["licencia_geo"] = cfg["licencia"]

    salida = mercados.to_crs("EPSG:4326")
    columnas = ["destino", "ciudad", "cve_ent", "cvegeo", "localidad_inegi", "poblacion", "lat", "lon",
                "distancia_tecoman_km", "fruterias_5km", "mayoristas_5km", "comercios_5km",
                "archivo_bronce_ciudad", "fecha_captura_ciudad",
                "archivo_bronce_comercios", "licencia_geo"]
    salida[columnas].to_csv(ruta("gold") / "mercados_geo.csv", index=False, encoding="utf-8-sig")
    (ruta("gold") / "mercados_geo.geojson").write_text(salida[columnas + ["geometry"]].to_json(), encoding="utf-8")

    resumen = {"mercados_ubicados": int(len(mercados)), "comercios_validos": int(len(comercios)),
               "rechazados_lugares": rech_l, "rechazados_comercios": rech_c,
               "distancia_km_min": float(mercados["distancia_tecoman_km"].min()),
               "distancia_km_max": float(mercados["distancia_tecoman_km"].max()), "crs_metrico": crs}
    (ruta("logs") / "geo_resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Geo: {resumen['mercados_ubicados']} mercados, {resumen['comercios_validos']} comercios DENUE, "
                f"distancias {resumen['distancia_km_min']}–{resumen['distancia_km_max']} km")
    return resumen


# ----------------------------------------------------------------------------- mapa
def mapa():
    """Mapa interactivo para el observatorio: mercados coloreados por precio del limón y su distancia a Tecomán."""
    import folium

    geo_csv = ruta("gold") / "mercados_geo.csv"
    if not geo_csv.exists():
        logger.warning("No hay mercados_geo.csv: ejecuta primero python -m src.transform.geo")
        return
    m = pd.read_csv(geo_csv)
    precios = None
    diario = ruta("gold") / "sniim_diario_limpio.csv"
    if diario.exists():
        d = pd.read_csv(diario, parse_dates=["fecha"])
        reciente = d[d["fecha"] >= d["fecha"].max() - pd.Timedelta(days=365)]
        precios = reciente.groupby("destino")["precio_frec_limpio"].median()
    m["precio_mediano_12m"] = m["destino"].map(precios) if precios is not None else None

    lug = pd.read_csv(ruta("silver") / "geo_lugares.csv")
    origen = lug[lug["tipo"] == "origen"].iloc[0]
    # El mapa base (dibujo de calles) es de OpenStreetMap y lo carga el navegador de quien ve el mapa:
    # el pipeline NO descarga nada de OSM. Los datos de los puntos son del INEGI y del SNIIM.
    atribucion = ('Mapa base &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> · '
                  'Datos: INEGI (Catálogo Único y DENUE) · Precios: SNIIM, Secretaría de Economía · LimónLab Colima')
    mapa = folium.Map(location=[23.5, -102.5], zoom_start=5, tiles="OpenStreetMap", attr=atribucion)
    folium.Marker([origen["lat"], origen["lon"]], tooltip="Tecomán, Colima (origen del limón)",
                  icon=folium.Icon(color="green", icon="leaf")).add_to(mapa)

    pmin, pmax = m["precio_mediano_12m"].min(), m["precio_mediano_12m"].max()
    for _, r in m.iterrows():
        p = r["precio_mediano_12m"]
        t = 0.5 if pd.isna(p) or pmax == pmin else (p - pmin) / (pmax - pmin)
        color = f"#{int(255 * t):02x}{int(160 * (1 - t)):02x}40"   # verde = barato, rojo = caro
        folium.PolyLine([[origen["lat"], origen["lon"]], [r["lat"], r["lon"]]], weight=1, color="#888",
                        opacity=0.5).add_to(mapa)
        folium.CircleMarker(
            [r["lat"], r["lon"]], radius=6 + (0 if pd.isna(r["comercios_5km"]) else min(r["comercios_5km"], 60)) / 6, color=color, fill=True,
            fill_opacity=0.8,
            popup=folium.Popup(f"<b>{r['destino']}</b><br>Distancia a Tecomán: {r['distancia_tecoman_km']} km<br>"
                               f"Precio mediano (12 meses): {'' if pd.isna(p) else f'{p:.2f} $/kg'}<br>"
                               f"Fruterías y mayoristas de frutas y verduras a 5 km: "
                               f"{'sin dato' if pd.isna(r['comercios_5km']) else int(r['comercios_5km'])}", max_width=320),
        ).add_to(mapa)
    salida = RAIZ / "dashboard" / "mapa_mercados.html"
    salida.parent.mkdir(exist_ok=True)
    mapa.save(str(salida))
    logger.info(f"Mapa: {salida.relative_to(RAIZ)}")


def main():
    construir()
    mapa()


if __name__ == "__main__":
    main()
