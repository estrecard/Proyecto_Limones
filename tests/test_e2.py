"""Pruebas de la E2: fuente geoespacial (INEGI), privacidad, token, caché, robots.txt, GeoPandas y linaje."""
import json

import pandas as pd
import pytest

import src.ingest.inegi_geo as ig
import src.utils as utils
from src.quality import linaje

TOKEN = "abc123-token-secreto"


@pytest.fixture
def bronce_temporal(tmp_path, monkeypatch):
    """Redirige todas las capas a una carpeta temporal para no tocar los datos reales."""
    def ruta_tmp(clave):
        p = tmp_path / clave
        p.mkdir(parents=True, exist_ok=True)
        return p
    for modulo in (utils, ig, linaje):
        monkeypatch.setattr(modulo, "ruta", ruta_tmp)
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    return tmp_path


LOCALIDADES = {"datos": [
    {"cvegeo": "060090001", "cve_ent": "06", "cve_mun": "009", "cve_loc": "0001", "nomgeo": "Tecomán",
     "ambito": "U", "latitud": "18.9089", "longitud": "-103.8747", "pob_total": "90000"},
    {"cvegeo": "060090123", "cve_ent": "06", "cve_mun": "009", "cve_loc": "0123", "nomgeo": "Tecomán Viejo",
     "ambito": "R", "latitud": "18.95", "longitud": "-103.80", "pob_total": "40"},
    {"cvegeo": "060020001", "cve_ent": "06", "cve_mun": "002", "cve_loc": "0001", "nomgeo": "Colima",
     "ambito": "U", "latitud": "19.2433", "longitud": "-103.7250", "pob_total": "150000"},
    {"cvegeo": "140390001", "cve_ent": "14", "cve_mun": "039", "cve_loc": "0001", "nomgeo": "Colima (otro estado)",
     "ambito": "R", "latitud": "20.0", "longitud": "-103.0", "pob_total": "999999"},
]}
DENUE = [
    {"Id": "111", "Nombre": "FRUTERIA DOÑA MARY", "Razon_social": "MARIA PEREZ LOPEZ",
     "Clase_actividad": "Comercio al por menor de frutas y verduras frescas", "Estrato": "0 a 5 personas",
     "Calle": "MADERO", "Telefono": "3130000000", "Correo_e": "x@y.mx", "Sitio_internet": "ejemplo.mx",
     "Latitud": "18.91", "Longitud": "-103.88"},
    {"Id": "222", "Nombre": "BODEGA EL LIMON", "Razon_social": "LIMONES SA DE CV",
     "Clase_actividad": "Comercio al por mayor de frutas y verduras frescas", "Estrato": "11 a 30 personas",
     "Latitud": "18.92", "Longitud": "-103.86"},
    {"Id": "333", "Nombre": "JUGOS Y FRUTAS LA PALMA", "Clase_actividad": "Restaurantes con servicio de preparación de antojitos",
     "Latitud": "18.93", "Longitud": "-103.85"},  # dice "frutas" pero no es comercio de frutas y verduras
]


def test_anonimizar_quita_nombres_contacto_y_domicilio():
    limpios = ig.anonimizar(DENUE)
    assert [e["categoria"] for e in limpios] == ["fruteria", "mayorista"]
    for e in limpios:
        assert set(e) == {"denue_id", "categoria", "estrato", "lat", "lon"}
    texto = json.dumps(limpios, ensure_ascii=False)
    for dato in ["DOÑA MARY", "MARIA PEREZ", "3130000000", "x@y.mx", "ejemplo.mx", "MADERO", "LIMONES SA"]:
        assert dato not in texto
    assert limpios[0]["lat"] == 18.91


def test_elegir_localidad_mas_poblada_de_la_entidad():
    regs = ig.localidades_limpias(LOCALIDADES["datos"])
    assert ig.elegir_localidad(regs, "Tecomán", "06")["cvegeo"] == "060090001"
    assert ig.elegir_localidad(regs, "Colima", "06")["cvegeo"] == "060020001"   # ignora el homónimo de Jalisco
    assert ig.elegir_localidad(regs, "Colima", "26") is None


def test_extraer_respeta_robots_y_no_consulta(bronce_temporal, monkeypatch):
    monkeypatch.setattr(ig, "permitido_por_robots", lambda url, ua: False)
    llamadas = []
    monkeypatch.setattr(ig.requests, "get", lambda *a, **k: llamadas.append(1))
    with pytest.raises(PermissionError):
        ig.extraer()
    assert llamadas == []


def test_extraer_anonimiza_oculta_token_y_usa_cache(bronce_temporal, monkeypatch):
    cfg = utils.cargar_config()["fuentes"]["inegi_geo"]
    cfg = {**cfg, "mercados": {"Colima: Centros de distribución de Colima": {"ciudad": "Colima", "cve_ent": "06"}},
           "pausa_entre_peticiones_seg": 0}
    monkeypatch.setattr(ig, "cargar_config", lambda: {"fuentes": {"inegi_geo": cfg}})
    monkeypatch.setattr(ig, "permitido_por_robots", lambda url, ua: True)
    monkeypatch.setattr(ig, "token_denue", lambda: TOKEN)
    consultas = []

    class Resp:
        def __init__(self, cuerpo): self.cuerpo = cuerpo
        def raise_for_status(self): pass
        def json(self): return json.loads(json.dumps(self.cuerpo))

    def falso_get(url, **k):
        consultas.append(url)
        return Resp(DENUE if "denue" in url else LOCALIDADES)
    monkeypatch.setattr(ig.requests, "get", falso_get)

    ig.extraer()
    assert len(consultas) == 4  # 2 ciudades (Tecomán y Colima) × (localidad + comercios)
    assert any(TOKEN in u for u in consultas)          # el token sí se usa en la petición...
    carpeta = bronce_temporal / "bronze" / "inegi_geo"
    guardado = " ".join(p.read_text(encoding="utf-8") for p in carpeta.glob("*.json"))
    assert TOKEN not in guardado                       # ...pero nunca se escribe en Bronce
    assert "DOÑA MARY" not in guardado and "3130000000" not in guardado
    metas = [json.loads(p.read_text(encoding="utf-8")) for p in carpeta.glob("*.meta.json")]
    assert all(m["robots_permitido"] and "INEGI" in m["licencia"] for m in metas)
    assert ig.ubicacion_en_bronce("Colima")["cvegeo"] == "060020001"

    ig.extraer()                # segunda vez: todo está en caché
    assert len(consultas) == 4  # no se volvió a consultar al INEGI


def test_sin_token_ubica_ciudades_pero_no_pide_comercios(bronce_temporal, monkeypatch):
    cfg = {**utils.cargar_config()["fuentes"]["inegi_geo"], "mercados": {}, "pausa_entre_peticiones_seg": 0}
    monkeypatch.setattr(ig, "cargar_config", lambda: {"fuentes": {"inegi_geo": cfg}})
    monkeypatch.setattr(ig, "permitido_por_robots", lambda url, ua: True)
    monkeypatch.setattr(ig, "token_denue", lambda: "")
    consultas = []

    class Resp:
        def raise_for_status(self): pass
        def json(self): return LOCALIDADES
    monkeypatch.setattr(ig.requests, "get", lambda url, **k: consultas.append(url) or Resp())
    ig.extraer()
    assert len(consultas) == 1 and "denue" not in consultas[0]


def test_geopandas_distancia_y_union_espacial():
    gpd = pytest.importorskip("geopandas")
    puntos = pd.DataFrame({"nombre": ["Tecomán", "Guadalajara"], "lat": [18.9089, 20.6767], "lon": [-103.8747, -103.3475]})
    g = gpd.GeoDataFrame(puntos, geometry=gpd.points_from_xy(puntos["lon"], puntos["lat"]), crs="EPSG:4326").to_crs("EPSG:6372")
    km = g.geometry.iloc[1].distance(g.geometry.iloc[0]) / 1000
    assert 190 < km < 215  # Tecomán–Guadalajara en línea recta ≈ 200 km
    zona = g.iloc[[1]].copy()
    zona["geometry"] = zona.geometry.buffer(10000)
    comercios = pd.DataFrame({"lat": [20.68, 20.90], "lon": [-103.35, -103.35]})  # uno a ~0.5 km, otro a ~25 km
    pc = gpd.GeoDataFrame(comercios, geometry=gpd.points_from_xy(comercios["lon"], comercios["lat"]), crs="EPSG:4326").to_crs("EPSG:6372")
    assert len(gpd.sjoin(pc, zona, predicate="within")) == 1


def test_validar_linaje_detecta_registros_sin_origen(bronce_temporal):
    (bronce_temporal / "bronze" / "sniim").mkdir(parents=True, exist_ok=True)
    (bronce_temporal / "bronze" / "sniim" / "a.html").write_text("x")
    oro = pd.DataFrame({
        "precio": [20.0, 21.0, 22.0, None],
        "origen_valor": ["observado", "observado", "imputado", "sin_dato"],
        "archivos_bronce": ["a.html", "", "", ""],
    })
    r = linaje.validar(oro)
    c = r["columnas"]["archivos_bronce"]
    assert c["valores_con_dato"] == 2       # el imputado y el vacío no se exigen
    assert c["sin_linaje"] == 1             # un valor observado sin archivo → se detecta
    assert r["pct_trazable_global"] == 50.0
