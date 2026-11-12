"""Muestra en pantalla el resumen del reporte de calidad más reciente (logs/calidad_*.json).

Uso:
    python -m src.quality.reporte
"""
import json

from src.utils import ruta


def main():
    reportes = sorted(ruta("logs").glob("calidad_*.json"))
    if not reportes:
        print("No hay reportes de calidad. Ejecuta primero: python -m src.transform.silver")
        return
    r = json.loads(reportes[-1].read_text(encoding="utf-8"))
    print(f"Reporte: {reportes[-1].name}   (ejecución {r['fecha_ejecucion']})\n")
    print(f"{'Fuente':<11} {'Evaluados':>9} {'Plata':>7} {'Cuarent.':>8} {'Advert.':>7} {'Acept.%':>8}  Periodo")
    for fuente, m in r["fuentes"].items():
        if not m.get("registros_evaluados"):
            print(f"{fuente:<11} sin datos")
            continue
        print(f"{fuente:<11} {m['registros_evaluados']:>9} {m['registros_plata']:>7} {m['registros_cuarentena']:>8} "
              f"{m['registros_con_advertencia']:>7} {m['tasa_aceptacion_pct']:>8}  {m['fecha_min']} a {m['fecha_max']}")
    print("\nReglas con registros detectados:")
    hubo = False
    for fuente, m in r["fuentes"].items():
        for regla in m.get("reglas", []):
            if regla["registros_que_fallan"]:
                hubo = True
                print(f"  {fuente:<11} {regla['codigo']} ({regla['tipo']}): {regla['registros_que_fallan']} — {regla['descripcion']}")
    if not hubo:
        print("  Ninguna: todos los registros pasaron las puertas de calidad.")


if __name__ == "__main__":
    main()