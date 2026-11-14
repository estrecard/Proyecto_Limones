# Reporte de limpieza y preprocesamiento — E1

*Generado automáticamente por `src/transform/gold.py` el 14/11/2026 06:27.*

## 1. Resolución de conflictos de esquema (SNIIM)

El mismo día, mercado y calibre puede aparecer en varias presentaciones (caja de 20 kg, arpilla de 15 kg, kilogramo...).
Como todos los precios se pidieron en **$/kg calculado**, las presentaciones son comparables y se consolidan con la **mediana**.

| Concepto | Valor |
|---|---|
| Registros en Plata | 19168 |
| Llaves únicas (fecha, mercado, calibre) | 15229 |
| Llaves con varias presentaciones | 3002 |
| Textos distintos en 'observaciones' | 17 |
| Categorías después de normalizar | {'Sin observación': 19145, 'Baja': 10, 'Alza': 8, 'Otra': 5} |

Otras resoluciones: comillas eliminadas de los nombres de mercado; texto libre de observaciones normalizado
con expresiones regulares (corrige errores como "A LA ALAZA" o "a la alza") a *Alza / Baja / Otra*.

## 2. Valores faltantes: diagnóstico del mecanismo

Se construyó el panel completo **día hábil × serie (mercado, calibre)** dentro del periodo activo de cada serie.

| Concepto | Valor |
|---|---|
| Días hábiles con publicación del SNIIM | 973 |
| Celdas del panel | 16630 |
| Celdas faltantes | 1401 (8.42 %) |

**Faltantes por temporada (%):** {'Alta oferta (may-sep)': 8.75, 'Baja oferta (ene-abr)': 8.03, 'Transición (oct-dic)': 8.35}

**Faltantes por día de la semana (%):** {'Jueves': 10.69, 'Lunes': 11.36, 'Martes': 4.85, 'Miércoles': 10.5, 'Viernes': 4.93}

**Pruebas:**
- Independencia faltante × temporada (χ²): p = 0.34
- Independencia faltante × día de la semana (χ²): p = 4.73e-39
- Precio previo a un hueco vs. sin hueco (Mann-Whitney): p = 2.15e-06
  (mediana 20.53 vs 24.00 $/kg)

**Interpretación:**
- **Temporada:** p = 0.34 → el porcentaje de faltantes **no** cambia de forma significativa entre temporadas.
- **Día de la semana:** p = 4.73e-39 → los faltantes **dependen del día** (algunos mercados no reportan ciertos días). La falta depende de una variable observada, así que el mecanismo **no es MCAR** sino **MAR**.
- **Precio antes del hueco:** p = 2.15e-06, mediana 20.53 vs 24.00 $/kg → los huecos aparecen cuando el precio venía **más bajo**: indicio de **MNAR** (el limón de Colima deja de llegar a ese mercado cuando no conviene enviarlo). Por eso los huecos largos **no se imputan**.
- **Conclusión:** los faltantes **no son MCAR**. Los huecos cortos se tratan como MAR (se pueden interpolar) y los huecos largos como posible MNAR (se dejan vacíos y se documentan).
- Series más incompletas: {'Colima: Centros de distribución de Colima | Limón c/semilla # 5': 59.0, 'Sonora: Central de Abasto de Cd. Obregón | Limón c/semilla # 5': 58.2, 'Sonora: Central de Abasto de Cd. Obregón | Limón c/semilla # 3': 43.7, 'Sonora: Central de Abasto de Cd. Obregón | Limón c/semilla # 4': 4.3, 'Sinaloa: Zona de Abasto de Mazatlán | Limón c/semilla # 5': 3.9, 'Durango: Centro de Distribución y Abasto de Gómez Palacio | Limón c/semilla # 5': 3.7}

**Otras fuentes:** Open-Meteo: 0 días faltantes (serie diaria completa). Banxico: fines de semana y festivos: el FIX no se publica (faltante estructural).

## 3. Imputación justificada

| Caso | Mecanismo | Tratamiento | Justificación |
|---|---|---|---|
| Huecos interiores ≤ 2 semanas en la serie semanal | MAR (festivos, días sin reporte) | Interpolación lineal | El precio cambia de forma gradual; un hueco corto se aproxima bien con sus vecinos |
| Huecos > 2 semanas | Probable MNAR (el limón de Colima no llegó a ese mercado) | **No se imputa**, queda vacío | Inventar semanas sin comercio sesgaría el modelo |
| Tipo de cambio en fines de semana y festivos | Estructural | LOCF (último valor publicado) | El FIX publicado sigue vigente hasta la siguiente publicación |

| Concepto | Valor |
|---|---|
| Semanas vacías antes de imputar | 152 |
| Semanas imputadas (interpolación) | 11 |
| Semanas que quedan vacías (huecos largos) | 141 |
| Días de tipo de cambio rellenados con LOCF | 440 |

Cada valor imputado queda marcado en la columna `imputado` de la capa Oro.

## 4. Atípicos y ruido

El precio del limón es muy estacional: una regla global marcaría como "atípico" todo febrero. Por eso se calcula una
**tendencia local** (mediana móvil centrada de 15 días hábiles por serie) y los métodos se aplican al
**residuo relativo** = (precio − tendencia) / tendencia.

**Hallazgo:** el precio es "pegajoso" — el **76.6 %** de los residuos es exactamente 0 porque el mismo
precio se repite varios días. Serie por serie, la MAD y el IQR valen 0, lo que hace inútiles ambos métodos
(el Z robusto divide entre 0 y el IQR marcaría cualquier cambio de precio). Por eso la escala se estima con los
**3560 residuos distintos de 0, juntando todas las series** (al ser porcentajes son comparables):
mediana = 0.39 %, MAD = 6.75 %.

- **Z-score robusto** (Iglewicz y Hoaglin, 1993): z = 0.6745·(x − mediana)/MAD; atípico si |z| > 3.5 (equivale a desviarse más de ~35.4 % de la tendencia).
- **IQR de Tukey**: atípico fuera de [-26.8 %, 27.2 %].

**Tratamiento:** solo se corrige lo que **ambos** métodos marcan **y es aislado** (≤ 2 días seguidos): eso es ruido
(error de captura o una venta puntual). Si la desviación se sostiene más días, es un **cambio de nivel real** del mercado:
se marca en `atipico_persistente` pero **no se modifica**. El valor corregido va en `precio_frec_limpio` y el original
se conserva en `precio_frec_original` (nada se borra).

| Concepto | Valor |
|---|---|
| Registros diarios evaluados | 15229 |
| Marcados por Z robusto | 64 |
| Marcados por IQR | 134 |
| Marcados por ambos | 64 |
| Persistentes (cambio de nivel, no se corrigen) | 59 |
| Aislados (ruido, corregidos) | 5 (0.03 %) |

Ejemplos de valores corregidos:

| Fecha | Mercado | Calibre | Precio reportado | Tendencia local | Z robusto |
|---|---|---|---|---|---|
| 28/02/2023 | Jalisco: Mercado Felipe Ángeles de Guadalajara | #5 | 40.0 | 20.0 | 9.95 |
| 05/06/2023 | Sonora: Central de Abasto de Cd. Obregón | #5 | 35.68 | 22.89 | 5.54 |
| 13/11/2026 | Colima: Centros de distribución de Colima | #5 | 22.0 | 37.0 | -4.09 |
| 11/03/2025 | Jalisco: Mercado Felipe Ángeles de Guadalajara | #5 | 36.67 | 26.0 | 4.06 |
| 13/11/2026 | Sonora: Mercado de Abasto Francisco I. Madero de Hermosillo | #5 | 22.0 | 16.0 | 3.71 |

## 5. Reducción de datos

- **Agregación:** de 15229 registros diarios a 3433 registros semanales (factor 4.4×). La semana es el horizonte que necesita el cliente.
- **Selección de variables:** se eliminan las constantes ["calidad (siempre 'Primera')", "origen (siempre 'Colima')", "seccion (siempre 'Frutas')", 'fuente'] y las técnicas ['fecha_captura', 'archivo_origen', 'producto_id', 'advertencias'] (se conservan en Plata para trazabilidad).
- **Selección de series:** 19 series con al menos 26 semanas; descartadas por cortas: {'Aguascalientes: Central de Abasto de Aguascalientes | Limón c/semilla # 5': 1, 'Sinaloa: Zona de Abasto de Mazatlán | Limón c/semilla # 5': 22}.

## 6. Integración de fuentes heterogéneas

| Conflicto | SNIIM | Open-Meteo | Banxico | Resolución |
|---|---|---|---|---|
| Formato de fecha | `dd/mm/aaaa` (texto) | `aaaa-mm-dd` | `dd/mm/aaaa` | Conversión explícita a `datetime` con formato fijo (Plata) |
| Tipo de los valores | Texto (`"20.00"`) | Número | Texto, con `"N/E"` | Conversión a número; lo no convertible queda vacío y lo atrapa la puerta de calidad |
| Calendario | Días hábiles | Todos los días | Días hábiles bancarios | Agregación a **semana (lunes a domingo)**; LOCF diario para el tipo de cambio |
| Granularidad | Mercado × calibre × presentación | Un punto (Tecomán) | Nacional | Clima y tipo de cambio se replican para todos los mercados de la semana |
| Unidades | $/kg calculado | mm, °C | MXN/USD | Se documentan en el nombre de la columna (`_mm`, `_kg`) |
| Llave | (fecha, mercado, calibre) | fecha | fecha | Llave común: `semana` |

| Concepto | Valor |
|---|---|
| Filas integradas | 3433 |
| Semanas sin clima | 0 |
| Semanas sin tipo de cambio | 0 |

Las semanas sin clima corresponden a la semana más reciente: Open-Meteo publica el reanálisis con ~5 días de retraso,
así que esos valores se completan solos en la siguiente ejecución automática.

## 7. Discretización y jerarquías conceptuales

| Jerarquía | Niveles |
|---|---|
| Tiempo | semana → mes → trimestre → año; y **temporada** del ciclo del limón (baja oferta ene-abr, alta oferta may-sep, transición oct-dic) |
| Geografía | mercado → estado → **región** {'Centro-Norte': 3, 'Golfo-Sureste': 2, 'Noroeste': 3, 'Norte': 5, 'Occidente': 3} |
| Producto | calibre (#3, #4, #5, S/C) → **tamaño** (Mediano, Grande, Sin clasificar) |

Discretización por terciles:
- `lluvia_30d_nivel`: Baja / Media / Alta, cortes en [4.0, 86.2] mm.
- `precio_nivel`: Bajo / Medio / Alto, cortes en [20.8, 27.5] $/kg.

## 8. Normalización y estandarización

Para cada variable continua se agregan dos columnas: `_minmax` = (x − min)/(max − min) en [0, 1] y `_z` = (x − media)/desv.

| Variable | Mín | Máx | Media | Desv. estándar |
|---|---|---|---|---|
| precio | 9.33 | 74.664 | 25.3642 | 8.3017 |
| lluvia_30d_mm | 0.0 | 438.6 | 77.0679 | 101.0103 |
| lluvia_semana_mm | 0.0 | 269.8 | 18.202 | 33.8731 |
| temp_media | 21.4 | 30.4714 | 26.2997 | 1.7662 |
| tipo_cambio | 16.5262 | 20.6838 | 18.2319 | 1.124 |

Los parámetros se guardan en `data/gold/parametros_normalizacion.json`. **Nota para el modelado (E1/E3):** al entrenar un modelo,
los parámetros deben recalcularse solo con el periodo de entrenamiento para no filtrar información del futuro.

## 9. Salidas en la capa Oro

| Archivo | Contenido |
|---|---|
| `data/gold/sniim_diario_limpio.csv` | Precio diario consolidado con banderas de atípico y valor original |
| `data/gold/limon_semanal.csv` | Tabla analítica: mercado × calibre × semana + clima + tipo de cambio + jerarquías + normalización |
| `data/gold/limon_semanal_nacional.csv` | Variable objetivo para el pronóstico: mediana semanal por calibre + covariables |
| `data/gold/parametros_normalizacion.json` | Parámetros Min-Max y Z-score |
