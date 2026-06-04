# Sistema de Gestión Operacional de Perforación

Ruta oficial:

`C:\Python_Proyectos\Report_Perforacion`

Versión actual:

`v2.3.0 - Estabilización Biblioteca Técnica Operacional`

## Ejecución

```powershell
cd C:\Python_Proyectos\Report_Perforacion
python -m streamlit run app_perforacion.py
```

También puede iniciarse con:

```powershell
lanzador.bat
```

## Acceso

Las credenciales se configuran en el archivo local `.env`.

```text
REPORT_PERFORACION_ADMIN_USER=Admin Jonathan
REPORT_PERFORACION_ADMIN_PASSWORD=Perforacion
REPORT_PERFORACION_ADMIN_NAME=Admin Jonathan
REPORT_PERFORACION_ADMIN_ROLE=admin
```

Para una instalación nueva, copie `.env.example` como `.env` y cambie la clave.

## Datos Operacionales

Base SQLite principal:

`C:\Python_Proyectos\Report_Perforacion\reportes_perforacion.db`

Excel derivado de exportación y respaldo:

`C:\Python_Proyectos\Report_Perforacion\reportes_perforacion.xlsx`

Directorios principales:

- `reportes_pdf/`: reportes PDF generados.
- `backup/`: respaldos Excel.
- `backups_sqlite/`: respaldos SQLite de migración o mantenimiento.
- `logs/`: auditoría operativa.
- `docs/`: Biblioteca Técnica Operacional.
- `data/`: planos, reportes de operador y archivos auxiliares.

## Módulos Principales

- Inicio y centro de control.
- Registro operacional de turnos.
- Dashboard operacional.
- Reportes PDF.
- Historial y auditoría.
- Alertas operacionales e inteligentes.
- Calidad de datos.
- Avance de malla.
- Acciones correctivas.
- Respaldos y exportación.
- Biblioteca Técnica Operacional.
- Panel ejecutivo.
- Ortomosaico Vista Mina.
- Análisis mensual.

## Tablas SQLite Relevantes

- `registros_perforacion`
- `auditoria_ediciones`
- `alertas_inteligentes`
- `alertas_inteligentes_control`
- `acciones_correctivas`
- `documentacion_tecnica`
- `mallas_avance`
- `pozos_avance`
- `planos_malla_avance`
- `reportes_operador_avance`

## Flujo Operacional

1. Ingresar al sistema con credenciales autorizadas.
2. Registrar datos operacionales desde Streamlit.
3. Validar duplicados por fecha, turno, equipo y operador.
4. Guardar en SQLite como fuente principal.
5. Exportar o respaldar en Excel como derivado operativo.
6. Revisar dashboard, alertas y calidad de datos.
7. Generar reportes PDF.
8. Auditar cambios y hacer seguimiento a acciones correctivas.

## Validación Preventiva

Chequeo ejecutado:

```powershell
python -m pytest
```

Resultado esperado:

```text
173 passed
```

El proyecto fuerza un directorio temporal local para pytest mediante `pytest.ini`, evitando problemas de permisos con el temporal global de Windows.

## Estado Operativo

El sistema queda preparado para operación local en Streamlit, con SQLite como fuente principal, login configurado por `.env`, respaldo/exportación, auditoría, alertas, PDF y módulos de análisis.
