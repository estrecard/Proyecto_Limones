# Código fuente

| Módulo | Responsabilidad | Entrega |
|---|---|---|
| `ingest/` | Captura de SNIIM (scraping), Open-Meteo y Banxico (API) hacia Bronce | E1 |
| `quality/` | Puertas de calidad CQ-01 a CQ-12 y cuarentena | E1 |
| `transform/` | Limpieza Bronce → Plata e integración Plata → Oro | E1 / E2 |
| `pipeline.py` | Orquestador de punta a punta | E1 |