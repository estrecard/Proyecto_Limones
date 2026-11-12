"""Pruebas del lector del SNIIM (con un HTML real guardado en tests/fixtures)
y de las funciones de limpieza de la capa Plata. No requieren internet."""
from datetime import date
from pathlib import Path

import pandas as pd

from src.ingest.sniim import leer_tabla, meses
from src.transform.silver import consolidar_capturas, numero

FIXTURE = Path(__file__).parent / "fixtures" / "sniim_resultados_ejemplo.html"


def test_lector_sniim_con_pagina_real():
    tabla = leer_tabla(FIXTURE.read_text(encoding="utf-8"))
    assert tabla["encabezado"] == {"producto": "Limón c/semilla # 3", "calidad": "Primera", "origen": "Colima"}
    assert tabla["paginas"] == 1
    assert len(tabla["renglones"]) == 37
    primero = tabla["renglones"][0]
    assert primero["fecha"] == "07/10/2026"
    assert primero["destino"] == "Sonora: Central de Abasto de Cd. Obregón"
    assert (primero["precio_min"], primero["precio_max"], primero["precio_frec"]) == ("20.00", "22.50", "20.00")
    assert primero["seccion"] == "Frutas"


def test_lector_sniim_sin_resultados_no_truena():
    tabla = leer_tabla("<html><body><p>NO HAY REGISTROS</p></body></html>")
    assert tabla["renglones"] == []


def test_meses_divide_el_periodo():
    tramos = list(meses(date(2026, 9, 15), date(2026, 11, 12)))
    assert tramos == [(date(2026, 9, 15), date(2026, 9, 30)),
                      (date(2026, 10, 1), date(2026, 10, 31)),
                      (date(2026, 11, 1), date(2026, 11, 12))]


def test_numero_convierte_texto_y_deja_vacio_lo_invalido():
    resultado = numero(pd.Series(["20.50", "1,234.5", "N/E", ""]))
    assert resultado.iloc[0] == 20.5
    assert resultado.iloc[1] == 1234.5
    assert resultado.iloc[2:].isna().all()


def test_consolidar_capturas_conserva_la_mas_reciente():
    df = pd.DataFrame({
        "fecha_texto": ["02/01/2025", "02/01/2025", "03/01/2025"],
        "tipo_cambio": [20.0, 20.5, 20.6],
        "fecha_captura": ["2026-11-01T10:00:00", "2026-11-12T10:00:00", "2026-11-12T10:00:00"],
    })
    resultado, reemplazados = consolidar_capturas(df, ["fecha_texto"])
    assert reemplazados == 1
    assert sorted(resultado["tipo_cambio"]) == [20.5, 20.6]