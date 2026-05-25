# Arquitectura Operacional

## Fuente oficial

La fuente oficial del sistema es `reportes_perforacion.db`.

`reportes_perforacion.xlsx` queda como:

- exportación operativa,
- respaldo derivado,
- insumo para recuperación manual.

La lectura cotidiana de la aplicación debe priorizar SQLite.

## Flujo operativo actual

El flujo principal es:

`Streamlit -> validaciones -> SQLite -> exportación Excel -> dashboard / PDF / alertas`

La escritura operativa confirma primero en SQLite. Si SQLite falla, el guardado no se considera exitoso. Excel puede fallar después sin invalidar el guardado principal.

## Estructura de módulos

- `app_perforacion.py`: aplicación Streamlit principal y orquestación visual.
- `data.py`: normalización, lectura, guardado, anexado y wrappers de compatibilidad.
- `db.py`: persistencia SQLite y operaciones CRUD.
- `dashboard.py`: vistas operacionales y analíticas sobre `DataFrame`.
- `metrics.py`: cálculos operacionales y KPI.
- `charts.py`: gráficas del dashboard.
- `pdf_report.py`: generación de PDF.
- `services/report_service.py`: payload, validaciones previas y ejecución del guardado.
- `services/export_service.py`: exportación Excel y respaldo del archivo.
- `services/alert_service.py`: reglas operacionales de alertas.
- `ui/`: secciones visuales del formulario, dashboard y mantenimiento.
- `pages/`: páginas multipágina de Streamlit.
- `validation/`: validaciones de formulario y reglas de negocio.

## Servicios principales

### `services/report_service.py`

Encapsula el flujo de guardado:

- construye el payload del registro,
- valida horas y operador,
- ejecuta el guardado,
- registra auditoría de rechazo y éxito,
- preserva compatibilidad con la UI.

### `services/export_service.py`

Encapsula la salida Excel:

- exportación desde `DataFrame`,
- formato visual del archivo,
- respaldo previo del Excel cuando aplica.

### `db.py`

Concentra la persistencia SQLite:

- creación de tablas,
- inserción,
- lectura,
- actualización,
- eliminación,
- reemplazo completo del histórico,
- detección de duplicados operacionales.

## Compatibilidad legacy temporal

El sistema mantiene compatibilidad temporal con rutas antiguas:

- `leer_reportes()` funciona como wrapper temporal sobre SQLite.
- `leer_reportes_excel_legacy()` existe para recuperación manual.
- `ui/data_status.py` sigue siendo un panel de comparación y mantenimiento SQLite vs Excel.

Estas rutas no deben interpretarse como el camino operativo principal.

## Flujo Streamlit -> SQLite -> Dashboard/PDF/Alertas

1. El usuario interactúa con Streamlit.
2. El formulario arma el payload y valida datos.
3. El guardado confirma primero en SQLite.
4. Excel se exporta como derivación secundaria.
5. Las vistas operativas leen desde SQLite.
6. Dashboard, PDF y alertas consumen el mismo `DataFrame` ya normalizado.

## Estado de la lectura

La lectura operativa debe usar SQLite.

Excel queda para:

- recuperación manual,
- respaldo,
- exportación,
- comparación de mantenimiento.

## Próximas capacidades del sistema

- avance digital de malla de perforación,
- visualización de pozos perforados sobre malla,
- estados por color por pozos / sector / avance,
- trazabilidad por operador,
- análisis operacional por turno, equipo y frente,
- Machine Learning para predicción de rendimiento,
- predicción de disponibilidad y utilización,
- integración con planos y referencias de malla.

## Riesgos técnicos actuales

- Excel sigue existiendo como artefacto operativo secundario, lo que exige mantener sincronización controlada.
- La compatibilidad legacy debe permanecer aislada para no reintroducir fallback automático.
- Las páginas manuales de mantenimiento no deben confundirse con la ruta operativa.

## Recomendación de evolución

La evolución natural del sistema es:

1. consolidar SQLite como única fuente operativa,
2. dejar Excel solo como exportación y recuperación manual,
3. añadir avance digital de malla,
4. construir analítica visual sobre SQLite,
5. preparar una API o frontend web cuando la persistencia quede estable.
