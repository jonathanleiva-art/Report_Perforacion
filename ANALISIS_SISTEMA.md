# ANÁLISIS DEL SISTEMA — Report Perforación
**Fecha:** 2026-06-19  
**Analista:** Claude Sonnet 4.6 (análisis automático)  
**Proyecto:** Sistema de reportería operacional de perforación minera  
**Directorio raíz:** `c:\Python_Proyectos\Report_Perforacion`

---

## RESUMEN EJECUTIVO

El sistema tiene **4 objetivos de negocio**:
1. Registrar turnos de perforación minera (Día/Noche)
2. Calcular KPIs: disponibilidad, utilización, rendimiento m/h
3. Gestionar planos de pozos (bancos, fases, mallas, sectores)
4. Visualizar flota en ortomosaico

El estado actual muestra un proyecto funcional pero con **deuda técnica significativa**: duplicaciones de código entre 3-4 archivos, un archivo `dashboard.py` de 2067 líneas que actúa como módulo-dios, módulos de baja relevancia operacional que consumen mantenimiento (ML, Biblioteca Técnica, Acciones Correctivas), y código de debug que quedó en producción.

### Hallazgos críticos:
- **3 conjuntos de funciones duplicadas** entre `app_perforacion.py`, `dashboard.py` y `pdf_report.py`
- **`dashboard.py` tiene 2067 líneas** — viola el principio de responsabilidad única
- **8 páginas de baja frecuencia** que no aportan a los 4 objetivos principales
- **Código DEBUG activo en producción** (bloques try/except con st.error() en páginas 01 y app_perforacion.py)
- **Lista de flota hardcodeada en 4 lugares distintos** sin usar la constante centralizada de `utils.py`
- **`_limpiar_entero()` duplicado** entre `db.py` y `utils.py`

---

## SECCIÓN 1: ANÁLISIS DE PÁGINAS (26 páginas)

### 1.1 Grupo Operacional — Alta frecuencia de uso

#### 01_Registro_Operacional.py (~400 líneas)
- **Función:** Formulario de ingreso de turnos. Modo normal + modo wizard (tablet).
- **Frecuencia:** Alta — uso diario operacional.
- **Dependencias clave:** `app_perforacion.formulario_registro()`, `ui.forms_sections`, `services.report_service`, `services.kpi_service`.
- **Problema encontrado (L85-94):** Bloque `# ── DEBUG TEMPORAL ──` activo con `app.st.error(f"⚠️ DEBUG — error en render_ubicacion_condiciones (wizard):\n\n```\n{_traceback.format_exc()}\n```")`. Este código debería eliminarse o convertirse en logging silencioso.
- **Problema encontrado:** Importa `app_perforacion as app` y llama a `app.st` — esto crea un acoplamiento rígido a `app_perforacion.py` como proxy de `streamlit`.
- **Recomendación:** Mantener. Eliminar bloque DEBUG en líneas 86-94.

#### 02_Dashboard_Operacional.py (~55 líneas)
- **Función:** Punto de entrada al dashboard principal, delega todo a `dashboard.dashboard()`.
- **Frecuencia:** Alta — primera página que abre el operador.
- **Problema encontrado:** Pasa 11 funciones como parámetros a `dashboard_view()`, incluyendo `color_estado_operacional_fn`, `columnas_horas_turno_fn`, `etiqueta_hora_fn` — estas deberían importarse directamente en `dashboard.py` en lugar de inyectarse.
- **Recomendación:** Mantener, pero simplificar la firma de `dashboard()`.

#### 03_Avance_Operacional.py (~986 líneas)
- **Función:** Seguimiento de avance por banco/fase/malla desde tabla `avance_malla`.
- **Frecuencia:** Alta — objetivo 3 (gestión de planos).
- **Problema encontrado:** Tiene SQL directo en la página (`db.conectar_db()` llamado en múltiples funciones locales) sin pasar por una capa de servicio. Funciones como `obtener_mallas_disponibles()`, `obtener_detalle_malla()`, `obtener_planificado()`, `obtener_tendencia_malla()` deberían estar en un servicio.
- **Problema encontrado:** `extraer_datos_plano_pdf()` (L156-232) es una función de 76 líneas que duplica parcialmente la funcionalidad de `services.enaex_pdf_extraction_service`.
- **Recomendación:** Mantener. Extraer SQL a un servicio. Eliminar `extraer_datos_plano_pdf()` y usar `enaex_pdf_extraction_service`.

#### 04_Gestion_Planos.py (~1318 líneas)
- **Función:** Carga, lectura y análisis de planos PDF; control de planes y sectores; OCR de pozos.
- **Frecuencia:** Media — uso al crear un nuevo plan de perforación.
- **Problema encontrado:** Archivo de 1318 líneas con 6+ subsistemas embebidos: carga de planos, lector PDF OCR, control planes/sectores, avance real vs planificado, registro asistido, generación Excel. Debería dividirse.
- **Problema encontrado:** `_generar_excel_pozos()` (L1077-1152) implementa generación Excel compleja con openpyxl directamente en la página.
- **Recomendación:** Mantener el módulo pero dividir en sub-tabs; extraer `_generar_excel_pozos()` a `services/export_service.py`.

#### 05_Ortomosaico_Vista_Mina.py (~1148 líneas)
- **Función:** Visualización ortomosaico con editor drag-and-drop de equipos y zonas.
- **Frecuencia:** Baja-Media — objetivo 4 (ortomosaico).
- **Problema encontrado:** Contiene ~800 líneas de HTML/JS inline para el editor fullscreen. El código JS es complejo y mantenible solo por quién lo escribió.
- **Recomendación:** Mantener (es el objetivo 4). Extraer HTML/JS a archivos separados en `assets/`.

#### 06_Alertas_Operacionales.py (~236 líneas)
- **Función:** Alertas de turnos faltantes y alertas de KPI (disponibilidad, utilización, rendimiento).
- **Frecuencia:** Alta — uso diario de supervisión.
- **Problema encontrado (L21):** `EQUIPOS_FLOTA = ["9245", "9259", "9272", "9274", "9277", "9339"]` definida localmente. Esta misma lista existe en `app_perforacion.py` (L235), `pages/25_Editar_Registro.py` (L21), `pages/26_Reconciliacion_Reportes.py` (L22), y `services/alert_service.py` (L11). Son **5 copias** de la misma constante.
- **Recomendación:** Mantener. Eliminar todas las copias locales y usar `from services.alert_service import EQUIPOS_REPORTES_REQUERIDOS`.

#### 07_Reportes_PDF.py (~75 líneas)
- **Función:** Genera PDFs y muestra lista de PDFs generados.
- **Frecuencia:** Media — uso semanal o mensual.
- **Problema encontrado (L24-26):** Define `dataframe_visible()` localmente (`return df.copy()`) — ignora la implementación real de `ui.formatting.dataframe_visible` que repara mojibake y normaliza columnas.
- **Recomendación:** Mantener. Eliminar `dataframe_visible()` local y usar `from ui.formatting import dataframe_visible`.

### 1.2 Grupo Análisis — Frecuencia variable

#### 08_Panel_Ejecutivo.py (~187 líneas)
- **Función:** Vista ejecutiva con KPIs consolidados, semáforo de salud operacional, rankings.
- **Frecuencia:** Alta — objetivo 2 (KPIs para jefatura).
- **Recomendación:** Mantener.

#### 09_Analisis_Mensual.py (leído parcialmente)
- **Función:** Análisis mensual de KPIs con ranking de equipos y operadores.
- **Frecuencia:** Media — uso mensual de cierre.
- **Recomendación:** Mantener.

#### 10_Dashboard_Excel_Operacional.py (leído parcialmente)
- **Función:** Dashboard sobre datos de ciclos Excel (fuente alternativa al SQLite manual).
- **Frecuencia:** Media — depende de si se usan ciclos Excel.
- **Recomendación:** Mantener — soporta la fuente de datos de ciclos Excel.

#### 11_Alertas_Inteligentes.py (leído parcialmente)
- **Función:** Sistema de alertas con criticidad INFO/PREVENTIVA/CRÍTICA, estado pendiente/vista/atendida.
- **Frecuencia:** Baja — duplica funcionalidad de `06_Alertas_Operacionales.py`.
- **Recomendación:** EVALUAR ELIMINACIÓN o consolidar con la página 06.

#### 12_Calidad_Datos.py (leído parcialmente)
- **Función:** Análisis de calidad de datos con estado Excelente/Aceptable/Observado/Crítico.
- **Frecuencia:** Baja — uso administrativo ocasional.
- **Recomendación:** Mantener solo si existe un responsable de calidad de datos definido.

### 1.3 Grupo Documentos

#### 13_Acciones_Correctivas.py
- **Función:** CRUD de acciones correctivas con estados Pendiente/En revisión/Corregido/Cerrado.
- **Frecuencia:** Baja — no pertenece al núcleo operacional de perforación.
- **Recomendación:** CANDIDATO A ELIMINAR. No contribuye a los 4 objetivos. Si se necesita, integrar como sub-sección de `12_Calidad_Datos.py`.

#### 14_Biblioteca_Tecnica.py
- **Función:** Repositorio de documentos PDF técnicos con catálogo.
- **Frecuencia:** Baja — consulta esporádica.
- **Recomendación:** CANDIDATO A ELIMINAR o externalizar a un SharePoint/repositorio dedicado.

#### 15_Machine_Learning.py
- **Función:** Modelos ML de apoyo (`ml.features`, `ml.model_training`, `ml.predictor`).
- **Frecuencia:** Muy baja — módulo experimental.
- **Recomendación:** CANDIDATO A ELIMINAR si el módulo `ml/` no está maduro. Importa `from ml.features import ...` — verificar si este módulo existe y funciona.

### 1.4 Grupo Administración

#### 16_Auditoria_Historial.py
- **Función:** Historial filtrable de registros operacionales con paginación.
- **Frecuencia:** Media — uso para auditoría y corrección.
- **Recomendación:** Mantener.

#### 17_Edicion_Controlada_Auditoria.py
- **Función:** Edición de registros existentes con trazabilidad de cambios.
- **Frecuencia:** Media — objetivo 1 (corrección de registros).
- **Recomendación:** Mantener.

#### 18_Respaldos_Exportacion.py
- **Función:** Exportación filtrada a Excel/CSV y gestión de backups.
- **Frecuencia:** Media-Alta — exportación operacional.
- **Recomendación:** Mantener.

#### 19_Administracion_Operadores.py (~50 líneas)
- **Función:** CRUD de operadores y sincronización desde ciclos Excel.
- **Frecuencia:** Baja — solo cuando cambia el personal.
- **Recomendación:** Mantener (administración necesaria).

#### 20_Administrar_Fuentes_Excel.py
- **Función:** Importación de Excel de ciclos de perforación como fuente alternativa.
- **Frecuencia:** Baja-Media — al recibir nuevos archivos de ciclos.
- **Recomendación:** Mantener.

#### 21_Fuentes_Datos.py
- **Función:** Administración de fuentes de datos activas (SQLite vs Excel ciclos).
- **Frecuencia:** Baja — configuración del sistema.
- **Recomendación:** Mantener — necesario para el sistema dual de fuentes.

#### 22_Importar_Excel.py
- **Función:** Importación con diagnóstico y validación de Excel externo.
- **Frecuencia:** Baja — al recibir nuevos Excels.
- **Recomendación:** Mantener.

#### 23_Administracion_Catalogos.py
- **Función:** CRUD de catálogo de equipos y operadores.
- **Frecuencia:** Baja — configuración inicial.
- **Recomendación:** Mantener.

#### 24_Alertas_Registros.py (nuevo, no registrado en main)
- **Función:** Panel de alertas de reportes faltantes con rangos configurables (7/14/30 días).
- **Frecuencia:** Alta — duplica parcialmente funcionalidad de `06_Alertas_Operacionales.py`.
- **Recomendación:** Evaluar consolidación con página 06 o mantener como vista dedicada.

#### 25_Editar_Registro.py (nuevo)
- **Función:** Edición directa de registros con formulario completo y recálculo KPI.
- **Frecuencia:** Media — complementa `17_Edicion_Controlada_Auditoria.py`.
- **Problema encontrado (L21):** `_EQUIPOS = ["9245", "9259", "9272", "9274", "9277", "9339"]` — 4ta copia hardcodeada.
- **Recomendación:** Mantener. Centralizar `_EQUIPOS`.

#### 26_Reconciliacion_Reportes.py (nuevo)
- **Función:** Reconciliación de registros con fechas sospechosas (lógica específica para fechas 2026-06-17/18).
- **Frecuencia:** Muy baja — herramienta de corrección puntual.
- **Problema encontrado (reconciliation_service.py, L15-16):** `TARGET_CREATED_DATES = {"2026-06-17", "2026-06-18"}` y `PROTECTED_KEYS = {("2026-06-15", "Noche", "9259")}` — lógica de negocio hardcodeada para un evento específico.
- **Recomendación:** ELIMINAR o refactorizar para ser paramétrico. La lógica hardcodeada de fechas específicas es una deuda técnica severa.

---

## SECCIÓN 2: ANÁLISIS DE MÓDULOS PRINCIPALES

### 2.1 app_perforacion.py (861 líneas)

**Rol:** Punto de entrada de la aplicación, registro de páginas, formulario principal.

**Funciones presentes:**
- `formulario_registro()` (L487-734): Formulario completo de ingreso — 248 líneas de lógica UI mezclada con validación.
- `render_panel_turnos_faltantes()` (L323-396): Panel de turnos faltantes (duplica lógica con `24_Alertas_Registros.py`).
- `_calcular_turnos_faltantes()` (L239-270): Llama a `alert_service`.
- `estado_operacional_equipo()` (L428-436): Wrapper que llama a `kpi_service.estado_operacional_equipo()`.

**Wrappers redundantes (delegaciones de 1 línea):**
- L399-400: `normalizar_nombre_columna` → `kpi_service.normalizar_nombre_columna`
- L403-404: `buscar_columna` → `kpi_service.buscar_columna`
- L407-408: `serie_numerica` → `kpi_service.serie_numerica`
- L411-412: `totales_productivos` → `kpi_service.totales_productivos`
- L483-484: `resumen_operacional_equipos` → `kpi_service.resumen_operacional_equipos`

**Duplicaciones críticas:**
- `DETENCION_HORAS_COLUMNAS` dict (L26-42): **Copia 1 de 2** (copia 2 en `pdf_report.py` L33-49).
- `color_estado_operacional()` (L439-458): **Copia 1 de 2** (copia 2 en `pdf_report.py` L391-410).
- `color_texto_estado_operacional()` (L461-480): **Copia 1 de 2** (copia 2 en `pdf_report.py` L413-432).
- `_EQUIPOS_FLOTA_ALERTA = ["9245", ...]` (L235): **Copia 1 de 5**.

**Código debug activo:**
- L526-531: Bloque DEBUG en formulario principal.
- L709-714: Otro bloque DEBUG en formulario principal.

### 2.2 dashboard.py (2067 líneas)

**Rol:** Módulo-dios del dashboard. Contiene visualizaciones, lógica KPI, resúmenes, gráficos de tendencia, ranking de horómetros, editor de estado de flota, y lógica de observaciones por fase.

**Duplicaciones internas:**
- L59-75: `texto_visible()` — DUPLICADO. La versión correcta está en `ui.formatting.texto_visible`.
- L78-93: `dataframe_visible()` — DUPLICADO. La versión correcta está en `ui.formatting.dataframe_visible`.
- L96-117: Cuatro wrappers de 1 línea a `kpi_service` — IGUALES a los de `app_perforacion.py`.

**Funciones de alto impacto:**
- `mostrar_panel_graficos_resumen()` (L578-622): Panel principal de KPIs.
- `_render_graficos_tendencia()` (L1074-1310): Gráficos de tendencia Disp/Util/Rendimiento — 236 líneas.
- `_render_ranking_horas_motor()` (L1313-1463): Ranking por horómetro.
- `mostrar_observaciones_detenciones_por_fase()` (L1688-1726): Consulta de detenciones.
- `dashboard()` (L1729-fin): Función principal que orquesta todo.

**Recomendación:** Dividir en módulos:
- `dashboard_kpi.py`: Funciones de KPI y resúmenes (≈500 líneas)
- `dashboard_charts.py`: Gráficos de tendencia y rankings (≈600 líneas)
- `dashboard_fleet.py`: Estado de flota y fase (≈400 líneas)
- `dashboard.py`: Solo orquestación (≈200 líneas)

### 2.3 db.py (1822 líneas)

**Rol:** Capa de acceso a SQLite. Define esquema, migración, consultas filtradas, índices.

**Puntos positivos:**
- `ClosingConnection` (L54-58): Cierre automático de conexiones.
- `normalizar_esquema_columnas()` (L282-319): Auto-migración de columnas al iniciar.
- `INDEXES_REGISTROS` (L43-51): 7 índices para performance.
- WAL mode activo para concurrencia.

**Duplicaciones:**
- `_limpiar_entero()` (L1813-1821): DUPLICADO de `limpiar_entero()` en `utils.py` (L60-76). Misma lógica, diferente nombre con underscore.

**Funciones pesadas:**
- `consultar_resumen_operacional_equipos_filtrado()` (L1033-1187): 154 líneas de SQL + Python para recalcular KPIs por equipo. Duplica lógica de `kpi_service`.
- `consultar_resumen_aceros_filtrado()` (L1190-1273): 83 líneas para resumen de aceros, lógica duplicada con `dashboard.resumen_general_aceros()`.

**Recomendación:** Mantener la capa de acceso a datos en `db.py` pero mover la lógica de KPI recalculada a `kpi_service`.

### 2.4 schema.py (510 líneas)

**Rol:** Definición canónica de columnas, aliases, equivalencias y normalización.

**Problema detectado:**
El dict `COLUMN_ALIASES` (L223-265) tiene **claves Python duplicadas** que Python sobreescribe silenciosamente. Por ejemplo, la clave `"Número equipo"` aparece 3 veces con el mismo valor. Aunque no es un bug (el valor es idéntico), genera confusión en mantenimiento y puede enmascarar errores si alguien cambia un valor sin notar que hay otra clave igual.

**Estructura:**
- `COLUMN_ALIASES` (L223-265): Aliases básicos históricos.
- `MODERN_COLUMN_ALIASES` (L293-328): Aliases de nomenclatura moderna.
- `LEGACY_COLUMN_ALIASES` (L330-332): Compatibilidad legacy.
- `ORTHOGRAPHY_COLUMN_ALIASES` (L334-359): Correcciones tipográficas.
- `COLUMN_EQUIVALENTS` (L399-419): Grupos lógicos usados por `kpi_service`.

**Recomendación:** Limpiar las claves duplicadas en `COLUMN_ALIASES`. Agregar un test unitario que verifique que no hay claves repetidas.

### 2.5 utils.py (112 líneas)

**Rol:** Constantes y funciones utilitarias globales.

**Constantes presentes:**
- `HORAS_TURNO = 12`
- `EQUIPOS` dict: `{"Sandvik D75KS": ["9245", "9277"], "SmartROC D65": ["9339"], "FlexiROC D65": ["9274", "9272", "9259"]}`
- `OPERADORES` list: 7 nombres
- `TIPOS_DETENCION`: 15 tipos de detención
- `IMAGENES_EQUIPO`: mapas de imágenes

**Problema:** `EQUIPOS` define la flota correctamente, pero las páginas y servicios usan listas planas `["9245", "9259", ...]` hardcodeadas en lugar de derivarlas de `EQUIPOS`.

**Recomendación:** Agregar `NUMEROS_FLOTA = [n for nums in EQUIPOS.values() for n in nums]` en `utils.py` y reemplazar las 5 copias hardcodeadas.

### 2.6 pdf_report.py (1108 líneas)

**Rol:** Generación de PDF con ReportLab (A4 landscape).

**Duplicaciones críticas:**
- `DETENCION_HORAS_COLUMNAS` dict (L33-49): **Copia 2 de 2** — idéntica a `app_perforacion.py` L26-42.
- `color_estado_operacional()` (L391-410): **Copia 2 de 2** — idéntica a `app_perforacion.py` L439-458.
- `color_texto_estado_operacional()` (L413-432): **Copia 2 de 2** — idéntica a `app_perforacion.py` L461-480.
- Wrappers L57-71: `normalizar_nombre_columna`, `buscar_columna`, `serie_numerica`, `totales_productivos` — igual que en `app_perforacion.py` y `dashboard.py`.

**Función de imagen diferenciada:**
- `ruta_imagen_equipo_pdf()` (L457-481): Versión más compleja de `ruta_imagen_equipo()` en `utils.py`. Tiene lógica adicional para PDF. Podría unificarse con un parámetro.

---

## SECCIÓN 3: ANÁLISIS DE SERVICIOS (29 servicios)

### 3.1 Servicios de alto uso (objetivos 1-4)

#### services/kpi_service.py — CRÍTICO
- **Funciones clave:** `calcular_kpi_operacional_productivo()`, `normalizar_nombre_columna()`, `buscar_columna()`, `serie_numerica()`, `totales_productivos()`, `resumen_operacional_equipos()`, `estado_operacional_equipo()`.
- **Problema:** Sus funciones principales (`normalizar_nombre_columna`, `buscar_columna`, `serie_numerica`, `totales_productivos`) están reexportadas como wrappers en `app_perforacion.py`, `dashboard.py` y `pdf_report.py`. Los 3 archivos deberían importar directamente desde `kpi_service`.
- **Recomendación:** Mantener. Eliminar los wrappers en los 3 archivos consumidores.

#### services/alert_service.py — CRÍTICO
- **Funciones clave:** `get_reportes_faltantes()`, `evaluar_alertas_operacionales()`, `EQUIPOS_REPORTES_REQUERIDOS`.
- **Constante:** `EQUIPOS_REPORTES_REQUERIDOS = ["9245", "9259", "9272", "9274", "9277", "9339"]` — **esta es la fuente canónica** que debe usarse en las 5 copias.
- **Recomendación:** Mantener. Exportar `EQUIPOS_REPORTES_REQUERIDOS` a las páginas que la necesiten.

#### services/report_service.py — CRÍTICO
- **Funciones:** `validar_datos_para_guardado()`, `ejecutar_guardado_reporte()`.
- **Recomendación:** Mantener. Bien estructurado.

#### services/executive_service.py
- **Funciones:** `consultar_panel_ejecutivo()`, `construir_panel_ejecutivo()`, `calcular_kpis_ejecutivos()`.
- **Problema (L21-22):** `def columna_operador_visual(df)` está definida en `executive_service` pero `buscar_columna` que importa es de `kpi_service` — la función `buscar_columna` no está importada explícitamente, sugiriendo que podría fallar.
- **Recomendación:** Mantener.

#### services/malla_service.py
- **Funciones:** Gestión de planos, pozos de malla, planes de perforación, sectores.
- **Problema:** 60+ funciones en un solo archivo (14 tablas distintas de DB).
- **Recomendación:** Mantener pero dividir en `malla_planes_service.py` y `malla_pozos_service.py`.

#### services/clasificacion_operacional_service.py
- **Funciones:** `clasificacion_inferida()`, `validar_clasificacion_registro()`, `actualizar_clasificacion_registro()`.
- **Recomendación:** Mantener — necesario para el objetivo 3 (planos/sectores).

#### services/reconciliation_service.py — PROBLEMÁTICO
- `TARGET_CREATED_DATES = {"2026-06-17", "2026-06-18"}` hardcodeado.
- `PROTECTED_KEYS = {("2026-06-15", "Noche", "9259")}` hardcodeado.
- Lógica específica para una corrección de datos puntual que no debería existir como servicio permanente.
- **Recomendación:** ELIMINAR o convertir en una herramienta paramétrica de administración.

### 3.2 Servicios de media relevancia

| Servicio | Uso | Observación |
|---|---|---|
| `catalog_service.py` | Alto | Catálogo de equipos/operadores activos. Necesario. |
| `backup_service.py` | Medio | Exportación y backup. Necesario. |
| `export_service.py` | Medio | Exportación Excel. Necesario. |
| `monthly_service.py` | Medio | Análisis mensual. Necesario. |
| `ciclos_service.py` | Medio | Fuente Excel de ciclos. Necesario. |
| `malla_avance_service.py` | Medio | Avance real vs planificado. Necesario. |
| `source_service.py` | Bajo | Registro de fuentes de datos. |
| `import_diagnostic_service.py` | Bajo | Diagnóstico de importación Excel. |
| `import_execution_service.py` | Bajo | Ejecución de importación Excel. |
| `operational_excel_service.py` | Medio | Dashboard Excel ciclos. |
| `operational_excel_query_service.py` | Medio | Consultas sobre ciclos Excel. |
| `data_source_selector_service.py` | Bajo | Selector de fuente activa. |
| `source_adapter_service.py` | Bajo | Adaptador de fuentes. |
| `source_routing_helpers.py` | Bajo | Helpers de enrutamiento de fuente. |

### 3.3 Servicios de baja relevancia (candidatos a eliminar)

| Servicio | Uso | Recomendación |
|---|---|---|
| `smart_alerts_service.py` | Muy bajo | Duplica `alert_service`. Evaluar consolidación. |
| `data_quality_service.py` | Bajo | Solo usado por páginas 12 y 13. |
| `corrective_actions_service.py` | Muy bajo | Solo usado por página 13 (candidata a eliminar). |
| `documentation_service.py` | Muy bajo | Solo usado por página 14 (candidata a eliminar). |
| `enaex_pdf_extraction_service.py` | Bajo | Usado por páginas 03 y 04. Podría consolidarse. |
| `ortomosaico_service.py` | Bajo | Solo usado por página 05. Sería reubicable. |
| `operator_admin_service.py` | Bajo | Solo usado por página 19. |

---

## SECCIÓN 4: ANÁLISIS DE UI COMPONENTS (16 componentes)

### 4.1 Componentes activos y necesarios

#### ui/formatting.py (26 líneas) — CRÍTICO
- `texto_visible(valor)`: Repara mojibake con `text_utils.reparar_mojibake`.
- `dataframe_visible(df)`: Normaliza columnas y valores de texto.
- **Problema:** Esta función está duplicada en `dashboard.py` (L59-93) con implementaciones distintas y menos completas. `dashboard.py` debería importar de aquí.

#### ui/auth.py (~80+ líneas)
- Sistema de autenticación con SHA256/bcrypt, carga de credenciales desde `.env`.
- Bien estructurado. Mantener.

#### ui/forms_sections.py (~80+ líneas leídas)
- Componentes de formulario: `render_equipo_operador_fecha()`, `render_ubicacion_condiciones()`, `render_horas_turno()`, `render_produccion_consumos()`.
- Bien factorizado. Mantener.

#### ui/components.py (~80+ líneas)
- `section_header()`, `metric_card()`, `kpi_hero_card()`, `fleet_status_card()`, `document_tile()`.
- Bien estructurado. Mantener.

#### ui/filters.py (~80+ líneas)
- `aplicar_filtros()` con manejo de fecha, turno, equipo, operador, tipo de detención.
- Mantener.

#### ui/page_header.py
- `render_page_header()`: Header estándar para todas las páginas.
- Mantener.

#### ui/alerts_view.py
- `mostrar_alertas_operacionales()`: Vista de alertas delegada desde el dashboard.
- Mantener.

#### ui/home.py
- Funciones auxiliares para la página principal: `contar_pdfs_generados()`, `ultima_fecha_registrada()`, `contar_alertas_actuales()`.
- Mantener.

#### ui/pdf_section.py
- `seccion_reporte_pdf()`: Sección de generación de PDF en el dashboard.
- Mantener.

#### ui/data_source.py
- `seleccionar_fuente_datos()`, `cargar_dataframe_fuente()`.
- Mantener — necesario para el sistema de fuentes dual.

### 4.2 Componentes con problemas específicos

#### ui/sectores_widget.py (nuevo, sin leer)
- Nuevo widget para selección de sectores. Necesita revisión.

#### ui/ortomosaico_ui.py
- `renderizar_controles()`, `construir_figura_ortomosaico()`, `config_plotly_interactivo()`.
- Mantener — objetivo 4.

---

## SECCIÓN 5: DUPLICACIONES Y CÓDIGO REPETIDO

### 5.1 Duplicaciones de Nivel Crítico

#### Duplicación 1: DETENCION_HORAS_COLUMNAS
| Archivo | Líneas |
|---|---|
| `app_perforacion.py` | L26-42 |
| `pdf_report.py` | L33-49 |

**Solución:** Mover a `utils.py` o a un módulo `constants.py`. Importar desde ahí.

#### Duplicación 2: color_estado_operacional() y color_texto_estado_operacional()
| Archivo | Líneas |
|---|---|
| `app_perforacion.py` | L439-458 y L461-480 |
| `pdf_report.py` | L391-410 y L413-432 |

Ambas versiones son **idénticas** (verificado en análisis anterior). 

**Solución:** Mover a `ui/formatting.py` o `utils.py`. Importar desde ambos archivos.

#### Duplicación 3: Wrappers de kpi_service
Los siguientes 4 wrappers de 1 línea aparecen idénticos en **3 archivos**:
- `normalizar_nombre_columna`, `buscar_columna`, `serie_numerica`, `totales_productivos`

| Archivo | Líneas |
|---|---|
| `app_perforacion.py` | L399-412 |
| `dashboard.py` | L96-117 |
| `pdf_report.py` | L57-71 |

**Solución:** Eliminar todos los wrappers. Usar `from services.kpi_service import normalizar_nombre_columna, buscar_columna, serie_numerica, totales_productivos` directamente donde se necesiten.

#### Duplicación 4: texto_visible() y dataframe_visible()
| Archivo | Líneas |
|---|---|
| `ui/formatting.py` | L6-25 (versión canónica) |
| `dashboard.py` | L59-93 (versión incompleta) |

La versión de `dashboard.py` es inferior: `texto_visible` solo devuelve `str(valor)` sin reparar mojibake, y `dataframe_visible` solo hace `df.copy()`.

**Solución:** Eliminar las versiones de `dashboard.py` y agregar al inicio: `from ui.formatting import texto_visible, dataframe_visible`.

#### Duplicación 5: Lista de flota hardcodeada
| Archivo | Variable | Línea |
|---|---|---|
| `services/alert_service.py` | `EQUIPOS_REPORTES_REQUERIDOS` | L11 |
| `app_perforacion.py` | `_EQUIPOS_FLOTA_ALERTA` | L235 |
| `pages/06_Alertas_Operacionales.py` | `EQUIPOS_FLOTA` | L21 |
| `pages/25_Editar_Registro.py` | `_EQUIPOS` | L21 |
| `pages/26_Reconciliacion_Reportes.py` | `_EQUIPOS` | L22 |

**Solución:** Usar `from services.alert_service import EQUIPOS_REPORTES_REQUERIDOS` en todas partes.

#### Duplicación 6: _limpiar_entero() vs limpiar_entero()
| Archivo | Función | Línea |
|---|---|---|
| `utils.py` | `limpiar_entero()` | L60-76 |
| `db.py` | `_limpiar_entero()` | L1813-1821 |

Misma lógica. `db.py` tiene su propia versión privada cuando podría importar `from utils import limpiar_entero`.

---

## SECCIÓN 6: IMPORTS NO UTILIZADOS O PROBLEMÁTICOS

### 6.1 Imports problemáticos confirmados

**`pages/07_Reportes_PDF.py` (L24-26):**
```python
def dataframe_visible(df):
    return df.copy()
```
Define localmente `dataframe_visible` ignorando la implementación de `ui.formatting`. Debería ser:
```python
from ui.formatting import dataframe_visible
```

**`pages/08_Panel_Ejecutivo.py` (L127-131):**
Define `mostrar_tabla_o_vacio()` localmente. Patrón similar en otras páginas.

**`pages/15_Machine_Learning.py` (L14):**
```python
from ml.features import FEATURE_COLUMNS, cargar_registros_sqlite, preparar_features
```
Importa de un módulo `ml/` que necesita verificación de existencia y madurez.

**`pages/16_Auditoria_Historial.py` (L16):**
```python
from audit.audit_log import AUDIT_LOG_PATH
```
Importa de un módulo `audit/` — necesita verificación.

**`pages/06_Alertas_Operacionales.py` (L2):**
```python
from operators import etiqueta_operador
```
Importa de un módulo `operators` (no es `services.operator_admin_service`). Necesita verificación de si existe el módulo raíz `operators.py`.

**`dashboard.py` (L59-93):**
Define `texto_visible()` y `dataframe_visible()` localmente sin importar de `ui.formatting`. Esto oculta el mojibake en el dashboard principal.

### 6.2 Posibles módulos raíz no documentados

Los siguientes imports de módulos raíz (sin prefijo `services/`) requieren verificación:
- `from operators import etiqueta_operador` — ¿existe `operators.py` en raíz?
- `from audit.audit_log import AUDIT_LOG_PATH` — ¿existe `audit/` directorio?
- `from ml.features import ...` — ¿existe `ml/` directorio?
- `from alerts import evaluar_alertas_operacionales` — en `ui/home.py`. ¿Es distinto de `services.alert_service`?
- `from data import leer_reportes_sqlite as leer_reportes` — en página 01. ¿Existe módulo `data/`?
- `from metrics import calcular_disponibilidad, ...` — en `kpi_service.py`. ¿Existe módulo `metrics/`?
- `from validation import report_validation` — en `report_service.py`. ¿Existe `validation/`?
- `from text_utils import reparar_mojibake` — en `ui/formatting.py`. ¿Existe `text_utils.py`?

---

## SECCIÓN 7: PLAN DE ACCIÓN

### Prioridad 1 — Críticas (impacto inmediato, riesgo de bug)

| # | Acción | Archivos | Esfuerzo |
|---|---|---|---|
| P1.1 | Eliminar código DEBUG activo | `app_perforacion.py` L526-531, L709-714; `pages/01_Registro_Operacional.py` L86-94 | 30 min |
| P1.2 | Eliminar funciones duplicadas en `dashboard.py` | `dashboard.py` L59-93 → import desde `ui.formatting` | 15 min |
| P1.3 | Eliminar `dataframe_visible` local en `pages/07_Reportes_PDF.py` | `pages/07_Reportes_PDF.py` L24-26 | 5 min |
| P1.4 | Centralizar lista de flota | 5 archivos con `_EQUIPOS` hardcodeado | 20 min |
| P1.5 | Centralizar `DETENCION_HORAS_COLUMNAS` | `app_perforacion.py` L26-42, `pdf_report.py` L33-49 | 15 min |
| P1.6 | Centralizar `color_estado_operacional` y `color_texto_estado_operacional` | `app_perforacion.py` L439-480, `pdf_report.py` L391-432 | 20 min |

### Prioridad 2 — Refactoring (mejora de mantenibilidad)

| # | Acción | Archivos | Esfuerzo |
|---|---|---|---|
| P2.1 | Eliminar wrappers de `kpi_service` en `app_perforacion.py`, `dashboard.py`, `pdf_report.py` | 3 archivos | 1 hora |
| P2.2 | Eliminar `_limpiar_entero()` de `db.py` y usar `from utils import limpiar_entero` | `db.py` L1813-1821 | 10 min |
| P2.3 | Limpiar claves duplicadas en `schema.py COLUMN_ALIASES` | `schema.py` L223-265 | 30 min |
| P2.4 | Dividir `dashboard.py` en 4 módulos | `dashboard.py` | 4-6 horas |
| P2.5 | Extraer SQL de `pages/03_Avance_Operacional.py` a un servicio | `pages/03_Avance_Operacional.py` | 2 horas |
| P2.6 | Limpiar `reconciliation_service.py` o hacerlo paramétrico | `services/reconciliation_service.py` | 1 hora |

### Prioridad 3 — Eliminación de páginas candidatas

| # | Página | Razón |
|---|---|---|
| P3.1 | `13_Acciones_Correctivas.py` | No pertenece al núcleo operacional |
| P3.2 | `14_Biblioteca_Tecnica.py` | Mejor en repositorio externo |
| P3.3 | `15_Machine_Learning.py` | Módulo experimental no maduro |
| P3.4 | `26_Reconciliacion_Reportes.py` | Herramienta para evento específico ya pasado |
| P3.5 | Consolidar `11_Alertas_Inteligentes.py` con `06_Alertas_Operacionales.py` | Duplicación funcional |

### Prioridad 4 — Mejoras de arquitectura (largo plazo)

| # | Acción | Descripción |
|---|---|---|
| P4.1 | Agregar `NUMEROS_FLOTA` a `utils.py` | Lista derivada de `EQUIPOS` para toda la app |
| P4.2 | Simplificar firma de `dashboard()` | Reducir de 11 parámetros a importaciones directas |
| P4.3 | Mover lógica KPI de `db.py` a `kpi_service` | `consultar_resumen_operacional_equipos_filtrado()` (L1033-1187) |
| P4.4 | Extraer HTML/JS del ortomosaico | De `pages/05_Ortomosaico_Vista_Mina.py` a `assets/` |
| P4.5 | Test unitario para `schema.py` | Verificar ausencia de claves duplicadas en COLUMN_ALIASES |

---

## SECCIÓN 8: MAPA DE DEPENDENCIAS

### 8.1 Grafo de dependencias principales

```
app_perforacion.py
    ├── ui.auth (autenticación)
    ├── ui.forms_sections (formulario de turno)
    ├── services.kpi_service (KPI cálculo)
    ├── services.alert_service (alertas faltantes)
    ├── services.report_service (guardado)
    └── db (consultas historial)

pages/02_Dashboard_Operacional.py
    └── dashboard.py
            ├── services.kpi_service
            ├── services.executive_service
            ├── services.catalog_service
            ├── services.malla_service
            ├── ui.components
            ├── ui.formatting (PERO duplica localmente)
            └── db

pages/01_Registro_Operacional.py
    └── app_perforacion.py (proxy de st + funciones)
        └── services.report_service, kpi_service, alert_service

pages/07_Reportes_PDF.py
    └── ui.pdf_section → pdf_report.py
            ├── services.kpi_service (wrappers)
            └── (duplica color functions de app_perforacion)

services/kpi_service.py
    ├── metrics (calcular_disponibilidad, etc.)
    ├── schema (columnas_equivalentes)
    ├── services.catalog_service
    └── utils (HORAS_TURNO, limpiar_entero)

services/alert_service.py
    ├── db (leer registros)
    └── schema (columnas_equivalentes)

services/executive_service.py
    ├── db
    ├── metrics
    ├── services.catalog_service
    ├── services.kpi_service
    └── services.alert_service

services/report_service.py
    ├── audit.audit_log
    ├── data (anexar_registro, crear_registro)
    ├── ui.form_helpers
    └── validation.report_validation

db.py
    ├── schema (normalización de columnas)
    └── config (DATABASE_PATH)
```

### 8.2 Módulos raíz confirmados (no en services/ ni ui/)

Los siguientes módulos existen fuera de las carpetas estándar y deben ser documentados:
- `config.py` — Configuración de rutas (DATABASE_PATH, EXCEL_PATH, etc.)
- `metrics/` o `metrics.py` — Funciones de cálculo matemático de KPIs
- `schema.py` — Definición canónica de columnas (en raíz)
- `utils.py` — Constantes y utilidades (en raíz)
- `data/` — Módulo de lectura de datos (importado en página 01)
- `operators.py` — `etiqueta_operador()` (importado en varias páginas)
- `text_utils.py` — `reparar_mojibake()` (importado en `ui/formatting.py`)
- `validation/` — `report_validation` (importado en `report_service.py`)
- `audit/` — `audit_log` (importado en páginas de auditoría)
- `ml/` — Modelos ML (importado en página 15)
- `runtime_cache/` — `@cache_data` y `@cache_resource` custom

---

## APÉNDICE

### A.1 Inventario de archivos leídos

| Archivo | Líneas | Leído |
|---|---|---|
| `app_perforacion.py` | 861 | Completo |
| `dashboard.py` | 2067 | L1-1469 + L1469-1769 |
| `db.py` | 1822 | Completo |
| `schema.py` | 510 | Completo |
| `utils.py` | 112 | Completo |
| `pdf_report.py` | 1108 | Completo |
| `pages/01_Registro_Operacional.py` | 399 | Completo |
| `pages/02_Dashboard_Operacional.py` | 55 | Completo |
| `pages/03_Avance_Operacional.py` | 985 | Completo |
| `pages/04_Gestion_Planos.py` | 1318 | Completo |
| `pages/05_Ortomosaico_Vista_Mina.py` | 1148 | Completo |
| `pages/06_Alertas_Operacionales.py` | 236 | Completo |
| `pages/07_Reportes_PDF.py` | 75 | Completo |
| `pages/08_Panel_Ejecutivo.py` | 187 | Completo |
| `pages/09_Analisis_Mensual.py` | ~200+ | Primeras 80 líneas |
| `pages/10_Dashboard_Excel_Operacional.py` | ~200+ | Primeras 80 líneas |
| `pages/11_Alertas_Inteligentes.py` | ~200+ | Primeras 80 líneas |
| `pages/12_Calidad_Datos.py` | ~200+ | Primeras 80 líneas |
| `pages/13_Acciones_Correctivas.py` | ~200+ | Primeras 60 líneas |
| `pages/14_Biblioteca_Tecnica.py` | ~200+ | Primeras 60 líneas |
| `pages/15_Machine_Learning.py` | ~100+ | Primeras 60 líneas |
| `pages/16_Auditoria_Historial.py` | ~200+ | Primeras 60 líneas |
| `pages/17_Edicion_Controlada_Auditoria.py` | ~200+ | Primeras 60 líneas |
| `pages/18_Respaldos_Exportacion.py` | ~300+ | Primeras 80 líneas |
| `pages/19_Administracion_Operadores.py` | ~100 | Primeras 50 líneas |
| `pages/20_Administrar_Fuentes_Excel.py` | ~200+ | Primeras 50 líneas |
| `pages/21_Fuentes_Datos.py` | ~200+ | Primeras 50 líneas |
| `pages/22_Importar_Excel.py` | ~200+ | Primeras 50 líneas |
| `pages/23_Administracion_Catalogos.py` | ~70 | Completo |
| `pages/24_Alertas_Registros.py` | ~150+ | Primeras 60 líneas |
| `pages/25_Editar_Registro.py` | ~300+ | Primeras 60 líneas |
| `pages/26_Reconciliacion_Reportes.py` | ~200+ | Primeras 60 líneas |
| `services/kpi_service.py` | ~500+ | Primeras 100 líneas |
| `services/alert_service.py` | ~300+ | Primeras 80 líneas |
| `services/report_service.py` | ~300+ | Primeras 80 líneas |
| `services/executive_service.py` | ~200+ | Primeras 60 líneas |
| `services/malla_service.py` | ~500+ | Primeras 60 líneas |
| `services/clasificacion_operacional_service.py` | ~200+ | Primeras 60 líneas |
| `services/reconciliation_service.py` | ~200+ | Primeras 60 líneas |
| `ui/auth.py` | ~200+ | Primeras 80 líneas |
| `ui/filters.py` | ~300+ | Primeras 80 líneas |
| `ui/forms_sections.py` | ~500+ | Primeras 80 líneas |
| `ui/formatting.py` | 26 | Completo |
| `ui/components.py` | ~120+ | Primeras 80 líneas |
| `ui/home.py` | ~100+ | Primeras 40 líneas |

### A.2 Resumen de conteo de problemas

| Categoría | Cantidad |
|---|---|
| Duplicaciones de código (conjuntos) | 6 |
| Copias de lista de flota hardcodeada | 5 |
| Bloques DEBUG activos en producción | 4 |
| Wrappers de 1 línea redundantes | 4 (×3 archivos = 12 funciones redundantes) |
| Páginas candidatas a eliminar | 4-5 |
| Módulos raíz no documentados | ~10 |
| Funciones locales que duplican `ui.formatting` | 4 |

### A.3 Líneas de código por módulo (aproximado)

| Módulo | Líneas |
|---|---|
| `dashboard.py` | 2067 |
| `db.py` | 1822 |
| `pdf_report.py` | 1108 |
| `pages/04_Gestion_Planos.py` | 1318 |
| `pages/05_Ortomosaico_Vista_Mina.py` | 1148 |
| `pages/03_Avance_Operacional.py` | 985 |
| `app_perforacion.py` | 861 |
| `schema.py` | 510 |
| Total estimado del proyecto | ~18.000-22.000 líneas |

---

*Fin del análisis. Archivo generado automáticamente — no modificar sin actualizar la versión correspondiente.*
