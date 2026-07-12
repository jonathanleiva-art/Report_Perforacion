# ANÁLISIS DEL SISTEMA v2 — Post Fase 1 y Fase 2
> Fecha: 2026-06-22
> Páginas analizadas: 22
> Objetivo: identificar siguiente ronda de optimización

---

## 1. RESUMEN EJECUTIVO

- Páginas que aportan directamente a los 4 objetivos: **10**
- Páginas secundarias/administrativas: **12**
- Páginas candidatas a fusión: **5 pares/grupos**
- Páginas candidatas a eliminación: **2**
- Servicios huérfanos detectados: **2** (`corrective_actions_service.py`, `documentation_service.py`)

**Diagnóstico general:** El núcleo operacional (registro, KPIs, alertas, planos, ortomosaico) está bien organizado. El peso muerto está concentrado en la franja administrativa: tres páginas de fuentes/importación Excel que se solapan funcionalmente (20, 21, 22), y dos páginas de alerta casi idénticas en concepto (06 y 24). El "Panel Ejecutivo" (08) y el "Dashboard Excel Operacional" (10) ofrecen vistas que ya existen parcialmente en otras páginas.

---

## 2. ANÁLISIS DE LAS 22 PÁGINAS

### [01] Registro Operacional (`pages/01_Registro_Operacional.py`)
- **Datos que muestra**: Formulario wizard de 4 pasos (identificación → producción + ubicación → horas → confirmación) y panel de turnos pendientes últimos 7 días con métricas de atraso
- **Servicios/módulos que usa**: `report_service` (ejecutar_guardado_reporte, validar_datos_para_guardado), `kpi_service` (calcular_kpi_operacional_productivo), `alert_service` (get_reportes_faltantes), `ui/forms_sections`, `data` (leer_reportes_sqlite, limpiar_cache_reportes)
- **Aporta a objetivos 1-4**: Sí (objetivo 1 — registro de turnos)
- **Duplica información de**: La página Inicio (`app_perforacion._render_inicio`) contiene el mismo formulario de registro pero en modo no-wizard. Son el mismo formulario con dos interfaces distintas.
- **Frecuencia de uso real**: Alta — el jefe de turno la usa 2 veces por turno (mínimo), una por turno día y una por turno noche
- **Recomendación**: `Mantener`
- **Justificación**: El modo wizard es la interfaz preferible para terreno (tablet). Duplica el formulario de Inicio pero se justifica como punto de acceso dedicado al registro operacional.

---

### [02] Dashboard Operacional (`pages/02_Dashboard_Operacional.py`)
- **Datos que muestra**: KPIs de flota, gráficos de disponibilidad/utilización/rendimiento, alertas operacionales, generación de PDF, imágenes de equipos; selección de fuente de datos
- **Servicios/módulos que usa**: `dashboard` (módulo core), `alert_service` (via `mostrar_alertas_operacionales`), `ui/filters`, `ui/pdf_section`, `ui/data_source`
- **Aporta a objetivos 1-4**: Sí (objetivo 2 — KPIs operacionales)
- **Duplica información de**: La página Inicio (`_render_inicio`) ejecuta exactamente el mismo `dashboard_view()` con los mismos parámetros. Esta página es un espejo funcional del inicio.
- **Frecuencia de uso real**: Alta — supervisores la consultarán cada turno para revisión rápida de KPIs
- **Recomendación**: `Mantener`
- **Justificación**: Aunque duplica el contenido del Inicio, su existencia como página dedicada permite que el inicio quede limpio como landing page con el formulario. La duplicación es aceptable si la página de Inicio se simplifica en el futuro.

---

### [03] Avance Operacional (`pages/03_Avance_Operacional.py`)
- **Datos que muestra**: Avance por banco/fase/malla: pozos perforados vs planificados, progreso en barra, mapa visual de pozos (scatter Plotly), desglose por tipo de perforación (Producción/Buffer/Precorte), tarjetas de equipos activos en malla, tendencia acumulada, ranking de operadores en la malla, resumen general de todas las mallas
- **Servicios/módulos que usa**: `db` (directamente via `avance_malla` y `mallas_plano`), `ui/formatting`
- **Aporta a objetivos 1-4**: Sí (objetivo 2 y 3 — KPIs y gestión de planos)
- **Duplica información de**: Parcialmente con `04_Gestion_Planos` (tab "Avance real vs planificado"), pero esta página está orientada a consumo de datos ya registrados mientras que la 04 gestiona el ingreso del plan. La sobreposición es en la visualización del avance.
- **Frecuencia de uso real**: Alta — supervisores la consultarán diariamente para controlar avance de malla
- **Recomendación**: `Mantener`
- **Justificación**: Vista operacional de avance de malla con gráficos específicos. Tiene lógica SQL propia y vistas que no existen en otras páginas (mapa scatter de pozos, ranking de operadores por malla).

---

### [04] Gestión Planos (`pages/04_Gestion_Planos.py`)
- **Datos que muestra**: 5 tabs: (1) carga de PDFs de planos, (2) lector PDF con clasificación de pozos, (3) plan de perforación con sectores + corrección de clasificación operacional + registro asistido de pozos, (4) avance real vs planificado por sector, (5) administración y auditoría de planos
- **Servicios/módulos que usa**: `malla_service` (14+ funciones), `malla_avance_service`, `clasificacion_operacional_service`, `enaex_pdf_extraction_service`, `db`, `ui/formatting`
- **Aporta a objetivos 1-4**: Sí (objetivo 3 — gestión de planos de pozos)
- **Duplica información de**: `03_Avance_Operacional` (vista de avance, solapamiento parcial en tab 4)
- **Frecuencia de uso real**: Media — se usa para cargar planos (evento puntual, 1 vez por malla) y para revisión semanal de avance
- **Recomendación**: `Mantener`
- **Justificación**: Es la página central del objetivo 3. Concentra toda la gestión de planos PDF, planes de perforación y seguimiento de sectores. La página más compleja del sistema con 5 tabs bien diferenciados.

---

### [05] Ortomosaico Vista Mina (`pages/05_Ortomosaico_Vista_Mina.py`)
- **Datos que muestra**: Imagen ortomosaico con zoom/pan Plotly, editor drag-and-drop de posición de equipos sobre el mosaico, dibujo de zonas de perforación (polígonos SVG), descarga de PNG con equipos marcados, visualización lado a lado con plano de perforación
- **Servicios/módulos que usa**: `ortomosaico_service` (listar archivos, obtener ortomosaico), `ui/ortomosaico_ui` (renderizar controles, construir figura), `ui/components`
- **Aporta a objetivos 1-4**: Sí (objetivo 4 — ortomosaico)
- **Duplica información de**: Ninguna
- **Frecuencia de uso real**: Media — supervisores y jefes de faena la consultan para posicionar equipos, principalmente al inicio del turno o al cambiar de sector
- **Recomendación**: `Mantener`
- **Justificación**: Único en su función. El editor fullscreen con JS embebido es sofisticado y cubre totalmente el objetivo 4.

---

### [06] Alertas Operacionales (`pages/06_Alertas_Operacionales.py`)
- **Datos que muestra**: (1) Turnos faltantes últimos 7 días con detalle por fecha/equipo/turno; (2) tabla paginada de alertas operacionales filtradas (disponibilidad 100% con mantención, utilización baja, rendimiento bajo, horas turno distintas de 12) consultadas directamente en SQLite
- **Servicios/módulos que usa**: `db` (consultar_alertas_operacionales_filtradas, obtener_valores_distintos_columna, contar_historial_filtrado), `catalog_service` (FLOTA_EQUIPOS)
- **Aporta a objetivos 1-4**: Parcial (objetivo 2 — KPIs, control de calidad de datos)
- **Duplica información de**: `24_Alertas_Registros` — ambas muestran turnos faltantes. La diferencia: 06 incluye también alertas de reglas operacionales, 24 está especializada solo en registros faltantes con interfaz más rica.
- **Frecuencia de uso real**: Media — supervisores la usan para detectar anomalías en los KPIs registrados. Los turnos faltantes son el punto de mayor uso.
- **Recomendación**: `Fusionar con 24_Alertas_Registros`
- **Justificación**: El panel de "turnos faltantes" de esta página y la página 24 hacen lo mismo desde fuentes diferentes pero con la misma intención. Fusionar permite tener una sola página de "Alertas" con tabs: Registros faltantes + Alertas operacionales.

---

### [07] Reportes PDF (`pages/07_Reportes_PDF.py`)
- **Datos que muestra**: Generación de PDF por rango de fechas/turno (via `ui/pdf_section`), tabla de PDFs ya generados con nombre/fecha modificación/tamaño
- **Servicios/módulos que usa**: `ui/pdf_section` (seccion_reporte_pdf), `ui/data_source`, `config` (REPORTS_PDF_DIR)
- **Aporta a objetivos 1-4**: Parcial (documentación operacional)
- **Duplica información de**: La sección PDF también está disponible en `02_Dashboard_Operacional` (a través de `dashboard_view` que llama a `seccion_reporte_pdf_fn`). Sin embargo, la lista de PDFs generados es exclusiva de esta página.
- **Frecuencia de uso real**: Baja — se genera PDF típicamente al cierre de semana o para informes. No es una tarea diaria de faena.
- **Recomendación**: `Mantener`
- **Justificación**: Aunque la generación de PDF está disponible en el dashboard, tener una página dedicada con el listado de PDFs generados y con filtros independientes es útil para el personal administrativo.

---

### [08] Panel Ejecutivo (`pages/08_Panel_Ejecutivo.py`)
- **Datos que muestra**: 8 KPIs agregados (metros, horas, disponibilidad, utilización, rendimiento, equipos activos, operadores), semáforo de salud operacional (índice 0-100), rankings (mejor rendimiento, menor utilización, mayor metraje por operador, causas de detención), tendencia semanal con line chart
- **Servicios/módulos que usa**: `executive_service` (consultar_panel_ejecutivo), `db` (obtener_valores_distintos_columna)
- **Aporta a objetivos 1-4**: Parcial (objetivo 2 — KPIs, vista gerencial)
- **Duplica información de**: `02_Dashboard_Operacional` (KPIs similares), `09_Analisis_Mensual` (rankings), `06_Alertas_Operacionales` (alertas). El "semáforo de salud" es único.
- **Frecuencia de uso real**: Baja — es una vista gerencial. En faena, los supervisores prefieren el dashboard operacional con más detalle. Un jefe de operaciones podría consultarla 1 vez por semana.
- **Recomendación**: `Fusionar con 02_Dashboard_Operacional`
- **Justificación**: El panel ejecutivo aporta el semáforo y los rankings que no están en el dashboard. En lugar de mantener dos páginas con KPIs similares, el dashboard podría tener un tab "Vista ejecutiva" con el semáforo, rankings y tendencia semanal.

---

### [09] Análisis Mensual (`pages/09_Analisis_Mensual.py`)
- **Datos que muestra**: KPIs mensuales (metros, horas, disponibilidad, utilización, rendimiento), diagnóstico automático textual, ranking de equipos y operadores del mes, gráficos de barras horizontales con Plotly; soporta fuente manual (SQLite) y ciclos Excel
- **Servicios/módulos que usa**: `monthly_service` (obtener_resumen/ranking_equipos/ranking_operadores_mensual), `ciclos_service` (equivalentes para ciclos), `ui/data_source`
- **Aporta a objetivos 1-4**: Parcial (objetivo 2 — KPIs agregados mensuales)
- **Duplica información de**: `08_Panel_Ejecutivo` (rankings similares), `10_Dashboard_Excel_Operacional` (rankings por equipo/operador desde Excel)
- **Frecuencia de uso real**: Baja — se consulta al cierre de mes para informes. No es herramienta de turno.
- **Recomendación**: `Mantener`
- **Justificación**: Es la única página que permite seleccionar un mes específico y año para análisis histórico. Los rankings mensuales son distintos a los rankings ejecutivos (que van por rango libre). Tiene valor para informes de gestión mensual.

---

### [10] Dashboard Excel Operacional (`pages/10_Dashboard_Excel_Operacional.py`)
- **Datos que muestra**: Selección de fuente Excel operacional importada, KPIs básicos (metros, equipos, operadores, horas), 4 gráficos Plotly (metros por equipo, metros por operador, metros por fecha, horas por tipo), tablas de registros/ranking equipos/ranking operadores
- **Servicios/módulos que usa**: `operational_excel_query_service` (listar_fuentes, cargar_registros, calcular_resumen, obtener_ranking)
- **Aporta a objetivos 1-4**: Parcial (objetivo 2 — KPIs desde Excel importado)
- **Duplica información de**: `09_Analisis_Mensual` (rankings similares desde otra fuente), `02_Dashboard_Operacional` (KPIs generales cuando la fuente es Excel)
- **Frecuencia de uso real**: Baja — solo útil cuando se trabaja con Excel importado operacional. Si el sistema trabaja principalmente con registros SQLite, esta página queda inactiva.
- **Recomendación**: `Convertir en sección de 20_Administrar_Fuentes_Excel`
- **Justificación**: Esta página visualiza datos de fuentes Excel importadas, lo cual es una extensión natural de "Administrar Fuentes Excel" que ya tiene un tab de "Operacional importado" con vistas similares. Unificar reduce navegación sin perder funcionalidad.

---

### [11] Alertas Inteligentes (`pages/11_Alertas_Inteligentes.py`)
- **Datos que muestra**: Resumen de alertas (total/pendientes/vistas/atendidas), botón para ejecutar motor incremental, tabla de alertas con causa/recomendación/criticidad/estado, acciones de estado (marcar como vista/atendida), detalle operativo con valor métrico y valor referencia
- **Servicios/módulos que usa**: `smart_alerts_service` (ejecutar_motor_alertas, obtener_alertas_inteligentes, resumen_alertas_inteligentes, marcar_alertas_estado), `db` (obtener_valores_distintos_columna)
- **Aporta a objetivos 1-4**: Parcial (objetivo 2 — análisis avanzado de KPIs)
- **Duplica información de**: `06_Alertas_Operacionales` (ambas muestran alertas operacionales, pero con motores diferentes: 06 evalúa reglas fijas en tiempo real, 11 tiene motor incremental persistente con estados)
- **Frecuencia de uso real**: Media — el motor debe ejecutarse periódicamente. En faena el supervisor lo revisa al inicio de cada turno para ver alertas pendientes.
- **Recomendación**: `Mantener`
- **Justificación**: El motor incremental con estados (pendiente/vista/atendida) y el historial persistente de alertas es funcionalmente distinto de las alertas en tiempo real de la página 06. No es duplicación funcional sino dos capas complementarias.

---

### [12] Calidad Datos (`pages/12_Calidad_Datos.py`)
- **Datos que muestra**: Score de calidad (0-100), estado del sistema (excelente/aceptable/observado/crítico), errores/advertencias/reglas no evaluadas, top 5 problemas, registros críticos priorizados, tabla de observaciones con regla/estado/recomendación, exportación a Excel formateado con 3 hojas
- **Servicios/módulos que usa**: `data_quality_service` (generar_resumen_ejecutivo_calidad), `db` (consultar_historial_filtrado, obtener_valores_distintos_columna)
- **Aporta a objetivos 1-4**: No directamente — es herramienta de QA
- **Duplica información de**: Ninguna (funcionalidad única)
- **Frecuencia de uso real**: Baja — se revisa cuando se sospecha de errores en datos o antes de generar informes. No es herramienta de turno.
- **Recomendación**: `Mantener`
- **Justificación**: Funcionalidad única de QA. El score de calidad y las reglas de validación son complementos esenciales para garantizar la integridad de los datos operacionales.

---

### [16] Auditoría Historial (`pages/16_Auditoria_Historial.py`)
- **Datos que muestra**: Historial operacional paginado con filtros SQL (fecha, turno, equipo, número, operador, banco, malla); audit log del sistema (CSV con eventos de guardado, edición y errores)
- **Servicios/módulos que usa**: `db` (consultar_historial_filtrado, contar_historial_filtrado, obtener_valores_distintos_columna), `audit.audit_log` (AUDIT_LOG_PATH)
- **Aporta a objetivos 1-4**: No directamente — trazabilidad y auditoría
- **Duplica información de**: `17_Edicion_Controlada_Auditoria` (ambas tienen filtros de búsqueda de historial muy similares)
- **Frecuencia de uso real**: Baja — uso puntual para auditorías o resolución de discrepancias. Solo admin.
- **Recomendación**: `Fusionar con 17_Edicion_Controlada_Auditoria`
- **Justificación**: La página 17 (Edición Controlada) ya tiene una tabla de resultados de búsqueda y una sección de auditoría del registro. Agregar el historial general y el audit log CSV como tabs adicionales en esa página elimina la duplicación de filtros y consolida toda la trazabilidad en un solo lugar. Ambas requieren admin=True.

---

### [17] Edición Controlada Auditoria (`pages/17_Edicion_Controlada_Auditoria.py`)
- **Datos que muestra**: Búsqueda filtrada de registros (fecha, turno, equipo, operador, malla), formulario de edición campo a campo con selectbox/number_input/text_input según tipo, auditoría del registro seleccionado (historial de cambios)
- **Servicios/módulos que usa**: `db` (consultar_registros_edicion, obtener_registro_por_id, actualizar_registro_auditado, leer_auditoria_ediciones, obtener_valores_distintos_columna), `catalog_service`, `schema` (NUMERIC_COLUMNS)
- **Aporta a objetivos 1-4**: No directamente — administración de datos
- **Duplica información de**: `25_Editar_Registro` — ambas permiten editar registros con motivo y auditoría. La diferencia: 17 es la interfaz original con formulario tradicional; 25 es más moderna con grupos colapsables, preview KPI en tiempo real y búsqueda integrada.
- **Frecuencia de uso real**: Baja — uso puntual para correcciones. Solo admin.
- **Recomendación**: `Fusionar con 25_Editar_Registro` (y absorber 16)
- **Justificación**: Las páginas 17 y 25 hacen exactamente lo mismo (editar un registro con auditoría). La 25 es más completa (recálculo KPI, sectores widget, búsqueda integrada). La 17 debería eliminarse conservando 25 como la interfaz definitiva, y absorbiendo el historial/audit log de la 16.

---

### [18] Respaldos Exportación (`pages/18_Respaldos_Exportacion.py`)
- **Datos que muestra**: Verificación de integridad (SQLite PRAGMA), respaldo manual (SQLite + Excel + PDF), exportaciones filtradas (datos filtrados, ciclos, auditoría), descarga de CONTRATO_DATOS.md, historial de respaldos de la carpeta backup/
- **Servicios/módulos que usa**: `backup_service` (verificar_integridad, generar_respaldo_manual, exportar_datos_filtrados_excel, exportar_auditoria_ediciones_excel, listar_respaldos, dataframe_a_excel_bytes), `ciclos_service` (leer_ciclos_operacional), `db`
- **Aporta a objetivos 1-4**: No directamente — continuidad operacional y resguardo
- **Duplica información de**: Ninguna
- **Frecuencia de uso real**: Baja — se usa al cierre de semana o cuando se requiere exportación. Solo admin.
- **Recomendación**: `Mantener`
- **Justificación**: Funcionalidad única y crítica para la continuidad operacional. Ninguna otra página tiene respaldo ni exportación filtrada.

---

### [19] Administración Operadores (`pages/19_Administracion_Operadores.py`)
- **Datos que muestra**: Lista de operadores registrados, lista de códigos de ciclos sin nombre asignado, formulario para asignar nombre a código, sincronización de operadores desde ciclos
- **Servicios/módulos que usa**: `operator_admin_service` (listar_operadores, listar_pendientes_ciclos, actualizar_operador, sincronizar_operadores_ciclos)
- **Aporta a objetivos 1-4**: No directamente — administración de catálogos
- **Duplica información de**: `23_Administracion_Catalogos` tiene un tab de operadores con funciones similares (listar, crear, desactivar)
- **Frecuencia de uso real**: Baja — se usa al importar nuevos ciclos Excel con códigos de operador no reconocidos. Solo admin.
- **Recomendación**: `Fusionar con 23_Administracion_Catalogos`
- **Justificación**: Administración de operadores es un caso especial del catálogo de operadores. Tener dos páginas para gestionar operadores (una para el catálogo maestro, otra para resolución de códigos de ciclos) genera confusión. Un tercer tab en "Administración Catálogos" llamado "Operadores de Ciclos" resolvería ambos casos.

---

### [20] Administrar Fuentes Excel (`pages/20_Administrar_Fuentes_Excel.py`)
- **Datos que muestra**: 4 tabs: (1) Importar Excel de ciclos, (2) gestión de fuentes de ciclos (activar/desactivar/eliminar), (3) visualización de fuentes operacionales importadas con preview de registros, (4) comparación de dos fuentes
- **Servicios/módulos que usa**: `ciclos_service` (importar_excel_ciclos, resumen_fuentes, actualizar_estado, eliminar_fuente, comparar_fuentes), `operational_excel_service` (resumen_fuentes_operacionales, leer_operacional_dashboard), `source_service` (actualizar_estado_fuente)
- **Aporta a objetivos 1-4**: No directamente — administración de fuentes de datos
- **Duplica información de**: `21_Fuentes_Datos` (listado y detalle de fuentes), `22_Importar_Excel` (importación con diagnóstico)
- **Frecuencia de uso real**: Baja — se usa cuando se importan nuevos ciclos Excel. Solo admin.
- **Recomendación**: `Fusionar con 21_Fuentes_Datos y 22_Importar_Excel` — crear una sola página "Gestión de Fuentes Excel"
- **Justificación**: Las páginas 20, 21 y 22 cubren el mismo flujo de trabajo: importar un Excel → diagnosticar → registrar fuente → administrar fuentes. Tener tres páginas separadas para este flujo lineal fragmenta la experiencia de usuario.

---

### [21] Fuentes Datos (`pages/21_Fuentes_Datos.py`)
- **Datos que muestra**: Tabla de todas las fuentes disponibles (enriquecidas con resumen de registros/metros/fechas), detalle de la fuente seleccionada con validación de soporte, recomendación de uso, orientación operacional
- **Servicios/módulos que usa**: `data_source_selector_service` (listar_fuentes_disponibles, obtener_fuente_seleccionable), `source_adapter_service` (validar_fuente_soportada, calcular_resumen_fuente_normalizado), `source_routing_helpers` (obtener_mensaje_orientacion)
- **Aporta a objetivos 1-4**: No directamente — informativa de configuración
- **Duplica información de**: `20_Administrar_Fuentes_Excel` (ambas listan fuentes con resumen)
- **Frecuencia de uso real**: Baja — es página informativa/diagnóstico. No genera acciones. Solo admin.
- **Recomendación**: `Fusionar con 20_Administrar_Fuentes_Excel`
- **Justificación**: Esta página es esencialmente un visor de estado de fuentes. Su contenido debe ser un tab "Estado de fuentes" dentro de la página consolidada de administración de fuentes.

---

### [22] Importar Excel (`pages/22_Importar_Excel.py`)
- **Datos que muestra**: Upload de Excel → diagnóstico previo (tipo de fuente, hojas, columnas reconocidas/faltantes, equipos/operadores detectados, metros estimados) → confirmación de fuente diagnosticada → importación controlada de fuentes previamente diagnosticadas
- **Servicios/módulos que usa**: `import_diagnostic_service` (diagnosticar_excel), `import_execution_service` (importar_fuente_diagnosticada), `source_service` (crear_fuente_datos, listar_fuentes_datos)
- **Aporta a objetivos 1-4**: No directamente — ingestión de datos
- **Duplica información de**: `20_Administrar_Fuentes_Excel` (tab "Importar")
- **Frecuencia de uso real**: Baja — evento puntual al recibir nuevos ciclos. Solo admin.
- **Recomendación**: `Fusionar con 20_Administrar_Fuentes_Excel`
- **Justificación**: El flujo de importación con diagnóstico de esta página complementa el flujo más directo de la página 20. Deben ser tabs secuenciales en la misma página: "Diagnosticar" → "Confirmar" → "Importar controlado".

---

### [23] Administración Catálogos (`pages/23_Administracion_Catalogos.py`)
- **Datos que muestra**: 2 tabs: (1) Equipos — listado, formulario crear equipo (código/nombre/modelo/tipo/estado), desactivar equipo; (2) Operadores — listado, formulario crear operador (código/nombre/empresa/cargo), desactivar operador
- **Servicios/módulos que usa**: `catalog_service` (listar_equipos_activos, crear_equipo, desactivar_equipo, listar_operadores_activos, crear_operador, desactivar_operador)
- **Aporta a objetivos 1-4**: No directamente — catálogos maestros
- **Duplica información de**: `19_Administracion_Operadores` (gestión de operadores)
- **Frecuencia de uso real**: Baja — se usa cuando ingresa un nuevo equipo a la flota o un nuevo operador. Solo admin.
- **Recomendación**: `Mantener` (absorber funcionalidad de 19)
- **Justificación**: Es el catálogo maestro central. Debe absorber la funcionalidad de administración de operadores de ciclos de la página 19.

---

### [24] Alertas Registros (`pages/24_Alertas_Registros.py`)
- **Datos que muestra**: Métricas de reportes faltantes (total, fechas afectadas, atraso máximo, equipos monitoreados), tarjetas por fecha con detalle de turnos y equipos faltantes agrupados por mes, filtro de período (7/14/30 días o rango personalizado)
- **Servicios/módulos que usa**: `alert_service` (get_reportes_faltantes, EQUIPOS_REPORTES_REQUERIDOS, TURNOS_REPORTES_REQUERIDOS)
- **Aporta a objetivos 1-4**: Parcial (objetivo 1 — control de cobertura de registro)
- **Duplica información de**: `06_Alertas_Operacionales` (panel de turnos faltantes) y `app_perforacion._render_inicio` (sidebar y panel de faltantes)
- **Frecuencia de uso real**: Alta — el supervisor la usará en cada turno para saber qué equipos no han reportado. Es el "¿quién falta?" del sistema.
- **Recomendación**: `Mantener` (y fusionar 06 en ella)
- **Justificación**: Esta página es la mejor implementación de "alertas de registros faltantes" del sistema. Tiene interfaz más rica (tarjetas por mes, filtros de período, métricas superiores) que el panel de la página 06. La 06 debe fusionarse aquí agregando un tab "Alertas operacionales" con las reglas KPI.

---

### [25] Editar Registro (`pages/25_Editar_Registro.py`)
- **Datos que muestra**: Buscador integrado (fecha desde/hasta, turno, equipo, operador), tabla de resultados con botón "Editar" por fila, formulario de edición agrupado en expanders colapsables (6 grupos), preview KPI en tiempo real recalculado, validación de duplicados al editar, motivo obligatorio, auditoría
- **Servicios/módulos que usa**: `db` (obtener_registro_por_id, actualizar_registro_auditado, limpiar_cache_consultas), `catalog_service` (FLOTA_EQUIPOS), `kpi_service` (calcular_kpi_operacional_productivo), `schema` (NUMERIC_COLUMNS), `ui/sectores_widget`
- **Aporta a objetivos 1-4**: No directamente — corrección de datos
- **Duplica información de**: `17_Edicion_Controlada_Auditoria` — misma funcionalidad, interfaz más avanzada
- **Frecuencia de uso real**: Media — se usa cuando el operador comete un error en el registro. Puede ocurrir 1-3 veces por semana.
- **Recomendación**: `Mantener` (reemplazar 17)
- **Justificación**: Es la implementación más completa de edición de registros: tiene preview KPI en tiempo real, sectores widget, búsqueda integrada con tabla y botón por fila. Debe reemplazar a la página 17.

---

## 3. SERVICIOS EN `services/`

### alert_service.py
- **Propósito**: Cálculo de reportes faltantes por equipo/turno/fecha; evaluación de alertas operacionales en SQLite
- **Importado por**: `app_perforacion.py`, `pages/01_Registro_Operacional.py`, `pages/24_Alertas_Registros.py`, `tests/test_reportes_faltantes_service.py`
- **Estado**: Activo

### backup_service.py
- **Propósito**: Respaldo manual de SQLite/Excel/PDF, verificación de integridad, exportación a Excel filtrada, historial de respaldos
- **Importado por**: `pages/18_Respaldos_Exportacion.py`, `tests/test_backup_service.py`
- **Estado**: Activo

### catalog_service.py
- **Propósito**: Catálogo maestro de equipos y operadores; constantes FLOTA_EQUIPOS; CRUD de equipos y operadores activos
- **Importado por**: `app_perforacion.py`, `pages/06_Alertas_Operacionales.py`, `pages/17_Edicion_Controlada_Auditoria.py`, `pages/23_Administracion_Catalogos.py`, `pages/25_Editar_Registro.py`, `tests/test_catalog_service.py`, `tests/test_catalog_flow_integration.py`
- **Estado**: Activo

### ciclos_service.py
- **Propósito**: Importación de Excel de ciclos de perforación, gestión de fuentes, comparación de fuentes, ranking mensual de ciclos
- **Importado por**: `pages/09_Analisis_Mensual.py`, `pages/18_Respaldos_Exportacion.py`, `pages/20_Administrar_Fuentes_Excel.py`, `tests/test_ciclos_service.py`, `tests/test_data_source_selector_service.py`, `tests/test_operational_excel_query_service.py`
- **Estado**: Activo

### clasificacion_operacional_service.py
- **Propósito**: Clasificación y corrección de tipo de sector en registros operacionales; resumen de clasificación; TIPOS_SECTOR
- **Importado por**: `pages/04_Gestion_Planos.py`, `tests/test_clasificacion_operacional_service.py`
- **Estado**: Activo

### corrective_actions_service.py
- **Propósito**: CRUD de acciones correctivas persistidas en tabla `acciones_correctivas`; gestión de estados y prioridades
- **Importado por**: `tests/test_corrective_actions_service.py` (solo tests)
- **Estado**: Huérfano

### data_quality_service.py
- **Propósito**: Generación de resumen ejecutivo de calidad de datos con score, reglas de validación, errores/advertencias, top problemas y registros críticos
- **Importado por**: `pages/12_Calidad_Datos.py`, `tests/test_data_quality_service.py`
- **Estado**: Activo

### data_source_selector_service.py
- **Propósito**: Listado y selección de fuentes de datos disponibles (ciclos y operacional Excel); abstracción de fuente seleccionable
- **Importado por**: `pages/21_Fuentes_Datos.py`, `tests/test_data_source_selector_service.py`, `tests/test_source_routing_helpers.py`
- **Estado**: Activo

### documentation_service.py
- **Propósito**: Gestión de biblioteca técnica de documentos (PDFs, Markdown, etc.); CRUD en tablas `documentacion_tecnica` y `biblioteca_documentos`
- **Importado por**: `tests/test_biblioteca_tecnica_service.py`, `tests/test_documentation_service.py` (solo tests)
- **Estado**: Huérfano

### enaex_pdf_extraction_service.py
- **Propósito**: Extracción de datos de PDFs de planos Enaex (fase, banco, malla, sectores con pozos y metros)
- **Importado por**: `pages/04_Gestion_Planos.py`, `tests/test_enaex_pdf_extraction_service.py`
- **Estado**: Activo

### executive_service.py
- **Propósito**: Consulta de panel ejecutivo: KPIs agregados, semáforo de salud, rankings, tendencia semanal, alertas ejecutivas
- **Importado por**: `pages/08_Panel_Ejecutivo.py`, `tests/test_executive_service.py`
- **Estado**: Activo

### export_service.py
- **Propósito**: Exportación y respaldo de Excel operacional con formato openpyxl (cabeceras, colores, anchos)
- **Importado por**: `db.py` (actualizar_registro_auditado), `data.py` (leer_reportes_sqlite)
- **Estado**: Activo (usado por módulos core)

### import_diagnostic_service.py
- **Propósito**: Diagnóstico previo de archivos Excel: detección de tipo de fuente, columnas reconocidas/faltantes, equipos y operadores detectados
- **Importado por**: `pages/22_Importar_Excel.py`, `tests/test_import_diagnostic_service.py`, `tests/test_import_excel_page.py`, `tests/test_import_execution_service.py`, `tests/test_operational_excel_import_from_source.py`
- **Estado**: Activo

### import_execution_service.py
- **Propósito**: Importación controlada de fuentes previamente diagnosticadas; delegación al importador correspondiente según tipo de fuente
- **Importado por**: `pages/22_Importar_Excel.py`, `tests/test_import_execution_service.py`, `tests/test_operational_excel_import_from_source.py`
- **Estado**: Activo

### kpi_service.py
- **Propósito**: Cálculo de KPIs operacionales (disponibilidad, utilización, rendimiento); estado operacional de equipo; resumen de equipos; normalización de columnas
- **Importado por**: `app_perforacion.py`, `pages/01_Registro_Operacional.py`, `pages/25_Editar_Registro.py`, `tests/*` (múltiples)
- **Estado**: Activo

### malla_avance_service.py
- **Propósito**: Cálculo de avance real vs planificado por plan y sector; cruce de registros operacionales con sectores planificados
- **Importado por**: `pages/04_Gestion_Planos.py`, `tests/test_malla_avance_service.py`
- **Estado**: Activo

### malla_service.py
- **Propósito**: CRUD completo de planos de malla, pozos de control, planes de perforación y sectores; auditoría de planos y sectores
- **Importado por**: `pages/04_Gestion_Planos.py`, `tests/*` (múltiples tests de malla)
- **Estado**: Activo

### monthly_service.py
- **Propósito**: Resumen mensual de KPIs, ranking de equipos y operadores por mes desde registros manuales SQLite
- **Importado por**: `pages/09_Analisis_Mensual.py`, `tests/test_monthly_service.py`
- **Estado**: Activo

### operational_excel_query_service.py
- **Propósito**: Consultas de registros operacionales importados desde Excel: listado de fuentes, resumen KPI, rankings por equipo/operador
- **Importado por**: `pages/10_Dashboard_Excel_Operacional.py`, `tests/test_operational_excel_query_service.py`
- **Estado**: Activo (pero asociado a página candidata a fusión)

### operational_excel_service.py
- **Propósito**: Importación y gestión de Excel operacional como fuente; resumen de fuentes operacionales; lectura de registros para dashboard
- **Importado por**: `pages/20_Administrar_Fuentes_Excel.py`, `tests/*` (múltiples)
- **Estado**: Activo

### operator_admin_service.py
- **Propósito**: Asignación de nombres a códigos de operadores detectados en ciclos; sincronización; listado de pendientes
- **Importado por**: `pages/19_Administracion_Operadores.py`
- **Estado**: Activo (pero asociado a página candidata a fusión)

### ortomosaico_service.py
- **Propósito**: Listado de archivos de ortomosaico disponibles; carga y preparación del ortomosaico (ruta maestra + preview)
- **Importado por**: `pages/05_Ortomosaico_Vista_Mina.py`
- **Estado**: Activo

### report_service.py
- **Propósito**: Construcción del payload de registro, validación de datos para guardado, ejecución del guardado (SQLite + Excel)
- **Importado por**: `app_perforacion.py`, `pages/01_Registro_Operacional.py`, `tests/*` (múltiples)
- **Estado**: Activo

### smart_alerts_service.py
- **Propósito**: Motor incremental de alertas inteligentes (disponibilidad, utilización, rendimiento, avería), gestión de estados, resumen de alertas
- **Importado por**: `pages/11_Alertas_Inteligentes.py`, `tests/test_smart_alerts_service.py`
- **Estado**: Activo

### source_adapter_service.py
- **Propósito**: Abstracción de adaptador de fuente; validación de soporte; cálculo de resumen normalizado independiente del tipo de fuente
- **Importado por**: `pages/21_Fuentes_Datos.py`, `tests/*`
- **Estado**: Activo

### source_routing_helpers.py
- **Propósito**: Mensajes de orientación operacional según tipo de fuente y nivel de soporte
- **Importado por**: `pages/21_Fuentes_Datos.py`, `tests/test_source_routing_helpers.py`
- **Estado**: Activo

### source_service.py
- **Propósito**: CRUD de fuentes de datos en tabla `fuentes_datos`; listar, crear, actualizar estado, incluir/excluir eliminadas
- **Importado por**: `pages/20_Administrar_Fuentes_Excel.py`, `pages/22_Importar_Excel.py`, `tests/*`
- **Estado**: Activo

---

## 4. SERVICIOS HUÉRFANOS DETECTADOS

### corrective_actions_service.py
- **Por qué es huérfano**: No es importado por ninguna de las 22 páginas activas ni por los módulos core (`app_perforacion.py`, `dashboard.py`, `db.py`, `pdf_report.py`). Solo lo importa `tests/test_corrective_actions_service.py`.
- **Funcionalidad**: CRUD de tabla `acciones_correctivas` con estados (pendiente/en proceso/cerrada), prioridades (baja/media/alta/crítica) y fecha de compromiso. Fue diseñado para un módulo de gestión de acciones correctivas que nunca se integró al sistema.
- **Recomendación**: **Eliminar** el servicio y su test asociado (`test_corrective_actions_service.py`). Si en el futuro se necesita un módulo de acciones correctivas, crearlo desde cero con el contexto actualizado. La tabla SQLite `acciones_correctivas` puede eliminarse del schema también.

### documentation_service.py
- **Por qué es huérfano**: No es importado por ninguna de las 22 páginas activas ni por los módulos core. Solo lo importan `tests/test_biblioteca_tecnica_service.py` y `tests/test_documentation_service.py`.
- **Funcionalidad**: Gestión de biblioteca técnica de documentos (PDFs de procedimientos, manuales de fabricante, ARTs, etc.) con tablas `documentacion_tecnica` y `biblioteca_documentos`. Fue diseñado para un módulo de biblioteca técnica que no se llegó a exponer como página.
- **Recomendación**: **Mantener como utilidad latente** pero eliminar los tests si no hay plan de integración a corto plazo. Tiene valor potencial para una futura página de "Biblioteca Técnica" que centralice manuales de equipos y procedimientos operacionales. Alternativamente, **eliminar** si no está en el roadmap de las próximas 3 fases.

---

## 5. MAPA DE DEPENDENCIAS (páginas → servicios)

| Página | kpi | alert | catalog | report | smart_alerts | monthly | executive | otros |
|--------|-----|-------|---------|--------|--------------|---------|-----------|-------|
| 01 Registro | ✓ | ✓ | - | ✓ | - | - | - | data, forms_sections |
| 02 Dashboard | - | ✓ | - | - | - | - | - | dashboard, pdf_section, data_source |
| 03 Avance | - | - | - | - | - | - | - | db (directo), formatting |
| 04 Gestión Planos | - | - | - | - | - | - | - | malla_service, malla_avance, clasificacion_op, enaex_pdf |
| 05 Ortomosaico | - | - | - | - | - | - | - | ortomosaico_service, ortomosaico_ui |
| 06 Alertas Op. | - | - | ✓ | - | - | - | - | db (directo) |
| 07 Reportes PDF | - | - | - | - | - | - | - | pdf_section, data_source |
| 08 Panel Ejecutivo | - | - | - | - | - | - | ✓ | db |
| 09 Análisis Mensual | - | - | - | - | - | ✓ | - | ciclos_service |
| 10 Dashboard Excel | - | - | - | - | - | - | - | operational_excel_query |
| 11 Alertas Inteligentes | - | - | - | - | ✓ | - | - | db |
| 12 Calidad Datos | - | - | - | - | - | - | - | data_quality_service, db |
| 16 Auditoría Historial | - | - | - | - | - | - | - | db, audit_log |
| 17 Edición Controlada | - | - | ✓ | - | - | - | - | db, schema |
| 18 Respaldos | - | - | - | - | - | - | - | backup_service, ciclos_service |
| 19 Admin Operadores | - | - | - | - | - | - | - | operator_admin_service |
| 20 Admin Fuentes | - | - | - | - | - | - | - | ciclos_service, operational_excel, source_service |
| 21 Fuentes Datos | - | - | - | - | - | - | - | data_source_selector, source_adapter, source_routing |
| 22 Importar Excel | - | - | - | - | - | - | - | import_diagnostic, import_execution, source_service |
| 23 Admin Catálogos | - | - | ✓ | - | - | - | - | catalog_service |
| 24 Alertas Registros | - | ✓ | - | - | - | - | - | alert_service |
| 25 Editar Registro | ✓ | - | ✓ | - | - | - | - | db, schema, sectores_widget |

---

## 6. PLAN DE ACCIÓN PRIORIZADO

### Prioridad ALTA (impacto inmediato, ≤ 2 horas)

#### Acción 1: Eliminar servicios huérfanos y sus tests
- **Páginas afectadas**: Ninguna (no hay páginas que los usen)
- **Archivos a eliminar**: `services/corrective_actions_service.py`, `tests/test_corrective_actions_service.py`, `tests/test_biblioteca_tecnica_service.py`, `tests/test_documentation_service.py`
- **Acción opcional**: Evaluar `services/documentation_service.py` — mantener si hay roadmap, eliminar si no
- **Beneficio concreto**: Reduce la base de código en ~500-700 líneas de código muerto. Elimina 2-4 tests que dan falsa sensación de cobertura pero no cubren funcionalidad activa. El `__init__.py` de services puede necesitar actualización.

#### Acción 2: Eliminar página 17 (Edición Controlada) — reemplazada por 25
- **Páginas afectadas**: `17_Edicion_Controlada_Auditoria.py` → eliminar; `25_Editar_Registro.py` → mantener
- **Cambio en navegación**: Remover `pages/17_Edicion_Controlada_Auditoria.py` del `st.navigation` en `app_perforacion.py` (línea 749)
- **Beneficio concreto**: Elimina ~360 líneas de código duplicado. La página 25 tiene todas las funcionalidades de la 17 más recálculo KPI, preview en tiempo real y búsqueda integrada. El usuario no pierde ninguna capacidad.

#### Acción 3: Mover historial/audit log (página 16) a la página 25
- **Páginas afectadas**: `16_Auditoria_Historial.py` → fusionar en 25; `25_Editar_Registro.py` → agregar tab "Historial"
- **Estrategia**: Agregar 2 tabs a la página 25: "Editar registro" (actual) + "Historial operacional" (tabla paginada de 16) + "Audit log" (CSV de 16)
- **Beneficio concreto**: Consolida toda la trazabilidad en un solo lugar. Elimina ~157 líneas. La página 16 solo requiere acceso admin=True igual que 25.

---

### Prioridad MEDIA (1-4 horas)

#### Acción 4: Fusionar páginas 06 y 24 en una sola "Alertas" con tabs
- **Páginas afectadas**: `06_Alertas_Operacionales.py` + `24_Alertas_Registros.py`
- **Estrategia**: Convertir la página 24 (mejor implementación) en la página "Alertas" con 2 tabs:
  - Tab "Registros faltantes" (contenido actual de 24, con filtros de período)
  - Tab "Alertas operacionales" (contenido actual de 06, con las 4 reglas KPI paginadas)
- **Cambio en navegación**: Remover la entrada de 06 del menú, mantener 24 renombrada como "Alertas"
- **Beneficio concreto**: Elimina ~237 líneas de la página 06. El usuario tiene un único punto de acceso a todas las alertas del sistema. Reduce de 6 a 5 ítems en la sección "Operacional" del menú.

#### Acción 5: Fusionar páginas 20, 21 y 22 en "Gestión de Fuentes Excel"
- **Páginas afectadas**: `20_Administrar_Fuentes_Excel.py`, `21_Fuentes_Datos.py`, `22_Importar_Excel.py`
- **Estrategia**: Crear una sola página con 5 tabs secuenciales:
  1. "Diagnóstico" (contenido de 22 — upload + diagnosticar)
  2. "Confirmar e importar" (contenido de 22 — sección de importación controlada)
  3. "Fuentes ciclos" (contenido de 20 — tab Fuentes)
  4. "Fuentes operacionales" (contenido de 20 — tab Operacional importado + tab Comparar + tab Importar ciclos)
  5. "Estado de fuentes" (contenido de 21)
- **Beneficio concreto**: Reduce de 3 a 1 página administrativa. Elimina ~600 líneas de código redundante de navegación/filtros duplicados. El flujo "importar Excel" queda en un solo lugar lógico.

#### Acción 6: Fusionar página 19 como tab en página 23
- **Páginas afectadas**: `19_Administracion_Operadores.py` → fusionar en 23
- **Estrategia**: Agregar un tercer tab "Operadores de Ciclos" a la página 23 con el contenido de la 19 (lista de pendientes, asignación de nombre a código, sincronización)
- **Beneficio concreto**: Elimina ~79 líneas. Todo el catálogo de entidades (equipos + operadores maestro + operadores de ciclos) queda en un solo lugar.

---

### Prioridad BAJA (refactorizaciones mayores, > 4 horas)

#### Acción 7: Fusionar Panel Ejecutivo (08) en Dashboard Operacional (02)
- **Páginas afectadas**: `08_Panel_Ejecutivo.py` → convertir en tab de 02
- **Estrategia**: Agregar un tab "Vista Ejecutiva" al dashboard con el semáforo de salud, rankings y tendencia semanal. Requiere refactorizar `dashboard.py` para aceptar un tab adicional o crear un componente embebible desde `executive_service`.
- **Riesgo**: Medio — `dashboard.py` es un módulo core que se usa en 2 páginas (Inicio y 02). Modificarlo requiere tests cuidadosos.
- **Beneficio concreto**: Reduce de 3 a 2 páginas en la sección "Análisis". El executive_service queda con un solo consumidor.

#### Acción 8: Refactorizar página Inicio para evitar duplicación de formulario
- **Páginas afectadas**: `app_perforacion._render_inicio` (página de inicio), `01_Registro_Operacional.py`
- **Estrategia**: En la página de Inicio, reemplazar el expander con el formulario de registro por un enlace/botón que redirija a la página 01. Convertir el Inicio en un verdadero "home" con KPIs del día, panel de faltantes y acceso rápido.
- **Riesgo**: Medio — implica cambiar el comportamiento del inicio que actualmente sirve como landing + formulario.
- **Beneficio concreto**: Elimina la duplicación de la lógica de formulario entre `app_perforacion.formulario_registro()` y `pages/01_Registro_Operacional._formulario_wizard()`. Reduce ~400 líneas duplicadas.

#### Acción 9: Consolidar Dashboard Excel Operacional (10) en Administrar Fuentes (20)
- **Páginas afectadas**: `10_Dashboard_Excel_Operacional.py` → mover como tab en la página consolidada de fuentes
- **Estrategia**: Dentro de la acción 5, el tab "Fuentes operacionales" puede incluir el dashboard de KPIs de la página 10 como sub-sección debajo de la tabla de registros. Los gráficos de metros por equipo/operador/fecha ya existen en la página 10 y pueden reutilizarse.
- **Beneficio concreto**: Elimina ~240 líneas. Reduce de 3 a 2 páginas en la sección "Análisis" del menú.

---

## 7. CANDIDATOS A FUSIÓN DETALLADOS

### Fusión 1: [06 Alertas Operacionales] + [24 Alertas Registros] → "Alertas"

- **Justificación**: Ambas páginas se enfocan en detectar problemas en los registros operacionales. La 24 detecta ausencias (registros faltantes), la 06 detecta anomalías en los KPIs registrados. Son dos capas del mismo concepto de "alerta operacional".
- **Datos en común**: Ambas leen de la misma base (registros_perforacion), ambas usan `alert_service`, ambas muestran información de turnos faltantes (la 06 además tiene un panel propio de faltantes que duplica a la 24).
- **Estrategia de fusión**: Tabs en la página 24 (que es la más completa):
  - Tab "Registros faltantes" (actual de 24)
  - Tab "Alertas KPI" (alertas de disponibilidad/utilización/rendimiento de la 06, con sus filtros de sidebar)
- **Riesgo**: Bajo — los componentes son independientes y los filtros de sidebar no colisionan si se usan keys distintas
- **Ahorro estimado**: ~237 líneas de código, 1 página menos en navegación, eliminación del panel de faltantes duplicado en 06

### Fusión 2: [16 Auditoría Historial] + [17 Edición Controlada] → absorbidas por [25 Editar Registro]

- **Justificación**: Las tres páginas trabajan sobre los registros históricos de la BD. La 25 ya tiene búsqueda + edición + vista de auditoría del registro. La 16 agrega el historial general y el audit log del sistema.
- **Datos en común**: Todas consultan `registros_perforacion` con filtros similares (fecha, turno, equipo, operador). Ambas 16 y 17 tienen código de filtros SQL casi idéntico (~70 líneas).
- **Estrategia de fusión**: Agregar 2 tabs a la página 25:
  - Tab "Editar" (actual de 25)
  - Tab "Historial" (tabla paginada de 16 con sus filtros)
  - Tab "Audit log" (CSV viewer de 16)
  Eliminar páginas 16 y 17 completamente.
- **Riesgo**: Bajo — los componentes son independientes. Solo hay que asegurarse que la página 25 mantenga `requerir_acceso()` sin admin=True mientras que los tabs de historial y audit log requieran admin=True internamente.
- **Ahorro estimado**: ~517 líneas de código (360 de la 17 + 157 de la 16), 2 páginas menos en navegación

### Fusión 3: [19 Admin Operadores] → tab en [23 Admin Catálogos]

- **Justificación**: Los operadores de ciclos son un subconjunto del catálogo de operadores. La distinción entre "operadores del sistema" (23) y "operadores de ciclos Excel" (19) no es natural para el usuario.
- **Datos en común**: Ambas listan operadores y permiten agregar/modificar. La diferencia es que 19 trabaja con `operator_admin_service` (resolución de códigos de ciclos) mientras que 23 usa `catalog_service` (catálogo maestro).
- **Estrategia de fusión**: Agregar tab "Operadores Ciclos" a la página 23 con el contenido íntegro de la 19 (botón sincronizar, tabla pendientes, tabla registrados, formulario asignación). Los dos servicios son independientes y no hay conflicto.
- **Riesgo**: Bajo — es adición de tab, no reescritura
- **Ahorro estimado**: ~79 líneas de código, 1 página menos en navegación

### Fusión 4: [20 Admin Fuentes] + [21 Fuentes Datos] + [22 Importar Excel] → "Gestión de Fuentes"

- **Justificación**: Las tres páginas forman un flujo lineal: diagnosticar un Excel (22) → confirmarlo como fuente (22) → verlo en el listado (21) → administrarlo (20). Tener el flujo partido en 3 páginas obliga al usuario a navegar entre ellas.
- **Datos en común**: Las tres trabajan con fuentes de datos (tabla `fuentes_datos`). Las tres usan `source_service` directa o indirectamente. Los filtros y selectbox de fuente se repiten en las tres.
- **Estrategia de fusión**: Una sola página con tabs secuenciales (ver Acción 5 del plan). La clave es que el flujo vaya de izquierda a derecha: Diagnosticar → Confirmar → Administrar → Estado.
- **Riesgo**: Medio — hay que cuidar que los `session_state` keys no colisionen entre tabs. Se recomienda usar prefijos por tab.
- **Ahorro estimado**: ~400 líneas de código redundante (navegación, filtros duplicados, imports repetidos), 2 páginas menos en navegación

### Fusión 5: [08 Panel Ejecutivo] → tab en [02 Dashboard Operacional]

- **Justificación**: El panel ejecutivo es una "vista resumida" del dashboard para jefatura. El dashboard operacional ya existe para los supervisores. Tener dos páginas distintas para el mismo conjunto de datos (diferenciadas solo por nivel de agregación) fragmenta la información.
- **Datos en común**: Ambas leen de `registros_perforacion` filtrados por fecha/turno/equipo/operador. Los KPIs del panel ejecutivo son subconjunto de los del dashboard.
- **Estrategia de fusión**: Agregar un tab "Vista Ejecutiva" al dashboard con el contenido de `executive_service`: semáforo de salud, rankings y tendencia semanal. Los filtros del sidebar ya existen en el dashboard.
- **Riesgo**: Medio — el dashboard usa el módulo `dashboard.py` que tiene su propia arquitectura. Agregar el executive como tab requiere refactorizar la función `dashboard()` para que acepte el contexto de tabs de Streamlit, o llamar a `executive_service` directamente desde la página 02.
- **Ahorro estimado**: ~187 líneas de código de la página 08, 1 página menos en la sección "Análisis"
