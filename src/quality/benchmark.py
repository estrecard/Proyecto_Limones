"""Optimización medida (E3): compara la versión de la etiqueta e2 (ANTES) contra la versión actual (DESPUÉS).

Qué hace, sin tocar tus datos reales:
  1. Crea dos carpetas temporales ("caja de arena"): una con el código de la etiqueta e2 y otra con el código actual.
  2. Copia en las dos EXACTAMENTE la misma capa Bronce, para que la comparación sea justa.
  3. En cada una mide, varias veces, la reconstrucción Bronce → Plata → Oro → linaje:
       - tiempo de ejecución por etapa (time.perf_counter),
       - memoria pico por etapa (tracemalloc, en una corrida aparte porque tracemalloc la hace más lenta),
       - huella (SHA-256) de las salidas, para demostrar que la optimización NO cambió los resultados.
  4. Prueba de errores (inyección de fallas): mete archivos de Bronce dañados (JSON roto, metadatos rotos)
     y ejecuta el pipeline completo. Cuenta errores de etapa y si la capa Oro se pudo actualizar.
  5. Escribe docs/E3/benchmark.json y docs/E3/optimizacion.md con la comparativa.

Uso:
    python -m src.quality.benchmark                 # antes = etiqueta e2, 3 repeticiones
    python -m src.quality.benchmark --repeticiones 5
    python -m src.quality.benchmark --antes e1      # comparar contra otra etiqueta
"""
import argparse
import hashlib
import io
import json
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDAS = ["data/silver/sniim.csv", "data/silver/open_meteo.csv", "data/silver/banxico.csv",
           "data/gold/sniim_diario_limpio.csv", "data/gold/limon_semanal.csv",
           "data/gold/limon_semanal_nacional.csv", "data/gold/parametros_normalizacion.json"]

# ----------------------------------------------------------------------------- lo que corre DENTRO de cada caja
MEDIDOR = r'''
import json, sys, time, tracemalloc, logging
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
n, salida = int(sys.argv[1]), Path(sys.argv[2])
from src.transform import silver, gold
from src.quality import linaje
for nombre in list(logging.root.manager.loggerDict):          # sin texto en pantalla: solo medimos
    for h in logging.getLogger(nombre).handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            h.setLevel(logging.CRITICAL)
ETAPAS = [("plata", silver.main), ("oro", gold.main), ("linaje", linaje.validar)]
tiempos = {e: [] for e, _ in ETAPAS}
for i in range(n):
    for etapa, f in ETAPAS:
        t = time.perf_counter(); f(); tiempos[etapa].append(round(time.perf_counter() - t, 3))
memoria = {}
for etapa, f in ETAPAS:
    tracemalloc.start(); f(); memoria[etapa] = round(tracemalloc.get_traced_memory()[1] / 1e6, 1); tracemalloc.stop()
salida.write_text(json.dumps({"tiempos_s": tiempos, "memoria_pico_mb": memoria}), encoding="utf-8")
'''

FALLAS = r'''
import json, sys, logging
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
salida = Path(sys.argv[1])
bronce = Path("data/bronze")
danados = {
    "banxico": ("banxico_DANADO_20990101_000000.json", '{"bmx": {"series": [ {"datos": [ {"fecha": "01/01/20'),
    "open_meteo": ("open_meteo_DANADO_20990101_000000.json", '<html>503 Service Unavailable</html>'),
}
for fuente, (archivo, contenido) in danados.items():
    (bronce / fuente / archivo).write_text(contenido, encoding="utf-8")
    (bronce / fuente / (archivo.rsplit(".", 1)[0] + ".meta.json")).write_text(json.dumps(
        {"fuente": fuente, "archivo": archivo, "fecha_captura": "2099-01-01T00:00:00"}), encoding="utf-8")
(bronce / "sniim" / "sniim_DANADO_20990101_000000.meta.json").write_text('{"fuente": "sniim", "archi', encoding="utf-8")
oro = Path("data/gold/limon_semanal.csv")
marca = oro.stat().st_mtime if oro.exists() else 0
from src import pipeline
for nombre in list(logging.root.manager.loggerDict):
    for h in logging.getLogger(nombre).handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            h.setLevel(logging.CRITICAL)
try:
    codigo = pipeline.main(["--solo-plata"])
except SystemExit as e:
    codigo = e.code
except Exception as e:
    codigo = f"excepción: {e}"
ultima = json.loads(Path("logs/ejecuciones.jsonl").read_text(encoding="utf-8").strip().splitlines()[-1])
ilegibles = Path("data/quarantine/bronce_ilegible.csv")
salida.write_text(json.dumps({
    "archivos_danados_inyectados": 3,
    "codigo_salida": codigo,
    "estado": ultima.get("estado"),
    "errores_de_etapa": len(ultima.get("errores", [])),
    "detalle_errores": [e[:160] for e in ultima.get("errores", [])],
    "oro_actualizado": oro.exists() and oro.stat().st_mtime > marca,
    "archivos_danados_aislados": max(0, len(ilegibles.read_text(encoding="utf-8-sig").strip().splitlines()) - 1)
                                 if ilegibles.exists() else 0,
}, ensure_ascii=False), encoding="utf-8")
'''


# ----------------------------------------------------------------------------- preparación de las cajas
def preparar(destino: Path, referencia):
    destino.mkdir(parents=True)
    if referencia:  # código de una etiqueta de git (sin tocar tu carpeta de trabajo)
        zip_bytes = subprocess.run(["git", "archive", "--format=zip", referencia, "src", "config"],
                                   cwd=RAIZ, capture_output=True, check=True).stdout
        zipfile.ZipFile(io.BytesIO(zip_bytes)).extractall(destino)
    else:
        shutil.copytree(RAIZ / "src", destino / "src", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(RAIZ / "config", destino / "config")
    shutil.copytree(RAIZ / "data" / "bronze", destino / "data" / "bronze")  # la MISMA entrada para las dos


def ejecutar(caja: Path, codigo: str, *args) -> dict:
    script = caja / "_medicion.py"
    script.write_text(codigo, encoding="utf-8")
    resultado = caja / "_resultado.json"
    p = subprocess.run([sys.executable, str(script), *map(str, args), str(resultado)], cwd=caja,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 or not resultado.exists():
        raise RuntimeError(f"Falló la medición en {caja.name}:\n{p.stderr[-2000:]}")
    return json.loads(resultado.read_text(encoding="utf-8"))


def huellas(caja: Path) -> dict:
    return {s: hashlib.sha256((caja / s).read_bytes()).hexdigest()[:16] if (caja / s).exists() else None
            for s in SALIDAS}


def medir(nombre: str, referencia, base: Path, repeticiones: int) -> dict:
    print(f"  · {nombre}: preparando copia ({referencia or 'código actual'})...", flush=True)
    caja = base / nombre
    preparar(caja, referencia)
    print(f"  · {nombre}: midiendo tiempo ({repeticiones} repeticiones) y memoria...", flush=True)
    m = ejecutar(caja, MEDIDOR, repeticiones)
    m["huellas"] = huellas(caja)
    advert = [l for l in (caja / "logs" / "pipeline.log").read_text(encoding="utf-8").splitlines()
              if "| WARNING |" in l or "| ERROR " in l] if (caja / "logs" / "pipeline.log").exists() else []
    m["avisos_en_bitacora_por_corrida"] = round(len(advert) / (repeticiones + 1), 1)
    print(f"  · {nombre}: inyectando archivos dañados y ejecutando el pipeline completo...", flush=True)
    m["inyeccion_fallas"] = ejecutar(caja, FALLAS)
    m["referencia"] = referencia or "código actual"
    return m


# ----------------------------------------------------------------------------- reporte
def resumen_tiempos(t: list) -> dict:
    return {"primera_s": t[0], "mediana_s": statistics.median(t), "mediana_sin_primera_s":
            statistics.median(t[1:]) if len(t) > 1 else t[0]}


def pct(antes, despues):
    return round(100 * (antes - despues) / antes, 1) if antes else 0.0


def reporte(r: dict) -> str:
    a, d = r["antes"], r["despues"]
    filas_t, filas_m = [], []
    tot = {"a": 0, "d": 0, "d_frio": 0}
    for etapa in ["plata", "oro", "linaje"]:
        ta, td = resumen_tiempos(a["tiempos_s"][etapa]), resumen_tiempos(d["tiempos_s"][etapa])
        tot["a"] += ta["mediana_s"]; tot["d"] += td["mediana_sin_primera_s"]; tot["d_frio"] += td["primera_s"]
        mejora = (f"**{pct(ta['mediana_s'], td['mediana_sin_primera_s'])} %**"
                  if max(ta["mediana_s"], td["mediana_sin_primera_s"]) >= 0.1 else "≈ igual (diferencia < 0.1 s = ruido)")
        filas_t.append(f"| {etapa.capitalize()} | {ta['mediana_s']:.2f} | {td['primera_s']:.2f} | "
                       f"{td['mediana_sin_primera_s']:.2f} | {mejora} |")
        ma, md = a["memoria_pico_mb"][etapa], d["memoria_pico_mb"][etapa]
        filas_m.append(f"| {etapa.capitalize()} | {ma} | {md} | **{pct(ma, md)} %** |")
    filas_t.append(f"| **Total** | **{tot['a']:.2f}** | **{tot['d_frio']:.2f}** | **{tot['d']:.2f}** | "
                   f"**{pct(tot['a'], tot['d'])} %** (×{tot['a'] / max(tot['d'], 1e-9):.1f} más rápido) |")
    iguales = [s for s in SALIDAS if a["huellas"][s] == d["huellas"][s] and a["huellas"][s]]
    fa, fd = a["inyeccion_fallas"], d["inyeccion_fallas"]
    sino = lambda x: "sí" if x else "**no**"
    e = r["entorno"]
    return f"""# Optimización medida del pipeline — E3

Generado automáticamente por `python -m src.quality.benchmark` el {r['fecha']}.
**Antes** = código de la etiqueta `{a['referencia']}` · **Después** = código actual · Misma capa Bronce para las dos
({r['archivos_bronce']} archivos). Entorno: {e['sistema']}, Python {e['python']}, pandas {e['pandas']}, {e['cpus']} CPU.

## 1. Tiempo de ejecución (segundos, reconstrucción Bronce → Plata → Oro → linaje)

Mediana de {r['repeticiones']} repeticiones. La versión nueva tiene caché de lectura del SNIIM: la **primera** corrida
(caché vacía, como un clon nuevo del repositorio) cuesta lo mismo que antes. Las **siguientes** solo leen los archivos
nuevos, que es lo que pasa en la ejecución diaria.

| Etapa | Antes (mediana) | Después, 1.ª corrida (sin caché) | Después (mediana, con caché) | Mejora |
|---|---|---|---|---|
{chr(10).join(filas_t)}

## 2. Memoria pico (MB, medida con `tracemalloc`)

| Etapa | Antes | Después | Reducción |
|---|---|---|---|
{chr(10).join(filas_m)}

`tracemalloc` mide la memoria que reserva Python (incluye los arreglos de pandas/NumPy). No incluye la memoria
interna de librerías en C como lxml, por eso es una medida comparativa entre versiones y no el total del proceso.

## 3. Errores: archivos de Bronce dañados (inyección de fallas)

Se metieron {fa['archivos_danados_inyectados']} archivos dañados (JSON cortado de Banxico, una página de error en lugar
de JSON de Open-Meteo y un `.meta.json` roto del SNIIM) y se ejecutó `python -m src.pipeline --solo-plata`.

| Indicador | Antes | Después |
|---|---|---|
| Estado de la ejecución | {fa['estado']} | {fd['estado']} |
| Errores de etapa en la bitácora | {fa['errores_de_etapa']} | {fd['errores_de_etapa']} |
| ¿Se actualizó la capa Oro? | {sino(fa['oro_actualizado'])} | {sino(fd['oro_actualizado'])} |
| Archivos dañados aislados en `data/quarantine/bronce_ilegible.csv` | {fa['archivos_danados_aislados']} | {fd['archivos_danados_aislados']} |
| Avisos (WARNING/ERROR) por corrida normal en `logs/pipeline.log` | {a['avisos_en_bitacora_por_corrida']} | {d['avisos_en_bitacora_por_corrida']} |

Errores de la versión anterior: {'; '.join(fa['detalle_errores']) or 'ninguno'}

## 4. ¿Cambiaron los resultados?

Huella SHA-256 de las salidas de Plata y Oro: **{len(iguales)} de {len(SALIDAS)} archivos idénticos** byte por byte entre
antes y después.

| Archivo | Antes | Después |
|---|---|---|
{chr(10).join(f"| `{s}` | `{a['huellas'][s]}` | `{d['huellas'][s]}` |" for s in SALIDAS)}

## 5. Qué se optimizó

| # | Cambio | Archivo | Efecto |
|---|---|---|---|
| O1 | Caché de lectura del SNIIM: cada HTML de Bronce (inmutable) se interpreta con BeautifulSoup una sola vez y sus renglones se guardan en `data/cache/sniim_renglones.json` | `src/transform/silver.py` | Tiempo de Plata |
| O2 | Agregaciones vectorizadas en Oro: linaje (`unir_unicos_por_grupo`), moda, mediana móvil y relleno por serie, sin funciones `lambda` que creaban una Serie por cada uno de los ~15 mil grupos | `src/transform/gold.py` | Tiempo de Oro |
| O3 | Oro lee de Plata solo las columnas que usa (`usecols`) y Plata libera la caché conforme la convierte | `gold.py`, `silver.py` | Memoria |
| O4 | Tolerancia a archivos de Bronce dañados: se registran en cuarentena y el resto continúa | `silver.py` | Errores |
| O5 | El aviso de pyarrow se muestra una vez por ejecución y no una por fuente | `silver.py` | Ruido en bitácora |
"""


def main():
    parser = argparse.ArgumentParser(description="Comparativa antes/después del pipeline")
    parser.add_argument("--antes", default="e2", help="etiqueta de git de la versión anterior")
    parser.add_argument("--repeticiones", type=int, default=3)
    args = parser.parse_args()
    import pandas as pd

    base = Path(tempfile.mkdtemp(prefix="limonlab_bench_"))
    print(f"Caja de arena: {base}")
    try:
        r = {"fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "repeticiones": args.repeticiones,
             "archivos_bronce": sum(1 for p in (RAIZ / "data" / "bronze").rglob("*") if p.is_file()),
             "entorno": {"sistema": f"{platform.system()} {platform.release()}", "python": platform.python_version(),
                         "pandas": pd.__version__, "cpus": __import__("os").cpu_count()},
             "antes": medir("antes", args.antes, base, args.repeticiones),
             "despues": medir("despues", None, base, args.repeticiones)}
    finally:
        shutil.rmtree(base, ignore_errors=True)
    carpeta = RAIZ / "docs" / "E3"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "benchmark.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    (carpeta / "optimizacion.md").write_text(reporte(r), encoding="utf-8")
    print("Listo: docs/E3/optimizacion.md y docs/E3/benchmark.json")


if __name__ == "__main__":
    main()
