# Plan de entregas — Trusted Data Lab

| Unidad | Entrega | Peso en Ingeniería de Datos | Contenido |
|---|---|---|---|
| 3 | **E0** | 10 % | Propuesta del observatorio, entrevista de campo, 3 preguntas analíticas, plan de recopilación ético y legal, máquina de captura en Bronce con GitHub Actions y sistema de calidad inicial (PSP) |
| 3 | **E1** | 40 % | Pronóstico de la variable objetivo: precio frecuente semanal del limón # 5 de Colima (ver `docs/E0/propuesta.md` §3.1) |
| 4 | **E2** | 20 % | Experimento con factores: temporada × calibre × lluvia (ver §3.2) |
| 4 | **E3** | 15 % | Comparación de grupos multivariados: mercados de destino (ver §3.3) |
| 4 | **E4** | 15 % | Por definir según la rúbrica oficial |

> El detalle de E1 a E4 se completará cuando se publiquen las rúbricas oficiales.

## Cómo etiquetar cada entrega

```powershell
git add .
git commit -m "E1: <descripción>"
git push
git tag -a e1 -m "Entrega E1"
git push origin e1
```