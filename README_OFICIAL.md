# Sistema de Reporte de Perforacion

Ruta oficial unica:

`C:\Python_Proyectos\Report_Perforacion`

Version actual:

`v2.3.0 - Estabilizacion Biblioteca Tecnica Operacional`

## Ejecucion

```powershell
cd C:\Python_Proyectos\Report_Perforacion
python -m streamlit run app_perforacion.py
```

Datos oficiales:

`C:\Python_Proyectos\Report_Perforacion\reportes_perforacion.db`

Excel oficial de exportacion y respaldo:

`C:\Python_Proyectos\Report_Perforacion\reportes_perforacion.xlsx`

## Fases estabilizadas

- FASE 14: Calidad de Datos.
- FASE 15: Score de Calidad.
- FASE 16: Acciones Correctivas.
- FASE 18: Biblioteca Tecnica Operacional.
- FASE 19: Estabilizacion Biblioteca Tecnica.

## Modulos principales

- `pages/06_Calidad_Datos.py`
- `pages/07_Acciones_Correctivas.py`
- `pages/08_Biblioteca_Tecnica.py`
- `services/data_quality_service.py`
- `services/corrective_actions_service.py`
- `services/documentation_service.py`
- `services/smart_alerts_service.py`
- `services/executive_service.py`

## Tablas SQLite

- `auditoria_ediciones`
- `alertas_inteligentes`
- `alertas_inteligentes_control`
- `acciones_correctivas`
- `documentacion_tecnica`

## Biblioteca Tecnica Operacional

La Biblioteca Tecnica vive en `docs/` y mantiene sus archivos separados de los reportes historicos.

Estructura base:

- `docs/manuales`
- `docs/procedimientos`
- `docs/seguridad`
- `docs/capacitaciones`
- `docs/troubleshooting`

La metadata se registra en SQLite mediante `documentacion_tecnica` con nombre, categoria, fabricante, equipo asociado, version, fecha documental, tipo de documento, palabras clave, criticidad, responsable, descripcion, ruta relativa y metadata fisica del archivo.

La pagina `pages/08_Biblioteca_Tecnica.py` permite filtrar por categoria, fabricante, equipo, criticidad y busqueda textual. Incluye descarga documental, vista de metadata y visor PDF embebido para archivos `.pdf`.

## Flujo operacional completo

1. Se registran datos operacionales desde Streamlit.
2. SQLite recibe el dato como fuente primaria.
3. Excel queda como derivado operativo y respaldo.
4. El dashboard ejecutivo lee desde SQLite.
5. Calidad de datos evalua registros y genera score.
6. Las alertas inteligentes se persisten en SQLite.
7. Las acciones correctivas se derivan y hacen seguimiento sin alterar el historico.
8. La Biblioteca Tecnica consulta metadata documental desde SQLite y archivos desde `docs/`.

## Estabilizacion

La version `v2.3.0` se congela despues de validar:

- dashboard ejecutivo,
- calidad de datos,
- score ejecutivo,
- alertas inteligentes,
- acciones correctivas,
- Biblioteca Tecnica Operacional,
- respaldo estable,
- documentacion actualizada.

Validacion FASE 19:

- `python -m compileall .`: OK.
- `python -m pytest tests -v`: 120 tests passed.
- `python -m streamlit run app_perforacion.py --server.headless=true --server.port=8505`: servidor iniciado correctamente.

## Estado operativo

El sistema queda estable para continuacion de nuevas funcionalidades sin modificar el modelo historico.
