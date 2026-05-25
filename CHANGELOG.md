# Changelog

## v2.0.0 - Refactor modular estable
Fecha: 2026-05-21

- Creacion de `schema.py`.
- Creacion de `pdf_report.py`.
- Creacion de `validation.py`.
- Creacion de `catalogs.py`.
- Creacion de `config.py`.
- Separacion de metricas en `metrics.py`.
- Normalizacion de `Utilizacion %`.
- Conexion segura de rutas desde `config.py`.

## v1.0.5 - Dashboard KPI Profesional
Fecha: 2026-05-20

- Se consolidó `C:\Python_Proyectos\Report_Perforacion` como carpeta oficial del sistema.
- Se corrigió SmartROC D65 de equipo `9239` a `9339` en código y datos históricos.
- Se agregó dashboard KPI profesional por equipo con fotos, estado operacional y métricas.
- Se agregó sección visual de KPI operacional por equipo en PDF con tarjetas e imágenes.
- Se corrigió lógica de estado operacional para mantención programada, avería, sin marcación y operación parcial.
- Se corrigió disponibilidad para descontar averías, mantenciones programadas, standby y sin marcación.
- Se mantuvo intacta la generación de Excel, PDF, historial, filtros, validaciones y reportes acumulados.

## v1.0.4 - Consolidación de versión estable
Fecha: 2026-05-20

- Se comparo la carpeta oficial contra respaldos historicos.
- Se fusionó el Excel histórico sin perder registros.
- Se dejó Streamlit ejecutando desde la carpeta oficial.
