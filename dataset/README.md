# LimónLab Colima — Precios semanales del limón de Colima en centrales de abasto, con clima, tipo de cambio y geografía

**Versión 1.0.0** · periodo 2023-01-02 a 2026-11-22 · licencia **CC BY 4.0**
· ficha técnica: [datasheet.md](https://github.com/estrecard/Proyecto_Limones/blob/main/docs/E3/datasheet.md)

| Archivo | Filas | Columnas | Llave primaria | SHA-256 |
|---|---|---|---|---|
| `limon_semanal.csv` | 3448 | 42 | destino, producto, semana | `3f98340fbdf0f40a…` |
| `limon_semanal_nacional.csv` | 708 | 13 | producto, semana | `22ba0b48998e7afa…` |
| `mercados_geo.csv` | 18 | 15 | destino | `ed56b1df3803602a…` |

El esquema completo (tipo y descripción de cada columna) está en `datapackage.json`
(formato estándar [Frictionless Data Package](https://specs.frictionlessdata.io/data-package/)).
Los archivos van en UTF-8 sin BOM; en Excel ábrelos con *Datos → Desde texto/CSV* eligiendo UTF-8.

## Cargar los datos

```python
import pandas as pd
semanal = pd.read_csv("limon_semanal.csv", parse_dates=["semana"])
nacional = pd.read_csv("limon_semanal_nacional.csv", parse_dates=["semana"])
```

## Cómo citar

Cárdenas Cuevas, E. E. (2026). *LimónLab Colima: precios semanales del limón de Colima en centrales de abasto*
(versión 1.0.0) [Conjunto de datos]. https://github.com/estrecard/Proyecto_Limones

Y conserva la atribución de las fuentes indicada en `LICENSE.md`.
