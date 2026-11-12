"""Pruebas de las puertas de calidad: cada regla debe atrapar el error que le corresponde
y dejar pasar los registros correctos."""
import pandas as pd
import pytest

from src.quality.gates import aplicar_puertas, reglas_de

TRAZA = {"fuente": "prueba", "fecha_captura": "2026-11-12T00:00:00", "archivo_origen": "prueba.json"}


def sniim(**cambios):
    """Un registro SNIIM válido; los argumentos cambian los campos que se quieran romper."""
    base = {"fecha": pd.Timestamp("2026-10-01"), "producto": "Limón c/semilla # 5", "calidad": "Primera",
            "origen": "Colima", "presentacion": "Kilogramo", "destino": "Jalisco: Mercado de Abasto de Guadalajara",
            "precio_min": 18.0, "precio_max": 22.0, "precio_frec": 20.0, **TRAZA}
    base.update(cambios)
    return base


def clima(**cambios):
    base = {"fecha": pd.Timestamp("2025-01-01"), "precipitacion_mm": 0.0,
            "temp_min": 18.0, "temp_media": 24.0, "temp_max": 31.0, **TRAZA}
    base.update(cambios)
    return base


def dolar(**cambios):
    base = {"fecha": pd.Timestamp("2025-01-02"), "tipo_cambio": 20.5, **TRAZA}
    base.update(cambios)
    return base


def evaluar(fuente, registros):
    aceptados, cuarentena, _ = aplicar_puertas(pd.DataFrame(registros), reglas_de(fuente))
    return aceptados, cuarentena


# ----------------------------------------------------------------------------- registros válidos pasan
def test_registros_validos_pasan_todas_las_puertas():
    for fuente, registro in [("sniim", sniim()), ("open_meteo", clima()), ("banxico", dolar())]:
        aceptados, cuarentena = evaluar(fuente, [registro])
        assert len(aceptados) == 1 and len(cuarentena) == 0, fuente


# ----------------------------------------------------------------------------- cada regla atrapa su error
@pytest.mark.parametrize("fuente, registro, regla", [
    ("sniim", sniim(precio_frec=float("nan")), "CQ-01"),               # Completitud
    ("banxico", dolar(tipo_cambio=float("nan")), "CQ-01"),             # día 'N/E'
    ("sniim", sniim(fecha=pd.NaT), "CQ-02"),                           # fecha inválida
    ("open_meteo", clima(fecha=pd.Timestamp("2099-01-01")), "CQ-02"),  # fecha futura
    ("sniim", sniim(precio_min=280, precio_max=290, precio_frec=285), "CQ-03"),  # precio absurdo
    ("sniim", sniim(precio_min=0.5, precio_max=1, precio_frec=0.8), "CQ-03"),
    ("sniim", sniim(precio_min=25, precio_frec=20), "CQ-04"),          # mínimo > frecuente
    ("open_meteo", clima(precipitacion_mm=-3), "CQ-06"),              # lluvia negativa
    ("open_meteo", clima(temp_max=60), "CQ-06"),                       # temperatura imposible
    ("open_meteo", clima(temp_min=30, temp_max=20), "CQ-07"),          # mínima > máxima
    ("banxico", dolar(tipo_cambio=205.3), "CQ-08"),                    # tipo de cambio absurdo
    ("sniim", sniim(origen="Michoacán"), "CQ-11"),                     # fuera del alcance
    ("sniim", sniim(producto="Limón persa"), "CQ-11"),
    ("sniim", sniim(destino="Guadalajara"), "CQ-11"),                  # destino sin formato
    ("sniim", sniim(archivo_origen=None), "CQ-12"),                    # sin trazabilidad
])
def test_regla_bloqueante_manda_a_cuarentena(fuente, registro, regla):
    aceptados, cuarentena = evaluar(fuente, [registro])
    assert len(aceptados) == 0
    assert len(cuarentena) == 1
    assert regla in cuarentena.iloc[0]["regla_fallida"]
    assert cuarentena.iloc[0]["motivo"]  # siempre se explica el motivo


def test_cq05_duplicado_conserva_el_primero():
    aceptados, cuarentena = evaluar("banxico", [dolar(), dolar()])
    assert len(aceptados) == 1
    assert list(cuarentena["regla_fallida"]) == ["CQ-05"]


def test_cq05_no_cuenta_registros_ya_rechazados():
    # El primero es inválido (CQ-08): el segundo, válido, NO debe marcarse como duplicado
    aceptados, cuarentena = evaluar("banxico", [dolar(tipo_cambio=500), dolar()])
    assert len(aceptados) == 1
    assert list(cuarentena["regla_fallida"]) == ["CQ-08"]


def test_registro_con_varios_errores_lista_todas_las_reglas():
    _, cuarentena = evaluar("sniim", [sniim(origen="Michoacán", precio_min=300, precio_max=310, precio_frec=305)])
    reglas = cuarentena.iloc[0]["regla_fallida"].split(";")
    assert "CQ-03" in reglas and "CQ-11" in reglas


# ----------------------------------------------------------------------------- advertencias
def test_cq09_salto_de_precio_es_advertencia_no_rechazo():
    registros = [sniim(fecha=pd.Timestamp("2026-10-01"), precio_min=18, precio_frec=20, precio_max=22),
                 sniim(fecha=pd.Timestamp("2026-10-02"), precio_min=40, precio_frec=45, precio_max=50)]  # +125 %
    aceptados, cuarentena = evaluar("sniim", registros)
    assert len(cuarentena) == 0
    assert list(aceptados.sort_values("fecha")["advertencias"]) == ["", "CQ-09"]