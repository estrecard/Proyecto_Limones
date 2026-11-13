# Ficha de entrega técnica — E0

| Campo | Valor |
|---|---|
| Proyecto | Trusted Data Lab — **LimónLab Colima** (Observatorio del Limón de Colima) |
| Entrega | **E0** — Propuesta, máquina de captura (Bronce) y sistema de calidad inicial |
| Integrante | Liza la foránea (trabajo individual) · GitHub: `estrecard` |
| Repositorio | https://github.com/estrecard/Proyecto_Limones |
| Etiqueta | `e0` → https://github.com/estrecard/Proyecto_Limones/tree/e0 |
| Fecha de entrega | 12/11/2026 |
| Docentes | Armando Roman Gallardo Heredia (Ingeniería de Datos) · Mtro. Joel (Análisis Estadístico) · Mtra. Isis (Calidad en los Sistemas de Información) |

## 1. Entregables y ubicación

| # | Entregable solicitado | Ubicación en el repositorio | Estado |
|---|---|---|---|
| 1 | Propuesta del observatorio: ficha, 3 preguntas analíticas y plan de recopilación con análisis ético y legal | [`docs/E0/propuesta.md`](propuesta.md) | ✅ |
| 1 | Entrevista de campo (≥ 15 min) | [`docs/E0/entrevista.md`](entrevista.md) | 🟡 Pendiente |
| 2a | Extractor ético ejecutándose automáticamente con GitHub Actions | [`.github/workflows/pipeline.yml`](../../.github/workflows/pipeline.yml) · [`src/pipeline.py`](../../src/pipeline.py) · [`src/ingest/`](../../src/ingest/) | ✅ |
| 2b | Serie histórica en crudo con ≥ 36 periodos | [`data/bronze/`](../../data/bronze/) — 47 meses (ene 2023 – nov 2026) | ✅ |
| 3a | Registros PSP abiertos | [`calidad/tiempo-liza.csv`](../../calidad/tiempo-liza.csv) · [`calidad/defectos-liza.csv`](../../calidad/defectos-liza.csv) | ✅ |
| 3b | 3 objetivos de calidad medibles | [`docs/E0/propuesta.md` §6.2](propuesta.md#62-objetivos-de-calidad-medibles) | ✅ |
| 4 | Ficha de entrega técnica | Este archivo | ✅ |

## 2. Arquitectura implementada

```
SNIIM (scraping) ─┐
Open-Meteo (API) ─┼─► data/bronze/ (crudo + .meta.json) ─► puertas de calidad CQ-01..CQ-12 ─┬─► data/silver/
Banxico (API) ────┘                                                                         └─► data/quarantine/
                         ▲
                GitHub Actions: lun-vie 18:17 (hora de Colima) · pytest antes de capturar
```

## 3. Datos capturados (capa Bronce)

| Fuente | Método | Periodo | Periodos mensuales | Archivos |
|---|---|---|---|---|
| SNIIM — limón c/semilla # 2, # 3, # 4, # 5 y sin clasificación, origen Colima | Scraping HTML | ene 2023 – nov 2026 | 47 | 235 HTML + 235 `.meta.json` |
| Open-Meteo — clima diario de Tecomán | API REST | ene 2023 – nov 2026 | 47 | JSON + `.meta.json` |
| Banxico — tipo de cambio FIX (SF43718) | API REST con token | ene 2023 – nov 2026 | 47 | JSON + `.meta.json` |

## 4. Cómo reproducir

```powershell
git clone https://github.com/estrecard/Proyecto_Limones.git
cd Proyecto_Limones
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env             # pegar el token de Banxico
python -m pytest                   # 25 pruebas
python -m src.pipeline             # captura incremental + capa Plata
python -m src.pipeline --historico # carga histórica completa (~15 min)
python -m src.quality.reporte      # resumen de calidad
```

## 5. Evidencias

- Ejecución exitosa de GitHub Actions: https://github.com/estrecard/Proyecto_Limones/actions/runs/43330815751 · captura en [`evidencia/actions.png`](evidencia/actions.png)
- Pruebas automáticas: [`docs/evidencia_pruebas_e1.txt`](../evidencia_pruebas_e1.txt) (25 pruebas aprobadas)
- Reporte de calidad: [`logs/calidad_20261113.json`](../../logs/calidad_20261113.json)
- Bitácora de ejecuciones: `logs/ejecuciones.jsonl`

## 6. Observaciones

- Entrega posterior a la fecha límite (09/11/2026).
- La entrevista de campo está pendiente; se agregará a `docs/E0/entrevista.md` y a la sección 2 de la propuesta, y se actualizará la etiqueta `e0`.
- Además de lo solicitado para la E0, el repositorio ya incluye la capa Plata con puertas de calidad (CQ-01 a CQ-12), la cuarentena y 25 pruebas automáticas.
- Limitación conocida: en la computadora local, el Control inteligente de aplicaciones de Windows bloquea `pyarrow`, así que la capa Plata se guarda en CSV (con Parquet cuando está disponible, como en GitHub Actions).