"""Pruebas de la capa Oro: limpieza estadística, imputación, discretización y normalización."""
import numpy as np
import pandas as pd

from src.transform.gold import (consolidar_sniim, normalizar, semanal_dolar, semanal_sniim, temporada,
                                tendencia_observacion, tratar_atipicos)


def registro(fecha, precio, presentacion="Kilogramo", destino="Jalisco: Mercado de Abasto de Guadalajara",
             producto="Limón c/semilla # 5", obs=None):
    return {"fecha": pd.Timestamp(fecha), "producto": producto, "destino": destino, "presentacion": presentacion,
            "precio_min": precio - 1, "precio_max": precio + 1, "precio_frec": precio,
            "observaciones": obs, "estado_destino": destino.split(":")[0]}


def test_tendencia_observacion_corrige_texto_libre():
    assert tendencia_observacion("A LA ALAZA") == "Alza"
    assert tendencia_observacion("a la alza") == "Alza"
    assert tendencia_observacion("A LA BAJA POR NUEVOS INGRESOS") == "Baja"
    assert tendencia_observacion("CAJA DE MAADERA") == "Otra"
    assert tendencia_observacion(None) == "Sin observación"


def test_temporada_del_limon():
    assert temporada(2) == "Baja oferta (ene-abr)"
    assert temporada(7) == "Alta oferta (may-sep)"
    assert temporada(11) == "Transición (oct-dic)"


def test_varias_presentaciones_mismo_dia_se_consolidan_con_mediana():
    s = pd.DataFrame([registro("2026-10-01", 20, "Caja de 20 kg."), registro("2026-10-01", 22, "Arpilla de 15 kg."),
                      registro("2026-10-01", 40, "Kilogramo")])
    rep = {}
    d = consolidar_sniim(s, rep)
    assert len(d) == 1
    assert d.iloc[0]["precio_frec"] == 22  # mediana: robusta a la presentación extrema (40)
    assert d.iloc[0]["n_presentaciones"] == 3
    assert rep["conflictos"]["llaves_con_varias_presentaciones"] == 1


def serie_diaria(precios, inicio="2026-01-05"):
    fechas = pd.bdate_range(inicio, periods=len(precios))
    s = pd.DataFrame([registro(f, p) for f, p in zip(fechas, precios)])
    return consolidar_sniim(s, {})


def test_atipico_aislado_se_corrige_y_cambio_de_nivel_no():
    # Otra serie con movimientos normales da escala a la MAD/IQR (residuos distintos de 0)
    rng = np.random.default_rng(0)
    normal = serie_diaria(list(20 + rng.normal(0, 1, 60).round(1)))
    normal["destino"] = "Sonora: Central de Abasto de Cd. Obregón"
    precios = [20.0] * 30
    precios[10] = 40.0                     # pico aislado de 1 día → ruido
    precios += [20.0] * 10 + [35.0] * 8 + [20.0] * 10  # 8 días seguidos en 35 → cambio de nivel real
    d = tratar_atipicos(pd.concat([serie_diaria(precios), normal], ignore_index=True), {})
    jal = d[d["destino"].str.startswith("Jalisco")].reset_index(drop=True)
    assert bool(jal.loc[10, "atipico"]) is True
    assert jal.loc[10, "precio_frec_limpio"] == 20.0          # corregido a la tendencia local
    assert jal.loc[10, "precio_frec_original"] == 40.0         # el original se conserva
    assert not jal.loc[jal["precio_frec"] == 35.0, "atipico"].any()


def test_imputa_huecos_cortos_y_no_los_largos():
    semanas = pd.date_range("2025-01-06", periods=40, freq="W-MON")
    filas = []
    for i, s in enumerate(semanas):
        if i in (5, 6) or 15 <= i <= 19:  # hueco de 2 semanas y hueco de 5 semanas
            continue
        filas.append({"fecha": s, "destino": "Jalisco: Mercado de Abasto de Guadalajara", "producto": "Limón c/semilla # 5",
                      "precio_frec_limpio": 20.0 + i, "precio_min": 19.0, "precio_max": 25.0 + i,
                      "atipico": False, "estado": "Jalisco", "calibre": "#5"})
    rep = {}
    w = semanal_sniim(pd.DataFrame(filas), rep)
    assert w.loc[[5, 6], "imputado"].all()                     # hueco corto: interpolado
    assert w.loc[5, "precio"] == 25.0
    assert w.loc[15:19, "precio"].isna().all()                 # hueco largo: se deja vacío (posible MNAR)
    assert rep["imputacion"]["imputadas_interpolacion"] == 2


def test_tipo_de_cambio_locf_en_fin_de_semana():
    b = pd.DataFrame({"fecha": pd.to_datetime(["2026-11-06", "2026-11-09"]), "tipo_cambio": [18.0, 18.6]})
    rep = {"imputacion": {}}
    w = semanal_dolar(b, rep)
    assert rep["imputacion"]["tipo_cambio_dias_locf"] == 2      # sábado y domingo
    assert w.iloc[0]["tipo_cambio"] == 18.0                     # semana del 2 al 8 usa el viernes para el fin de semana


def test_normalizacion_minmax_y_z():
    t = pd.DataFrame({c: [1.0, 2.0, 3.0, 4.0, 5.0] for c in
                      ["precio", "lluvia_30d_mm", "lluvia_semana_mm", "temp_media", "tipo_cambio"]})
    t, params = normalizar(t, {})
    assert t["precio_minmax"].min() == 0 and t["precio_minmax"].max() == 1
    assert abs(t["precio_z"].mean()) < 1e-12 and abs(t["precio_z"].std() - 1) < 1e-12
    assert params["precio"]["media"] == 3.0
