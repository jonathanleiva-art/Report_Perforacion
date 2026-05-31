# Changelog

## Pendiente - Preparacion de ortomosaicos operacionales
Fecha: 2026-05-25

- Se agrego la carpeta base `ortomosaicos/` para futuros archivos geoespaciales, ortomosaicos o panoramicas de apoyo operacional de la mina.
- Se movio el archivo maestro `20260524_AVA_DES_F1-F2_PCP.tif` a `ortomosaicos/`.
- Se genero una vista previa liviana `20260524_AVA_DES_F1-F2_PCP_preview.jpg` para visualizacion en Streamlit.
- Se agrego `pages/10_Ortomosaico_Vista_Mina.py` con selector de archivo, visualizacion interactiva Plotly, zoom, pan, reset de vista y texto referencial de apoyo operacional.
- Se modularizo la logica en `services/ortomosaico_service.py` y `ui/ortomosaico_ui.py`, dejando preparada la arquitectura para futuras capas de puntos, coordenadas, pozos, equipos y poligonos.
- No se modificaron calculos KPI, reportes, base de datos ni dashboard principal.

## v2.3.0 - Estabilizacion Biblioteca Tecnica Operacional
Fecha: 2026-05-25

- Se documento FASE 18 como Biblioteca Tecnica Operacional.
- Se agrego repositorio documental en `docs/` separado del historico operacional.
- Se incorporo la tabla SQLite `documentacion_tecnica` para metadata documental.
- Se agrego `services/documentation_service.py` para estructura documental, sincronizacion, filtros, metadata y lectura de archivos.
- Se agrego `pages/08_Biblioteca_Tecnica.py` con filtros documentales, tarjetas de documentos, descarga y visor PDF embebido.
- Se mantuvo SQLite como fuente principal del sistema, sin mezclar documentos tecnicos con reportes operacionales.
- Se congela FASE 19 como version estable de Biblioteca Tecnica.
- Se valido con `python -m compileall .`, `python -m pytest tests -v` y arranque Streamlit headless en puerto `8505`.
- Total de pruebas: 120 passed.
- Version de estabilizacion: `v2.3.0`.

## v2.2.0 - Estabilizacion posterior a acciones correctivas
Fecha: 2026-05-25

- Se consolidaron FASE 14, FASE 15 y FASE 16 como parte de la linea estable del sistema.
- Se agrego el modulo de Calidad de Datos con reglas defensivas, score ejecutivo y exportacion a Excel.
- Se agrego el modulo de Acciones Correctivas con persistencia SQLite, seguimiento de estado y derivacion desde observaciones.
- Se incorporaron nuevas tablas SQLite para calidad de datos, alertas inteligentes y acciones correctivas.
- Se mantuvo la arquitectura operativa basada en SQLite sin romper Excel, PDF, historial, auditoria ni machine learning.
- Se valido el estado del sistema con `compileall` y `pytest` en verde antes de la congelacion.
- Version sugerida de estabilizacion: `v2.2.0`.

## v2.1.0-dashboard-ejecutivo - Estabilizacion posterior al dashboard ejecutivo
Fecha: 2026-05-25

- Se marco FASE 12 como implementada con dashboard ejecutivo profesional, KPI cards y graficos Plotly.
- Se corrigio una key duplicada en `dashboard.py` para evitar conflicto de Streamlit.
- Se valido el estado de pruebas con `compileall` y `pytest` en verde.
- Se mantiene la arquitectura de SQLite, Excel, PDF, historial, auditoria y machine learning sin cambios funcionales.

## v2.0.0 - Refactor modular estable
Fecha: 2026-05-21

- Creacion de `schema.py`.
- Creacion de `pdf_report.py`.
- Creacion de `validation.py`.
- Creacion de `catalogs.py`.
- Creacion de `config.py`.
- Separacion de metricas en `metrics.py`.
- Normalizacion de `Utilización`.
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
