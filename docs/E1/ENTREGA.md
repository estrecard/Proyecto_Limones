# Ficha de entrega técnica — E1

| Campo | Valor |
|---|---|
| Proyecto | Trusted Data Lab — **LimónLab Colima** (Observatorio del Limón de Colima) |
| Entrega | **E1** — Pipelines de limpieza estadística hacia Plata y Oro, con puerta de calidad automática y cuarentena |
| Integrante | Liza la foránea (trabajo individual) · GitHub: `estrecard` |
| Repositorio | https://github.com/estrecard/Proyecto_Limones |
| Etiqueta | `e1` → https://github.com/estrecard/Proyecto_Limones/tree/e1 |
| Fecha de entrega | 13/11/2026 |
| Docentes | Armando Roman Gallardo Heredia (Ingeniería de Datos) · Mtro. Joel (Análisis Estadístico) · Mtra. Isis (Calidad en los Sistemas de Información) |

## 1. Entregables y ubicación

| # | Entregable solicitado | Dónde está | Evidencia |
|---|---|---|---|
| 1a | Valores faltantes: diagnóstico MCAR/MAR/MNAR e imputación justificada | `src/transform/gold.py` → `diagnosticar_faltantes()`, `semanal_sniim()`, `semanal_dolar()` | [Reporte §2–3](reporte_limpieza.md#2-valores-faltantes-diagnóstico-del-mecanismo) |
| 1b | Atípicos y ruido (IQR y Z-score robusto) | `tratar_atipicos()` | [Reporte §4](reporte_limpieza.md#4-atípicos-y-ruido) |
| 1c | Normalización Min-Max y Z-score | `normalizar()` → columnas `_minmax` y `_z`; `data/gold/parametros_normalizacion.json` | [Reporte §8](reporte_limpieza.md#8-normalización-y-estandarización) |
| 1d | Discretización y jerarquías conceptuales | `discretizar()` → temporada, región, tamaño, terciles de lluvia y precio | [Reporte §7](reporte_limpieza.md#7-discretización-y-jerarquías-conceptuales) |
| 1e | Reducción de datos | `semanal_sniim()` → agregación diaria → semanal y selección de variables y series | [Reporte §5](reporte_limpieza.md#5-reducción-de-datos) |
| 2 | Integración y resolución de conflictos de esquema y tipos | `consolidar_sniim()`, `integrar()`; conversión de tipos en `src/transform/silver.py` | [Reporte §1 y §6](reporte_limpieza.md#6-integración-de-fuentes-heterogéneas) |
| 3 | Puerta de calidad automática con **Pandera** y cuarentena con motivo | `src/quality/gates.py` (un `DataFrameSchema` por fuente) → `data/quarantine/*_cuarentena.csv` | [`docs/plan_calidad.md`](../plan_calidad.md) · `logs/calidad_AAAAMMDD.json` |
| 4 | Ficha técnica y relatoría | Este archivo · [`docs/relatoria-E1.md`](../relatoria-E1.md) | — |

Se entregan **scripts en `src/`** (opción permitida por la rúbrica). El reporte [`docs/E1/reporte_limpieza.md`](reporte_limpieza.md)
se **genera automáticamente** en cada ejecución con los números reales de esa corrida.

## 2. Flujo implementado

```
Bronce (crudo) ─► silver.py: tipos y fechas ─► Pandera (CQ-01..CQ-12, CQ-ESQ) ─┬─► Plata
                                                                               └─► Cuarentena (regla_fallida, motivo, fecha_rechazo)
Plata ─► gold.py: conflictos ─► faltantes ─► atípicos ─► reducción semanal ─► imputación
               ─► integración (SNIIM + clima + tipo de cambio) ─► discretización ─► normalización ─► Oro
```

Todo corre con un solo comando (`python -m src.pipeline`) y de forma automática en **GitHub Actions** de lunes a viernes.

## 3. Resultados principales (ejecución del 13/11/2026)

| Etapa | Resultado |
|---|---|
| Puerta de calidad | SNIIM 19,150/19,151 aceptados (99.99 %); **1 registro en cuarentena** (CQ-04: precio frecuente menor que el mínimo, Cd. Obregón, 05/03/2025); 57 advertencias CQ-09. Open-Meteo y Banxico, 100 % |
| Conflictos de esquema | 2,064 + 936 llaves (fecha, mercado, calibre) con varias presentaciones, consolidadas con la mediana del precio en $/kg |
| Faltantes | 8.42 % del panel diario. **No son MCAR**: dependen del día de la semana (χ², p ≈ 1e-38 → MAR) y aparecen cuando el precio venía más bajo (Mann-Whitney, p ≈ 3e-6 → indicio de MNAR) |
| Imputación | 11 semanas interpoladas (huecos ≤ 2 semanas); 141 semanas de huecos largos sin imputar; 440 días de tipo de cambio con LOCF |
| Atípicos | Precio "pegajoso" (76.7 % de residuos = 0) → escala estimada con residuos distintos de 0. 62 desviaciones fuertes: **59 cambios de nivel reales** (se marcan) y **3 ruidos aislados** (se corrigen) |
| Reducción | 15,214 registros diarios → 3,433 semanales (4.4×); 19 series válidas |
| Oro | `limon_semanal.csv` (tabla analítica), `limon_semanal_nacional.csv` (variable objetivo), `sniim_diario_limpio.csv` |

## 4. Cómo reproducir

```powershell
git clone https://github.com/estrecard/Proyecto_Limones.git
cd Proyecto_Limones
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env               # pegar el token de Banxico
python -m pytest                     # 32 pruebas
python -m src.pipeline --solo-plata  # Plata (Pandera) + Oro con los datos de Bronce ya descargados
python -m src.pipeline               # captura incremental + Plata + Oro
```

## 5. Pruebas automáticas

| Archivo | Qué prueba |
|---|---|
| `tests/test_gates.py` | Cada regla de la puerta Pandera manda a cuarentena el error que le corresponde, con su motivo |
| `tests/test_ingesta_y_plata.py` | Lector del SNIIM con una página real, conversión de tipos y consolidación de capturas |
| `tests/test_gold.py` | Mediana de presentaciones, texto libre, atípico aislado vs. cambio de nivel, imputación solo de huecos cortos, LOCF, Min-Max y Z-score |

## 6. Evidencias

- Ejecuciones de GitHub Actions (Bronce → Plata → Oro), manuales y programadas: https://github.com/estrecard/Proyecto_Limones/actions/workflows/pipeline.yml
- Pruebas: [`docs/E1/evidencia_pruebas.txt`](evidencia_pruebas.txt) (32 pruebas aprobadas)
- Reporte de calidad: `logs/calidad_AAAAMMDD.json` · Resumen de Oro: `logs/gold_resumen.json`
- Registros en cuarentena: `data/quarantine/sniim_cuarentena.csv`
