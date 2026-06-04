# Arquitectura Operacional

## Fuente oficial

La fuente oficial del sistema es `reportes_perforacion.db`.

`reportes_perforacion.xlsx` permanece como exportacion operativa, respaldo derivado e insumo de recuperacion manual. La lectura cotidiana de la aplicacion debe priorizar SQLite.

## Flujo operativo actual

`Streamlit -> validaciones -> SQLite -> exportacion Excel -> dashboard / PDF / alertas / calidad / acciones correctivas / biblioteca tecnica`

La escritura operativa confirma primero en SQLite. Si SQLite falla, el guardado no se considera exitoso. Excel puede fallar despues sin invalidar el guardado principal.

## Estructura de modulos

- `app_perforacion.py`: aplicacion Streamlit principal y orquestacion visual.
- `data.py`: normalizacion, lectura, guardado, anexado y wrappers de compatibilidad.
- `db.py`: persistencia SQLite y operaciones CRUD.
- `dashboard.py`: vistas operacionales y analiticas sobre `DataFrame`.
- `metrics.py`: calculos operacionales y KPI.
- `charts.py`: graficas del dashboard.
- `pdf_report.py`: generacion de PDF.
- `services/report_service.py`: payload, validaciones previas y ejecucion del guardado.
- `services/export_service.py`: exportacion Excel y respaldo del archivo.
- `services/alert_service.py`: reglas operacionales de alertas.
- `services/data_quality_service.py`: reglas defensivas de calidad de datos, score ejecutivo y resumen automatico.
- `services/corrective_actions_service.py`: registro, consulta y seguimiento de acciones correctivas.
- `services/documentation_service.py`: biblioteca tecnica, metadata documental, sincronizacion de `docs/` y lectura de archivos.
- `services/smart_alerts_service.py`: motor incremental de alertas inteligentes.
- `services/executive_service.py`: panel ejecutivo, salud operacional y rankings.
- `ui/`: secciones visuales del formulario, dashboard y mantenimiento.
- `pages/`: paginas multipagina de Streamlit.
- `validation/`: validaciones de formulario y reglas de negocio.

## Tablas SQLite principales

- `auditoria_ediciones`: trazabilidad de cambios sobre registros historicos.
- `alertas_inteligentes`: alertas automaticas persistidas por motor incremental.
- `alertas_inteligentes_control`: control de ultimo registro procesado y ejecucion.
- `acciones_correctivas`: seguimiento de acciones derivadas de alertas y calidad.
- `documentacion_tecnica`: metadata documental de la Biblioteca Tecnica Operacional.

## Biblioteca Tecnica

FASE 18 incorporo una biblioteca documental separada del historico operacional.

Componentes:

- pagina Streamlit `pages/09_Biblioteca_Tecnica.py`,
- servicio `services/documentation_service.py`,
- raiz documental `docs/`,
- tabla SQLite `documentacion_tecnica`.

Estructura base de `docs/`:

- `docs/manuales`: manuales de fabricante y material tecnico base.
- `docs/procedimientos`: procedimientos operacionales.
- `docs/seguridad`: documentos de seguridad y controles criticos.
- `docs/capacitaciones`: material de capacitacion, ART y difusiones.
- `docs/troubleshooting`: guias de diagnostico y solucion de fallas.

La tabla `documentacion_tecnica` contiene:

- `id`: identificador interno.
- `nombre`: nombre visible del documento.
- `categoria`: clasificacion documental.
- `fabricante`: fabricante asociado cuando aplica.
- `equipo_asociado`: equipo o flota relacionada.
- `version`: version documental.
- `fecha_documento`: fecha tecnica del documento.
- `tipo_documento`: PDF, Word, planilla, presentacion, texto o archivo.
- `palabras_clave`: terminos para busqueda documental.
- `criticidad`: Baja, Media, Alta o Critica.
- `autor_responsable`: responsable documental.
- `descripcion`: contexto operativo.
- `ruta_relativa`: ruta unica dentro de `docs/`.
- `extension`, `tamano_bytes`, `fecha_archivo`: metadata fisica del archivo.
- `created_at`, `updated_at`: trazabilidad de registro.

Indices documentales:

- `idx_documentacion_categoria`
- `idx_documentacion_fabricante`
- `idx_documentacion_equipo`
- `idx_documentacion_criticidad`

La pagina de Biblioteca Tecnica ofrece filtros por categoria, fabricante, equipo y criticidad; busqueda por palabras clave y metadata; tarjetas documentales; descarga; visor PDF embebido para `.pdf`; y previsualizacion de `.md` y `.txt`.

## Compatibilidad legacy temporal

El sistema mantiene compatibilidad temporal con rutas antiguas:

- `leer_reportes()` funciona como wrapper temporal sobre SQLite.
- `leer_reportes_excel_legacy()` existe para recuperacion manual.
- `ui/data_status.py` sigue siendo un panel de comparacion y mantenimiento SQLite vs Excel.

Estas rutas no deben interpretarse como el camino operativo principal.

## Fases estabilizadas

- FASE 14: Calidad de Datos.
- FASE 15: Score ejecutivo de calidad.
- FASE 16: Acciones Correctivas.
- FASE 17: estabilizacion posterior a acciones correctivas.
- FASE 18: Biblioteca Tecnica Operacional.
- FASE 19: estabilizacion y documentacion de Biblioteca Tecnica.

## FASE 19

Se congela la linea `v2.3.0` despues de incorporar la Biblioteca Tecnica.

Alcance:

- documentacion oficial actualizada,
- version `VERSION_2_3_0.txt`,
- respaldo estable en `backup/fase_19_biblioteca_tecnica_estable_YYYYMMDD_HHMMSS`,
- validacion de compilacion, tests y arranque Streamlit.

## Riesgos tecnicos actuales

- Excel sigue existiendo como artefacto operativo secundario, lo que exige mantener sincronizacion controlada.
- La compatibilidad legacy debe permanecer aislada para no reintroducir fallback automatico.
- Las paginas manuales de mantenimiento no deben confundirse con la ruta operativa principal.
- La Biblioteca Tecnica debe mantener rutas relativas dentro de `docs/` para evitar dependencias externas.

## Recomendacion de evolucion

1. Consolidar SQLite como unica fuente operativa.
2. Dejar Excel solo como exportacion y recuperacion manual.
3. Ampliar analitica de calidad y acciones correctivas.
4. Fortalecer alertas y seguimiento por prioridad.
5. Incorporar carga controlada de documentos tecnicos con revision de metadata.

