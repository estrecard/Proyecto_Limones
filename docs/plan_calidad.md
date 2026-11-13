# Plan de calidad de datos (Calidad en los Sistemas de Información)

El plan se basa en el modelo de calidad de datos **ISO/IEC 25012**. Cada regla es una **puerta de calidad automática**. Si un registro falla una regla **bloqueante**, se envía a `data/quarantine/` con el código de la regla y el motivo. Si falla una regla de **advertencia**, pasa a Plata pero queda marcado.

## Dimensiones y reglas

| Código | Dimensión ISO 25012 | Fuente | Regla | Tipo |
|---|---|---|---|---|
| CQ-01 | Completitud | Todas | Campos obligatorios no nulos (fecha, central, precio frecuente) | Bloqueante |
| CQ-02 | Exactitud sintáctica | Todas | Fecha válida y no futura | Bloqueante |
| CQ-03 | Exactitud semántica | SNIIM | 2 ≤ precio $/kg ≤ 150 | Bloqueante |
| CQ-04 | Consistencia | SNIIM | precio mínimo ≤ precio frecuente ≤ precio máximo | Bloqueante |
| CQ-05 | Unicidad | Todas | Sin duplicados por llave (fecha + central + presentación) | Bloqueante (se conserva el primero) |
| CQ-06 | Exactitud semántica | Open-Meteo | precipitación ≥ 0; −5 ≤ temperatura ≤ 50 °C | Bloqueante |
| CQ-07 | Consistencia | Open-Meteo | temp. mínima ≤ temp. media ≤ temp. máxima | Bloqueante |
| CQ-08 | Exactitud semántica | Banxico | 10 ≤ tipo de cambio ≤ 40 MXN/USD | Bloqueante |
| CQ-09 | Credibilidad | SNIIM | Variación diaria del precio frecuente ≤ 50 % | Advertencia |
| CQ-10 | Actualidad | Todas | Dato más reciente con ≤ 7 días de antigüedad | Advertencia |
| CQ-11 | Conformidad | SNIIM | Producto y central coinciden con el catálogo normalizado | Bloqueante |
| CQ-12 | Trazabilidad | Todas | Cada registro conserva `fuente`, `fecha_captura` y `archivo_origen` | Bloqueante |

## Métricas de calidad por ejecución

- **% de completitud** por columna.
- **Tasa de aceptación** = registros en Plata / registros en Bronce.
- **Registros en cuarentena** por regla.
- **Frescura**: días desde el último dato por fuente.

Se guardan en `logs/calidad_AAAAMMDD.json` y se muestran en el observatorio (E3).

## Política de cuarentena

1. Nunca se borran datos. Lo rechazado se guarda con `regla_fallida`, `motivo` y `fecha_rechazo`.
2. Bronce es inmutable. Si una regla cambia, Plata se regenera desde Bronce.
3. Los umbrales viven en `config/settings.yaml` para ajustarlos sin tocar el código.
## Implementación (E1): puerta de calidad con Pandera

Desde la E1 las reglas se implementan con **Pandera** (`src/quality/gates.py`): un `DataFrameSchema` por fuente define
columnas, tipos (con conversión estricta), nulos permitidos, rangos y reglas entre columnas. Cada `Check` lleva el código
de la regla (por ejemplo `CQ-04`). La validación se ejecuta en modo *lazy*, que reúne todas las fallas con el índice del
registro; con eso cada registro inválido va a `data/quarantine/` con `regla_fallida`, `motivo` y `fecha_rechazo`.

| Regla nueva | Dimensión | Descripción |
|---|---|---|
| CQ-ESQ | Conformidad de esquema | Un valor no se pudo convertir al tipo esperado (texto donde va número, etc.) |

- La unicidad (CQ-05) se evalúa en un segundo esquema, solo sobre los registros que pasaron el primero.
- CQ-09 (advertencia) y CQ-10 (actualidad) se calculan con pandas porque no rechazan registros.
- Si falla la **estructura** (por ejemplo, falta una columna completa), el pipeline se detiene con error: no es un problema de registros sino de la fuente.
