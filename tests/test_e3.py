"""Pruebas de la E3: las optimizaciones NO cambian resultados, tolerancia a Bronce dañado y publicación del dataset."""
import hashlib
import json
import shutil

import numpy as np
import pandas as pd
import pytest

import src.publicacion.dataset as pub
import src.transform.silver as silver
import src.utils as utils
from src.transform import gold


@pytest.fixture
def capas_temporales(tmp_path, monkeypatch):
    def ruta_tmp(clave):
        p = tmp_path / clave
        p.mkdir(parents=True, exist_ok=True)
        return p
    for modulo in (utils, silver, pub):
        monkeypatch.setattr(modulo, "ruta", ruta_tmp)
    monkeypatch.setattr(silver, "RAIZ", tmp_path)
    monkeypatch.setattr(pub, "RAIZ", tmp_path)
    silver.ILEGIBLES.clear()
    return tmp_path


def copiar_bronce_sniim(destino, n=4):
    origen = utils.RAIZ / "data" / "bronze" / "sniim"
    metas = sorted(origen.glob("*.meta.json"))[:n]
    if not metas:
        pytest.skip("No hay Bronce del SNIIM en el repositorio")
    (destino / "bronze" / "sniim").mkdir(parents=True, exist_ok=True)
    for m in metas:
        shutil.copy(m, destino / "bronze" / "sniim" / m.name)
        crudo = json.loads(m.read_text(encoding="utf-8"))["archivo"]
        shutil.copy(origen / crudo, destino / "bronze" / "sniim" / crudo)
    return metas


# ----------------------------------------------------------------------------- O1: caché del SNIIM
def test_cache_sniim_da_exactamente_lo_mismo_que_leer_todo(capas_temporales):
    copiar_bronce_sniim(capas_temporales)
    sin_cache = silver.leer_sniim(usar_cache=False)
    primera = silver.leer_sniim()            # interpreta los HTML y llena la caché
    segunda = silver.leer_sniim()            # ya no interpreta nada: todo sale de la caché
    assert (capas_temporales / "data" / "cache" / "sniim_renglones.json").exists()
    pd.testing.assert_frame_equal(sin_cache, primera)
    pd.testing.assert_frame_equal(sin_cache, segunda)


def test_cache_solo_interpreta_archivos_nuevos(capas_temporales, monkeypatch):
    copiar_bronce_sniim(capas_temporales, n=2)
    silver.leer_sniim()
    llamadas = []
    original = silver.leer_tabla
    monkeypatch.setattr(silver, "leer_tabla", lambda html: llamadas.append(1) or original(html))
    silver.leer_sniim()
    assert llamadas == []                     # nada nuevo: cero HTML interpretados
    copiar_bronce_sniim(capas_temporales, n=3)
    silver.leer_sniim()
    assert len(llamadas) == 1                 # solo el archivo nuevo


# ----------------------------------------------------------------------------- O4: Bronce dañado
def test_bronce_danado_se_aisla_y_no_detiene_la_lectura(capas_temporales):
    carpeta = capas_temporales / "bronze" / "banxico"
    carpeta.mkdir(parents=True)
    bueno = {"bmx": {"series": [{"datos": [{"fecha": "02/01/2026", "dato": "17.50"}]}]}}
    (carpeta / "b1.json").write_text(json.dumps(bueno), encoding="utf-8")
    (carpeta / "b1.meta.json").write_text(json.dumps({"archivo": "b1.json", "fecha_captura": "2026-01-02T00:00:00"}))
    (carpeta / "b2.json").write_text('{"bmx": {"series": [ {"dat', encoding="utf-8")            # JSON cortado
    (carpeta / "b2.meta.json").write_text(json.dumps({"archivo": "b2.json", "fecha_captura": "2026-01-03T00:00:00"}))
    (carpeta / "b3.meta.json").write_text('{"archivo": "b3.js')                                   # metadatos rotos
    df = silver.leer_banxico()
    assert len(df) == 1 and df["tipo_cambio"].iloc[0] == 17.5
    assert sorted(i["archivo"] for i in silver.ILEGIBLES) == ["b2.json", "b3.meta.json"]


# ----------------------------------------------------------------------------- O2: agregaciones vectorizadas
def test_unir_unicos_vectorizado_igual_al_original():
    rng = np.random.default_rng(7)
    valores = ["a.html", "b.html", "c.html;a.html", "", None, "d.html;;b.html"]
    df = pd.DataFrame({"k1": rng.integers(0, 30, 600), "k2": rng.choice(["x", "y"], 600),
                       "v": [valores[i] for i in rng.integers(0, len(valores), 600)]})
    esperado = df.groupby(["k1", "k2"])["v"].agg(gold.unir_unicos)
    obtenido = gold.unir_unicos_por_grupo(df, ["k1", "k2"], "v").reindex(esperado.index).fillna("")
    pd.testing.assert_series_equal(esperado, obtenido, check_names=False)


def test_moda_vectorizada_igual_al_original_con_empates():
    df = pd.DataFrame({"k": [1, 1, 1, 2, 2, 3, 3, 3, 3],
                       "t": ["Sube", "Baja", "Sube", "Baja", "Sube", "Estable", "Baja", "Estable", "Baja"]})
    esperado = df.groupby("k")["t"].agg(lambda x: x.mode().iat[0])
    obtenido = gold.moda_por_grupo(df, ["k"], "t").reindex(esperado.index)
    pd.testing.assert_series_equal(esperado, obtenido, check_names=False)   # empate → el menor ('Baja')


# ----------------------------------------------------------------------------- publicación del dataset
def oro_minimo(carpeta):
    oro = carpeta / "gold"
    oro.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"destino": ["M1", "M1", "M1"], "producto": ["L5"] * 3,
                  "semana": ["2026-11-09", "2026-11-16", "2026-11-23"], "precio": [20.0, 21.5, 22.0],
                  "precio_z": [0.1, 0.2, 0.3], "origen_valor": ["observado"] * 3}).to_csv(oro / "limon_semanal.csv", index=False)
    pd.DataFrame({"producto": ["L5"] * 2, "semana": ["2026-11-09", "2026-11-16"],
                  "precio_mediana": [20.0, 21.5]}).to_csv(oro / "limon_semanal_nacional.csv", index=False)


def test_publicar_crea_paquete_estandar_con_licencia_y_huellas(capas_temporales, monkeypatch):
    oro_minimo(capas_temporales)
    monkeypatch.setattr(pub, "cargar_config", lambda: {"publicacion": {"version": "9.9.9", "corte": "2026-11-22"}})
    paquete = pub.publicar()
    carpeta = capas_temporales / "dataset"
    assert paquete["licenses"][0]["name"] == "CC-BY-4.0" and (carpeta / "LICENSE.md").exists()
    semanal = next(r for r in paquete["resources"] if r["name"] == "limon_semanal")
    assert semanal["filas"] == 2                              # la semana del 23/11 queda fuera del corte
    assert "precio_z" not in {f["name"] for f in semanal["schema"]["fields"]}   # columnas técnicas no se publican
    for r in paquete["resources"]:
        assert r["hash"] == "sha256:" + hashlib.sha256((carpeta / r["path"]).read_bytes()).hexdigest()
        assert all(f["description"] for f in r["schema"]["fields"])
    assert (capas_temporales / "dist" / "limonlab_colima_dataset_v9.9.9.zip").exists()


def test_publicar_se_detiene_con_datos_personales_o_columnas_sin_descripcion():
    with pytest.raises(ValueError, match="datos personales"):
        pub.revisar({"limon_semanal": pd.DataFrame({"destino": ["M"], "producto": ["L"], "semana": [1],
                                                    "telefono": ["313"]})})
    with pytest.raises(ValueError, match="sin descripción"):
        pub.revisar({"limon_semanal": pd.DataFrame({"destino": ["M"], "producto": ["L"], "semana": [1],
                                                    "columna_misteriosa": [1]})})
