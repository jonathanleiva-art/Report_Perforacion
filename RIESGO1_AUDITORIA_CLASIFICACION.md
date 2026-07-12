# Riesgo 1 — Auditoría: columnas de clasificación en registros_perforacion

**Columnas auditadas:** `tipo_sector`, `numero_precorte`, `identificador_sector`
**Fecha:** 2026-07-12  
**Objetivo:** Mapeo completo de dependencias antes de migrar estas columnas a tabla propia con FK.

---

## 1. Referencias en el código (todos los .py)

### Archivos con referencias — tabla resumen

| Archivo | Rol | Lee | Escribe | Criticidad |
|---|---|:---:|:---:|---|
| `services/clasificacion_operacional_service.py` | Servicio de clasificación | ✓ | ✓ WRITE | **CRÍTICO** — escritura directa con UPDATE |
| `services/report_service.py` | Construcción del payload de INSERT | — | ✓ WRITE | **CRÍTICO** — escribe las 3 columnas en cada registro nuevo |
| `services/malla_avance_service.py` | Motor de avance plan vs real | ✓ | — | **CRÍTICO** — filtra DataFrame por las 3 columnas para calcular avance |
| `pages/04_Gestion_Planos.py` | UI clasificación operacional | ✓ | via service | **CRÍTICO** — panel completo depende de leer estas columnas por fila |
| `pages/25_Editar_Registro.py` | Edición de registro individual | ✓ | via service | **ALTO** — precarga el formulario con tipo_sector y numero_precorte |
| `pages/01_Registro_Operacional.py` | Formulario de ingreso | — | via service | **ALTO** — extrae tipo_sector del widget de sectores y lo pasa a report_service |
| `app_perforacion.py` | Lanzador (inline de registro) | — | via service | **ALTO** — duplica lógica de 01_Registro_Operacional para guardar registro |
| `dashboard.py` | Panel ejecutivo / detalle | ✓ | — | **MEDIO** — usa `_serie_detalle_fase()` que busca `tipo_sector` entre varios alias |
| `pdf_report.py` | Generación de PDF de turno | ✓ | — | **MEDIO** — `_sectores_por_equipo_pdf()` busca la columna por alias fallback |
| `schema.py` | Definición del esquema de columnas | — | — | **MEDIO** — declara las 3 en COLUMNAS_REQUERIDAS y COLUMN_EQUIVALENTS |
| `ui/forms_sections.py` | Widget de ubicación (formulario) | ✓ | — | **BAJO** — solo lee `identificador_sector` como variable local, no SQL |
| `ui/sectores_widget.py` | Widget de sectores por turno | ✓ | — | **BAJO** — compat legacy: lee `numero_precorte` como alias de `numero` |
| `services/enaex_pdf_extraction_service.py` | Extracción de planos ENAEX | — | — | **NINGUNA** — usa los mismos nombres como claves de dict para `sectores_perforacion`, no para `registros_perforacion` |

### Detalle por archivo crítico

#### `services/clasificacion_operacional_service.py`
- `COLUMNAS_CLASIFICACION = ["tipo_sector", "numero_precorte", "identificador_sector"]` — constante central
- `actualizar_clasificacion_registro()` — hace `UPDATE registros_perforacion SET tipo_sector=?, numero_precorte=?, identificador_sector=?` con auditoría en `auditoria_correcciones`
- `resumen_clasificacion()` — lee las 3 columnas del DataFrame para generar estadísticas (con_tipo_sector, precorte_sin_numero, otro_sin_identificador)
- `clasificacion_inferida()` — función derivada: retorna tipo_sector si existe, infiere "Producción" por malla si no

#### `services/report_service.py`
- `construir_datos_registro()` — el payload de INSERT incluye las 3 columnas directamente:
  ```python
  "tipo_sector": tipo_sector,              # desde primer sector del formulario
  "numero_precorte": numero_precorte_op,   # solo si tipo == "Precorte"
  "identificador_sector": identificador_sector,
  ```
- `validar_datos_para_guardado()` — valida que si tipo_sector == "Precorte" haya numero_precorte

#### `services/malla_avance_service.py` ← **LA DEPENDENCIA MÁS COMPLEJA**
- `_filtrar_registros_sector()` — el JOIN implícito más crítico del sistema:
  ```python
  # Para Producción → filtra por malla
  # Para Precorte   → filtra por numero_precorte
  # Para Buffer 1/2 → filtra por tipo_sector
  # Para Borde/Otro → filtra por identificador_sector
  ```
  Este filtro trabaja sobre un DataFrame que viene de `SELECT * FROM registros_perforacion`.  
  Si las columnas se mueven a otra tabla, este SELECT necesita un LEFT JOIN antes de llegar aquí.
- `obtener_registros_por_plan()` — normaliza el DataFrame: renombra alias, llena `tipo_sector` por `_normalizar_tipo_sector_registro()`
- El mapeo de alias (`CAMPO_ALIASES`) también incluye las 3 columnas para compatibilidad con fuentes Excel importadas

#### `pages/04_Gestion_Planos.py`
- Panel de clasificación operacional: lee `tipo_sector`, `numero_precorte`, `identificador_sector` de cada fila del resultado de query para mostrar el formulario de reclasificación
- Tabla de avance: renombra columnas (`"tipo_sector": "Tipo"`, `"numero_precorte": "Precorte"`, `"identificador_sector": "Sector"`)
- Selector de registros sin clasificar: muestra `tipo_sector` actual en el dropdown

#### `dashboard.py`
- `construir_detalle_observaciones_detenciones()` — crea columna "Tipo de sector" buscando entre varios alias incluyendo `"tipo_sector"` (línea 1664). El DataFrame llega desde un SELECT que incluye todas las columnas de `registros_perforacion`.

#### `pdf_report.py`
- `_sectores_por_equipo_pdf()` — busca la primera columna sector disponible en orden: `"Sectores trabajados"`, `"Tipo de perforación"`, `"tipo_sector"`, `"Tipo de sector"`, `"Tipo sector"`. Lee por filas el valor para agrupar el detalle de turno en el PDF.

---

## 2. Clasificación por tipo de uso

### Solo lee (SELECT)
- `services/malla_avance_service.py`
- `services/clasificacion_operacional_service.py` (resumen_clasificacion, clasificacion_inferida)
- `dashboard.py`
- `pdf_report.py`
- `pages/04_Gestion_Planos.py` (visualización)
- `pages/25_Editar_Registro.py` (precarga formulario)

### Escribe directamente en la tabla (INSERT/UPDATE)
- `services/clasificacion_operacional_service.py` → `actualizar_clasificacion_registro()` hace UPDATE
- `services/report_service.py` → `construir_datos_registro()` produce el payload de INSERT

### Escribe indirectamente (pasa datos a servicios de escritura)
- `pages/01_Registro_Operacional.py` → extrae tipo_sector y llama a report_service
- `app_perforacion.py` → mismo patrón
- `pages/04_Gestion_Planos.py` → llama a `clasificacion_operacional_service.actualizar_clasificacion_registro()`
- `pages/25_Editar_Registro.py` → llama al servicio de edición de registros

### Sin dependencia real en registros_perforacion
- `services/enaex_pdf_extraction_service.py` — opera sobre `sectores_perforacion`, no `registros_perforacion`
- `services/malla_service.py` — opera sobre `sectores_perforacion` (tabla del plan, no la flat)
- `ui/sectores_widget.py` — manejo de widget en memoria, sin SQL
- `ui/forms_sections.py` — variable local en formulario, sin SQL

---

## 3. Origen en el schema: ¿columnas fijas o dinámicas?

**Son columnas dinámicas agregadas por ALTER TABLE**, no parte del CREATE TABLE original.

En `db.py` no hay mención a estas columnas. El mecanismo de creación es genérico:

```python
# db.py — mecanismo de ADD COLUMN dinámico
connection.execute(
    f"ALTER TABLE {tabla} ADD COLUMN {columna} TEXT"
)
```

Esto se dispara a partir de `schema.py`, donde las 3 columnas aparecen declaradas en `COLUMNAS_REQUERIDAS` en **tres listas distintas** (líneas 34-36, 130-132, 171-173), correspondientes a tres formatos de fuente Excel importable.

También aparecen en:
- `COLUMN_EQUIVALENTS` (líneas 321-328): mapa de aliases para normalización de nombres al importar Excel (`"Tipo sector"` → `"tipo_sector"`, `"Numero precorte operacional"` → `"numero_precorte"`, etc.)
- `_CAMPO_A_COLUMNAS_EQUIVALENTES` (líneas 421-424): usado por el motor de avance para resolver alias en DataFrames

**Consecuencia clave:** La columna existe en producción porque fue agregada dinámicamente cuando se importó el primer Excel que las incluía o cuando el sistema arrancó por primera vez con el schema nuevo. No hay garantía de que existan en entornos de prueba limpios sin que pase por ese mecanismo.

---

## 4. Registros poblados (dimensionamiento de migración)

**Base total: 245 registros en `registros_perforacion`**

| Columna | Poblados | % | Detalle |
|---|---|---|---|
| `tipo_sector` | **161** | 65.7% | Producción: 140 · Precorte: 11 · Buffer 1: 5 · Buffer 2: 4 · Otro: 1 |
| `numero_precorte` | **11** | 4.5% | Solo registros Precorte (100% de ellos tienen el número) |
| `identificador_sector` | **4** | 1.6% | Muy escaso — solo Otro/Borde |

- Los 84 registros con `tipo_sector = NULL` son **registros históricos** ingresados antes de que existiera el campo o importados desde Excel sin columna de sector.
- Las 3 columnas están en posiciones 67-69 de 74 en el `SELECT *`, confirmando que son las últimas en ser agregadas al esquema.
- En una migración: 161 filas necesitan inserción en la tabla destino; las 84 nulas quedan sin fila en la nueva tabla (equivalente semántico con LEFT JOIN).

---

## 5. JOINs implícitos — dónde rompe si las columnas desaparecen de registros_perforacion

El patrón crítico es este:

```python
# Todos estos lugares hacen SELECT * (o equivalente) y luego filtran/muestran
# tipo_sector en el mismo DataFrame, asumiendo que está en la misma fila.

df = pd.read_sql("SELECT * FROM registros_perforacion WHERE ...", conn)
# ↑ Si tipo_sector ya no está aquí → KeyError en todos los accesos df["tipo_sector"]
```

### Lugares con JOIN implícito que se romperían

1. **`malla_avance_service.obtener_registros_por_plan()`** — hace `SELECT * FROM registros_perforacion WHERE fase=? AND banco=?` y luego en `_filtrar_registros_sector()` filtra `df["tipo_sector"]`, `df["numero_precorte"]`, `df["identificador_sector"]`. **Rompería el cálculo de avance de todas las mallas.**

2. **`clasificacion_operacional_service.resumen_clasificacion()`** — recibe un DataFrame de `registros_perforacion` y accede directamente a `df["tipo_sector"]`, `df["numero_precorte"]`, `df["identificador_sector"]`. **Rompería el panel de clasificación en 04_Gestion_Planos.**

3. **`pdf_report._sectores_por_equipo_pdf()`** — busca `"tipo_sector"` entre las columnas del DataFrame del reporte. Si no la encuentra usa otras como fallback, pero en la práctica hoy siempre cae en `tipo_sector`. **Rompería el PDF de turno para registros Precorte/Buffer.**

4. **`dashboard.construir_detalle_observaciones_detenciones()`** — `_serie_detalle_fase(df, ..., "tipo_sector")` buscará la columna y retornará valores vacíos si no existe (no crash, pero columna "Tipo de sector" siempre vacía en el dashboard).

5. **`pages/25_Editar_Registro.py`** — carga el registro y accede a `registro.get("tipo_sector")`, `registro.get("numero_precorte")`. Con LEFT JOIN serían None en vez de crash, pero el formulario no precargaría los valores.

6. **`pages/04_Gestion_Planos.py`** (panel de clasificación) — accede a `registro.get("tipo_sector")`, `registro.get("numero_precorte")`, `registro.get("identificador_sector")`. Mismo comportamiento.

---

## Lista de archivos a modificar si se migra a tabla propia

Orden de mayor a menor impacto:

### Capa de datos (cambios de SQL y lógica)
1. **`services/clasificacion_operacional_service.py`** — cambiar UPDATE de `registros_perforacion` a INSERT/UPDATE en tabla nueva; cambiar SELECT que carga el DataFrame para incluir LEFT JOIN
2. **`services/report_service.py`** — cambiar payload de INSERT: sacar las 3 columnas del INSERT a `registros_perforacion` y hacer INSERT separado en tabla nueva
3. **`services/malla_avance_service.py`** — cambiar `obtener_registros_por_plan()` para hacer LEFT JOIN antes de devolver el DataFrame; `_filtrar_registros_sector()` no necesita cambios si el JOIN se hace upstream
4. **`db.py`** — agregar CREATE TABLE para la nueva tabla; ajustar o eliminar el ADD COLUMN dinámico para estas 3 columnas
5. **`schema.py`** — eliminar las 3 columnas de `COLUMNAS_REQUERIDAS` (3 apariciones) y de `COLUMN_EQUIVALENTS`; actualizar `sectores_trabajados` en `_CAMPO_A_COLUMNAS_EQUIVALENTES`

### Capa de UI (ajustes de lectura)
6. **`pages/04_Gestion_Planos.py`** — asegurar que el SELECT que alimenta el panel de clasificación incluya JOIN; sin cambios en la lógica de formulario
7. **`pages/25_Editar_Registro.py`** — asegurar que el SELECT del registro incluya JOIN
8. **`pages/01_Registro_Operacional.py`** — sin cambios en lógica; depende de report_service (punto 2)
9. **`app_perforacion.py`** — sin cambios en lógica; depende de report_service (punto 2)

### Capa de reporte
10. **`pdf_report.py`** — el alias fallback ya maneja el caso; verificar que el DataFrame de entrada incluya las columnas via JOIN
11. **`dashboard.py`** — `_serie_detalle_fase` ya degrada gracefully; verificar que el DataFrame incluya las columnas via JOIN

### Tests
12. **`tests/test_clasificacion_operacional_service.py`** — actualizar inserción de fixture para usar nueva tabla
13. **`tests/test_report_service_payload.py`** — verificar que el payload esperado ya no incluya las 3 columnas en el INSERT a `registros_perforacion`
14. **`tests/test_report_service_validaciones.py`** — sin cambios si la validación sigue siendo de negocio
15. **`tests/test_malla_avance_service.py`** — actualizar `_insertar_registro_real()` para no insertar tipo_sector en `registros_perforacion`

---

## Conclusión

La migración no es trivial. Hay **3 capas de acoplamiento**:

- **Capa de escritura** (2 servicios): report_service al insertar + clasificacion_service al corregir → necesitan INSERT a tabla nueva en la misma transacción
- **Capa de lectura con JOIN** (1 servicio crítico + 2 páginas): malla_avance_service es el que más riesgo tiene porque su lógica de filtrado depende de que las 3 columnas estén en el mismo DataFrame que metros y pozos
- **Capa de presentación** (dashboard, PDF): degradan sin crash si el JOIN no está, pero muestran datos vacíos

El camino más seguro es una **migración por fases**:
1. Crear la nueva tabla y poblarla (sin tocar la existente)
2. Hacer que los servicios de escritura escriban en ambas tablas (doble escritura temporal)
3. Cambiar los servicios de lectura para usar JOIN
4. Validar que el avance calculado sea idéntico con y sin las columnas flat
5. Eliminar las columnas de `registros_perforacion`
