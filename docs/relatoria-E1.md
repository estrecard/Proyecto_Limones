# Relatoría de la etapa E1 — LimónLab Colima



**Integrante:** Liza la foránea · **Periodo:** 12 al 13 de noviembre de 2026

## 1. Objetivo de la etapa

Llevar los datos crudos del observatorio (precios del SNIIM, clima de Tecomán y tipo de cambio) a las capas
**Plata** y **Oro** mediante un pipeline automático de limpieza estadística, con una **puerta de calidad** que manda
los registros inválidos a cuarentena con su motivo, sin borrar nada.

## 2. Qué se hizo

1. **Puerta de calidad con Pandera.** Las 12 reglas del plan de calidad de la E0 se convirtieron en un esquema de
   Pandera por fuente. Cada regla lleva su código (CQ-01 a CQ-12) para que la cuarentena diga exactamente qué falló.
2. **Resolución de conflictos.** Un mismo día y mercado puede reportar varias presentaciones (caja, arpilla, kilo),
   y las observaciones vienen escritas a mano con errores. Se consolidaron y se normalizaron.
3. **Diagnóstico de faltantes.** Se armó el panel completo de días hábiles por mercado y calibre, y se probó si
   los huecos dependían de la temporada, del día de la semana o del precio.
4. **Atípicos y ruido.** Se separó la tendencia del precio con una mediana móvil y se aplicaron Z-score robusto e IQR al residuo.
5. **Reducción, integración, discretización y normalización.** Paso a semanas, unión con el clima y el dólar,
   jerarquías (temporada, región, tamaño) y columnas Min-Max y Z-score.
6. **Automatización y pruebas.** La capa Oro se agregó al pipeline y a GitHub Actions, con 32 pruebas automáticas.

## 3. Decisiones importantes y por qué

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Consolidar presentaciones con la **mediana** | Promedio | Una presentación con precio extremo movería mucho el promedio |
| Buscar atípicos en el **residuo** respecto a la tendencia | Z-score sobre el precio | El limón es muy estacional: todo febrero saldría "atípico" |
| Estimar la escala con los residuos **distintos de 0** de todas las series | MAD/IQR por serie | El precio es "pegajoso" (76.7 % de residuos = 0) y la MAD por serie valía 0 |
| Corregir solo desviaciones **aisladas** (≤ 2 días) | Corregir todo lo marcado | 59 de 62 desviaciones duraban varios días: eran cambios de precio reales, no errores |
| No imputar huecos **largos** | Interpolar todo | Indicio de MNAR: el limón de Colima no llegó a ese mercado; inventar precios sesgaría el pronóstico |
| Trabajar por **semana** | Por día | Es el horizonte que necesita el cliente (pronóstico a 2–4 semanas) y reduce el ruido diario |

## 4. Problemas encontrados y cómo se resolvieron

| Problema | Solución |
|---|---|
| La primera versión de atípicos marcó **0** casos (MAD = 0) y el IQR marcó **3,552** (cualquier cambio de precio) | Residuo relativo y escala con residuos distintos de 0 (defecto D15) |
| Rachas de varios días se trataban como ruido | Regla de persistencia: solo se corrige lo aislado (D16) |
| Error de parámetros duplicados en el esquema de Pandera | Corregido antes de ejecutar (D17) |
| La expresión regular no reconocía "A LA ALAZA" | Lo detectó una prueba automática; se corrigió (D18) |
| Windows bloquea algunas librerías compiladas (Control inteligente de aplicaciones) | Se usa `python -m pip`, CSV como respaldo y GitHub Actions como entorno limpio |

## 5. Hallazgos sobre los datos

- La puerta de calidad encontró un **error real** del SNIIM: un precio frecuente menor que el mínimo (Cd. Obregón, 05/03/2025).
- Los faltantes **no son al azar**: algunos mercados no reportan ciertos días de la semana, y los huecos aparecen cuando el precio venía más bajo.
- El calibre **# 5** domina los registros, y el calibre # 2 de origen Colima no aparece en ningún mercado.
- No hay registros de origen Colima en la Central de Abasto de Iztapalapa (CDMX): el limón colimense que reporta el SNIIM va sobre todo al norte y al Bajío.

## 6. Aprendizajes

- +
- $a1 = Read-Host "Aprendizaje 1"
- 

## 7. Siguientes pasos

- Usar `data/gold/limon_semanal_nacional.csv` (calibre # 5) como variable objetivo del pronóstico.
- Recalcular los parámetros de normalización solo con el periodo de entrenamiento al modelar.
- Completar la entrevista de campo pendiente de la E0.
