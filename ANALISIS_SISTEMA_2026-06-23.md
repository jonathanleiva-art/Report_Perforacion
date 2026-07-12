# ANÁLISIS EXHAUSTIVO DEL SISTEMA — REPORTE DE PERFORACIÓN
**Fecha de análisis:** 2026-07-11  
**Hora de generación:** 19:55 (hora local)  
**Versión del sistema:** Ver `VERSION.txt` (streamlit==1.57.0, pandas==3.0.1)  
**Analista:** Claude Code (solo lectura — ningún archivo fue modificado)

---

## SECCIÓN 1 — INVENTARIO GENERAL

### 1a) Estructura de archivos

**Archivos Python en raíz (selección de módulos core):**

| Archivo | Líneas |
|---------|--------|
| `dashboard.py` | 2.150 |
| `db.py` | 1.836 |
| `pdf_report.py` | 1.173 |
| `app_perforacion.py` | 781 |
| `schema.py` | 515 |
| `data.py` | 499 |
| `charts.py` | 695 |
| `utils.py` | 5.722 bytes (≈200 líneas útiles) |

**Archivos de configuración:**

- `requirements.txt` — existe, 9 líneas
- `pyproject.toml` — **NO existe**
- `setup.py` — **NO existe**
- `.streamlit/config.toml` — **NO existe** (sin directorio `.streamlit/`)
- `.env` — existe (224 bytes)

**Dependencias extraídas de `requirements.txt`:**

```
streamlit==1.57.0
pandas==3.0.1
openpyxl==3.1.5
plotly==6.7.0
reportlab==4.4.9
matplotlib==3.10.9
Pillow==12.2.0
PyMuPDF==1.27.2.3
bcrypt>=4.0.0
```

Python requerido: no especificado en requirements.txt (no hay `pyproject.toml`). Los `.pyc` usan `cpython-314`, indicando **Python 3.14**.

**Directorio `services/` — 26 archivos de servicio:**

```
alert_service.py, backup_service.py, catalog_service.py, ciclos_service.py,
clasificacion_operacional_service.py, corrective_actions_service.py,
data_quality_service.py, data_source_selector_service.py, documentation_service.py,
enaex_pdf_extraction_service.py, executive_service.py, export_service.py,
import_diagnostic_service.py, import_execution_service.py, kpi_service.py,
malla_avance_service.py, malla_service.py (2.662 líneas), monthly_service.py,
operational_excel_query_service.py, operational_excel_service.py,
operator_admin_service.py, ortomosaico_service.py, report_service.py,
smart_alerts_service.py, source_adapter_service.py, source_routing_helpers.py,
source_service.py, ubicacion_service.py
```

**Directorio `ui/` — 15 módulos:**

```
alerts_view.py, auth.py, components.py, data_source.py, data_status.py,
filters.py, form_helpers.py, formatting.py, forms_sections.py, home.py,
ortomosaico_ui.py, page_header.py, pdf_section.py, sectores_widget.py, theme.py
```

**Directorio `tests/` — 55 archivos de test**

---

### 1b) Páginas activas

22 páginas encontradas en `pages/`:

| # | Archivo | Líneas |
|---|---------|--------|
| 1 | `04_Gestion_Planos.py` | 1.317 |
| 2 | `05_Ortomosaico_Vista_Mina.py` | 1.147 |
| 3 | `03_Avance_Operacional.py` | 985 |
| 4 | `25_Editar_Registro.py` | 652 |
| 5 | `17_Edicion_Controlada_Auditoria.py` | 447 |
| 6 | `12_Calidad_Datos.py` | 434 |
| 7 | `01_Registro_Operacional.py` | 389 |
| 8 | `09_Analisis_Mensual.py` | 281 |
| 9 | `20_Administrar_Fuentes_Excel.py` | 278 |
| 10 | `22_Importar_Excel.py` | 276 |
| 11 | `10_Dashboard_Excel_Operacional.py` | 239 |
| 12 | `06_Alertas_Operacionales.py` | 236 |
| 13 | `18_Respaldos_Exportacion.py` | 227 |
| 14 | `11_Alertas_Inteligentes.py` | 197 |
| 15 | `08_Panel_Ejecutivo.py` | 187 |
| 16 | `24_Alertas_Registros.py` | 168 |
| 17 | `21_Fuentes_Datos.py` | 158 |
| 18 | `16_Auditoria_Historial.py` | 157 |
| 19 | `19_Administracion_Operadores.py` | 78 |
| 20 | `23_Administracion_Catalogos.py` | 74 |
| 21 | `07_Reportes_PDF.py` | 74 |
| 22 | `02_Dashboard_Operacional.py` | 54 |

**Páginas eliminadas (en gitStatus como borradas):**  
`13_Acciones_Correctivas.py`, `14_Biblioteca_Tecnica.py`, `15_Machine_Learning.py`

**Páginas nuevas (no commiteadas aún):**  
`24_Alertas_Registros.py`, `25_Editar_Registro.py`

---

### 1c) Tamaño de la BD y registros por tabla

**Resultado del script ejecutado:**

```
Tamaño BD: 13.6 MB
```

| Tabla | Filas |
|-------|-------|
| `registros_perforacion` | **245** |
| `ciclos_perforacion` | **6.669** |
| `registros_excel_operacional` | **9.707** |
| `alertas_inteligentes` | **691** |
| `operadores` | **22** |
| `auditoria_ediciones` | **36** |
| `reportes` (legacy) | **50** |
| `acciones_correctivas` | **3** |
| `avance_malla` | **212** |
| `archivos_planos_malla` | **7** |
| `planes_perforacion` | **7** |
| `mallas_plano` | **4** |
| `biblioteca_documentos` | **4** |
| `fuentes_datos` | **2** |
| `alertas_inteligentes_control` | **2** |
| `pozos_malla_control` | **1** |
| `auditoria_planos_malla` | **21** |
| `sectores_perforacion` | **1** |
| `sqlite_sequence` | **19** |
| Resto de tablas (mallas_avance, pozos_avance, etc.) | **0** |

**Observación importante:** La tabla `equipos` está vacía (0 filas), aunque el sistema usa `catalog_service.FLOTA_EQUIPOS` como lista hardcoded.

---

## SECCIÓN 2 — SALUD DE LA BASE DE DATOS

### 2a) Duplicados en `registros_perforacion`

```sql
SELECT "Fecha turno", Turno, "Número equipo", Operador, COUNT(*) as n
FROM registros_perforacion
WHERE "Fecha turno" IS NOT NULL
GROUP BY "Fecha turno", Turno, "Número equipo", Operador
HAVING COUNT(*) > 1
ORDER BY n DESC LIMIT 20
```

**Resultado: 0 duplicados encontrados.** La tabla no tiene registros duplicados por la combinación fecha+turno+equipo+operador.

---

### 2b) Reportes faltantes (últimos 30 días al 2026-07-11)

**Análisis de cobertura con 6 equipos (`9245`, `9259`, `9272`, `9274`, `9277`, `9339`) y 2 turnos (`Día`/`Noche`) desde 2026-06-11:**

```
Combinaciones posibles:  372  (31 días × 6 equipos × 2 turnos)
Combinaciones existentes: 160
Combinaciones faltantes:  212  (57% sin registro)
```

**Primeros 20 faltantes detectados:**

```
('2026-06-15', '9259', 'Día')
('2026-06-23', '9339', 'Día')
('2026-06-24', '9245', 'Noche')
('2026-06-24', '9259', 'Noche')
('2026-06-24', '9272', 'Noche')
('2026-06-24', '9274', 'Noche')
('2026-06-24', '9277', 'Noche')
('2026-06-24', '9339', 'Noche')
('2026-06-25', '9245', 'Día') ... todos los equipos del 25 en adelante
```

**Interpretación:** Los datos de `registros_perforacion` llegan hasta el 2026-06-24 (turno Día). A partir de la fecha 2026-06-25 en adelante no hay registros de SQLite oficial, pero pueden existir en `registros_excel_operacional` (9.707 filas). La cobertura 2026-06-11 a 2026-06-24 es prácticamente completa (con excepción de algunos turnos puntuales como `9339 Día 2026-06-23`).

---

### 2c) Consistencia de operadores

**Códigos encontrados en `registros_perforacion` vs tabla `operadores`:**

| Código en registros | Nombre | En tabla `operadores` |
|--------------------|---------|-----------------------|
| `002036` | Carlos Rondon | Sí |
| `002268` | Diego Huerta | Sí |
| `005925` | Henry Latus | Sí |
| `007494` | Jhon Tapia | Sí |
| `008086` | Jonathan Leiva | Sí |
| `009234` | Diego Aracena | Sí |
| `009464` | Jhan Calderon | Sí |
| `009608` | Nicolas Torres | Sí |
| `009939` | Mauricio Mora | Sí |
| `203528` | Tereza Inostroza | Sí |
| `203529` | Valeria Millan | Sí |
| `203666` | Martina Díaz | Sí |
| `204167` | Matías Toro | Sí |
| **`94964`** | Jhan Calderon | **NO** |
| **`M-203529`** | Valeria Millan | **NO** |
| **`M-2036`** | Carlos Rondon | **NO** |
| **`M-204167`** | Nicolas Torres / Matías Toro (ambos) | **NO** |
| **`M-8086`** | Jonathan Leiva | **NO** |
| **`M-9464`** | Jhan Calderon | **NO** |
| **`M-9608`** | Nicolas Torres | **NO** |
| **`M-9698`** | Nicolas Torres | **NO** |
| **`M-9939`** | Mauricio Mora | **NO** |

**Problemas detectados:**
1. **9 códigos con prefijo `M-` no existen en la tabla `operadores`** — son códigos legados del sistema Excel original, no normalizados.
2. **Código `94964` es un duplicado de `009464`** (Jhan Calderon) — posiblemente ingresado sin relleno de ceros.
3. **`M-204167` asociado a dos personas diferentes** (Nicolas Torres con 1 registro y Matías Toro con 14) — inconsistencia de código/nombre.

---

### 2d) Consistencia de Banco/Malla/Fase

**Valores únicos encontrados en `registros_perforacion`:**

**Banco (10 valores únicos):**
```
'2280', '2296', '2312', '2328', '2328, 2296', '2344', '2360', '2360, 2280',
'2376', '2392'
```

**Malla (30+ valores únicos, muestra):**
```
'103', '107', '108', '108, 109', '108, 109, 114', '109', '109, 113',
'110', '110, 107', '113, 114', '114', '117, 118, 119', '119', '122', ...
```

**Fase (4 valores únicos):**
```
'1', '1, 2', '2', '2, 1'
```

**Observaciones:**
- Los valores de Banco, Malla y Fase contienen **entradas compuestas separadas por coma** (`'108, 109, 114'`), lo que es la razón por la que `db.obtener_valores_distintos_columna()` y `ui/filters.py` aplican splitting CSV para obtener tokens individuales. La BD almacena texto libre, no normaliza a filas.
- El valor `'2, 1'` en Fase es semánticamente igual a `'1, 2'` pero son tokens distintos que el `arbol_ubicacion` de `ubicacion_service.py` trataría diferente.
- Los bancos son todos numéricos (`2280`, `2296`, etc.) sin labels descriptivos.

---

## SECCIÓN 3 — BUGS CONOCIDOS PENDIENTES

### 3a) Bug selector Banco con valores numéricos crudos

**Análisis de `ui/filters.py` línea 298:**

```python
filtro_bancos = st.multiselect("Banco", bancos, default=bancos, key="dashboard_bancos")
```

**No existe `format_func`** en el multiselect de Banco. La función `_etiqueta_operador` se usa para Operadores (línea 288), y `texto_visible` para Turnos (línea 290), pero el selector Banco muestra directamente los valores numéricos brutos (ej: `'2280'`, `'2328, 2296'`).

**Cómo se construyen las opciones de Banco (línea 270):**
```python
bancos = _serie_opciones_split(df_opciones, "Banco") if usar_excel \
         else (_opciones_desde_sql("Banco") or _serie_opciones_split(df, "Banco"))
```

`_opciones_desde_sql("Banco")` llama a `db.obtener_valores_distintos_columna("Banco")` que aplica el splitting CSV en líneas 908-916 de `db.py`, devolviendo valores individuales (`'2280'`, `'2296'`...).

**Veredicto:** Los bancos se muestran como números crudos sin ninguna etiqueta descriptiva. No hay función de formato. Esto es un problema de UX ya que los operadores no tienen contexto sobre qué banco es `2280`. **No es un crash, sino una UX degradada**.

En `pages/16_Auditoria_Historial.py` línea 53-58, el selector Banco tampoco tiene `format_func`:
```python
banco = app.st.multiselect(
    "Banco",
    db.obtener_valores_distintos_columna("Banco"),
    format_func=texto_visible,   # solo wrapping para encoding, no descripción
    key="historial_banco",
)
```

---

### 3b) Try/except amplios en código del proyecto

**Total de `except Exception: pass/return` en archivos del proyecto (excluido `.venv`): 32**

Más críticos (ocultan errores silenciosamente):

| Archivo | Línea | Tipo |
|---------|-------|------|
| `app_perforacion.py` | 129 | `except Exception: return` |
| `dashboard.py` | 231, 539 | `except Exception: return` |
| `dashboard.py` | 985 | `except Exception: pass` |
| `data.py` | 498 | `except Exception: pass` |
| `pages/03_Avance_Operacional.py` | 231 | `except Exception: return` |
| `pages/04_Gestion_Planos.py` | 948, 974 | `except Exception: return/pass` |
| `pages/05_Ortomosaico_Vista_Mina.py` | 32, 48 | `except Exception: return` |
| `pages/25_Editar_Registro.py` | 101, 124, 185, 204, 259, 601 | 6 instancias |
| `ui/auth.py` | 40 | `except Exception: return` |
| `ui/filters.py` | 180 | `except Exception: return` |
| `services/backup_service.py` | 165, 184 | `except Exception: return` |

**El caso más grave:** `pages/25_Editar_Registro.py` tiene **6 except silenciosos**, siendo una página nueva no commiteada que maneja edición de registros críticos operacionales.

---

### 3c) Logs de error

**`logs/audit_log.csv` — existe y tiene datos.**

- Primeras entradas: 2026-05-25 (inicio de operación real)
- Última actividad real: 2026-07-03

**Errores críticos detectados en audit_log.csv (2026-07-03):**

```
2026-07-03T00:41:25,guardado_excel,,,,,error,[Errno 13] Permission denied: '...reportes_perforacion.xlsx'
2026-07-03T00:46:20,guardado_excel,,,,,error,[Errno 13] Permission denied: '...reportes_perforacion.xlsx'
2026-07-03T00:53:20,guardado_excel,,,,,error,[Errno 13] Permission denied: '...reportes_perforacion.xlsx'
... (7 errores consecutivos el 2026-07-03)
```

**Patrón:** El archivo `reportes_perforacion.xlsx` estaba abierto (bloqueado por Excel u otro proceso) cuando el sistema intentó escribir. Esto ocurrió 7 veces seguidas pero los registros en SQLite se guardaron correctamente (acción `creacion_reporte` con resultado `ok` después de cada error).

**Archivos `.log` en el proyecto:** 31 archivos `streamlit_*.log` en la raíz. El más reciente y relevante: `streamlit_current_err.log` (483 KB).

**Errores en `streamlit_current_err.log`:**

1. `Please replace st.components.v1.html with st.iframe` — advertencia de deprecación (línea 2, repetida decenas de veces)
2. `Please replace use_container_width with width` — deprecación masiva: **37 ocurrencias en 11 archivos**
3. Ningún crash de excepción Python detectado en el log actual.

---

## SECCIÓN 4 — CALIDAD DE CÓDIGO

### 4a) Constantes duplicadas

**`FLOTA_EQUIPOS`** — definida una vez, bien importada:
```python
# services/catalog_service.py:18
FLOTA_EQUIPOS = ["9245", "9259", "9272", "9274", "9277", "9339"]
```
Importada desde: `app_perforacion.py`, `services/alert_service.py`, `pages/25_Editar_Registro.py`, `pages/17_Edicion_Controlada_Auditoria.py`, `pages/06_Alertas_Operacionales.py`, `tests/test_reportes_faltantes_service.py`. **Sin duplicados.**

**`color_estado_operacional`** — definida solo una vez:
```python
# utils.py:135
def color_estado_operacional(estado): ...
```
Importada en `app_perforacion.py`. No hay definiciones duplicadas.

**`DETENCION_HORAS_COLUMNAS`** — definida solo una vez:
```python
# utils.py:114
DETENCION_HORAS_COLUMNAS = { ... }
```
No hay duplicados.

**Observación:** La arquitectura de constantes es correcta. No hay duplicados críticos detectados.

**Problema de encoding en `ui/filters.py`:** Hay cadenas de texto con encoding roto en el código fuente (no en la BD):
```python
"Tipo de perforaciÃƒÂ³n"  # línea 142
"Tipo detenciÃ³n"          # línea 160, 292, 376
"Tipo de perforaciÃ³n"     # línea 273
```
Estas son strings UTF-8 mal decodificadas como Latin-1 que quedaron en el código. En producción pueden no matchear los nombres reales de columna.

---

### 4b) Funciones muy largas

**Top 15 funciones más largas en el proyecto (excluido `.venv`):**

| Líneas | Archivo | Función | Línea inicio |
|--------|---------|---------|--------------|
| 570 | `pages/03_Avance_Operacional.py` | `main()` | 412 |
| 500 | `pages/05_Ortomosaico_Vista_Mina.py` | `_generar_editor_completo_html()` | 426 |
| 344 | `dashboard.py` | `dashboard()` | 1.806 |
| 286 | `services/malla_service.py` | `asegurar_tablas()` | 228 |
| 263 | `services/data_quality_service.py` | `evaluar_calidad_datos()` | 154 |
| 261 | `pages/01_Registro_Operacional.py` | `_formulario_wizard()` | 17 |
| 253 | `pdf_report.py` | `generar_pdf()` | 920 |
| 236 | `dashboard.py` | `_render_graficos_tendencia()` | 1.074 |
| 235 | `app_perforacion.py` | `formulario_registro()` | 424 |
| 231 | `pages/12_Calidad_Datos.py` | `generar_excel_calidad()` | 117 |
| 220 | `pages/05_Ortomosaico_Vista_Mina.py` | `_generar_editor_fullscreen_html()` | 203 |
| 210 | `pages/05_Ortomosaico_Vista_Mina.py` | `main()` | 934 |
| 197 | `ui/filters.py` | `aplicar_filtros()` | 201 |
| 189 | `ui/auth.py` | `aplicar_estilo_login()` | 128 |
| 178 | `services/report_service.py` | `validar_datos_para_guardado()` | 46 |

**Funciones críticas por tamaño:**
- `main()` en `03_Avance_Operacional.py` con 570 líneas es una función monolítica que debería dividirse.
- `generar_pdf()` en `pdf_report.py` con 253 líneas construye todo el story del PDF secuencialmente.
- `asegurar_tablas()` en `malla_service.py` con 286 líneas define el schema SQL completo inline.

---

### 4c) Imports sospechosos

**`app_perforacion.py`** (imports líneas 1-23):
```python
import sqlite3     # usado en líneas internas de funciones
import html        # uso en escape() — OK
from schema import columnas_equivalentes  # verificar si se usa
```
`columnas_equivalentes` se importa pero requiere verificación de uso en el resto del archivo.

**`db.py`** — importa `pandas`, `pathlib`, módulos de cache internos. Sin imports evidentemente sobrantes.

**`pdf_report.py`** — importa `kpi_service`, `audit_log`, `services.catalog_service`, `charts`. Todos parecen usados.

---

### 4d) Archivos .pyc

```
Total .pyc en proyecto (excluido .venv): 97 archivos
```

Distribuidos en `__pycache__/` de: raíz, `ui/`, `services/`, `pages/`, `tests/`, `validation/`, `audit/`. Son compilados normales de Python 3.14. No necesitan atención.

---

## SECCIÓN 5 — CONSISTENCIA UI/UX

### 5a) Tema aplicado

**Mecanismo de tema:** `ui/theme.py` define `aplicar_tema_profesional()` que:
1. Lee `assets/styles.css` (tema industrial oscuro #0d0e10 / naranja #E67E22 / fuente Barlow)
2. Inyecta el CSS via `st.markdown(unsafe_allow_html=True)`
3. Inyecta `assets/ui_effects.js` via `components.html` (que genera la advertencia de deprecación)
4. Fuerza visibilidad del sidebar nav

**`ui/page_header.py`** llama `aplicar_tema_profesional()` en cada `render_page_header()`.

**Páginas que aplican el tema correctamente** (todas las que llaman `render_page_header`): **22 de 22 páginas**. Todas importan y llaman `render_page_header` desde `ui.page_header`.

**Páginas con CSS/tema propio adicional** (además del theme global):
- `app_perforacion.py` — tiene CSS inline en `formulario_registro()`
- `pdf_report.py` — tiene tema propio dentro del PDF (colores HexColor hardcoded)
- `charts.py` — colores hardcoded para gráficos Plotly

**Archivos que referencian `#0d0e10`, `#E67E22`, `Barlow` directamente en código Python:**
```
pdf_report.py, pages/01_Registro_Operacional.py, pages/25_Editar_Registro.py,
dashboard.py, app_perforacion.py, pages/24_Alertas_Registros.py,
pages/03_Avance_Operacional.py, charts.py
```
8 archivos tienen referencias directas — es decir, si se cambia el tema en `styles.css`, estos archivos quedarían desincronizados visualmente.

---

### 5b) Filtros de Banco/Malla/Fase — comparación entre módulos

| Módulo | Implementación | Usa `ubicacion_service` | Lógica CSV-split |
|--------|---------------|------------------------|------------------|
| `ui/filters.py` (dashboard sidebar) | `_serie_opciones_split()` propia + `db.obtener_valores_distintos_columna()` | NO | Sí (propia) |
| `ui/pdf_section.py` (filtros PDF cascada) | `ubicacion_service.valores_unicos()`, `opciones_banco_cascada()`, `opciones_malla_cascada()` | **SÍ** | Sí (via service) |
| `pages/16_Auditoria_Historial.py` | `db.obtener_valores_distintos_columna()` con `format_func=texto_visible` | NO | Sí (via db.py) |
| `pages/17_Edicion_Controlada_Auditoria.py` | `db.obtener_valores_distintos_columna("Área operacional")` para ese campo; Banco/Malla/Fase se editan como text_input libre | NO | NO (campo libre) |

**Inconsistencias detectadas:**

1. **`ui/pdf_section.py` usa correctamente `ubicacion_service`** con filtros en cascada (Fase → Banco → Malla). Es la implementación más completa.

2. **`ui/filters.py` (dashboard)** duplica la lógica de splitting CSV con `_serie_opciones_split()` sin usar `ubicacion_service`. No tiene cascada; los tres filtros son independientes.

3. **`pages/16_Auditoria_Historial.py`** usa `db.obtener_valores_distintos_columna("Banco")` directamente, que también hace splitting en `db.py:908-916`. Sin cascada.

4. **`pages/17_Edicion_Controlada_Auditoria.py`** edita Banco/Malla/Fase como `text_input` libre (línea 292 del archivo), sin selector. Esto permite ingresar valores no normalizados que luego aparecen en la BD como strings compuestos no estándar.

**Conclusión:** Hay tres implementaciones paralelas del mismo concepto (splitting de CSV en Banco/Malla/Fase). Solo `pdf_section.py` usa el `ubicacion_service` canónico.

---

## SECCIÓN 6 — MÓDULO DE REPORTES PDF

### 6a) Estado de las secciones nuevas

**`_seccion_ubicacion_pdf()`** — existe en `pdf_report.py` línea 844:
- Filtra filas donde todos los campos ubicación (Banco, Fase, Malla) están vacíos
- Expande mallas múltiples CSV en filas individuales usando `_split_csv()`
- Genera combinaciones cartesianas Banco×Fase×Malla
- Muestra tabla "Ubicación Operacional" con 6 columnas

**`_seccion_observaciones_pdf()`** — existe en `pdf_report.py` línea 883:
- Itera los campos: `'Condición del terreno'`, `'Observaciones'`, `'Observación estado equipo'`
- Filtra correctamente valores vacíos/nan (línea 898: `if val and val.lower() not in ("nan", "none", "nat")`)
- Genera tabla "Observaciones de Terreno" con 5 columnas
- Si solo hay el header (len(filas) <= 1), retorna silenciosamente sin mostrar nada

**Inserción dentro de `generar_pdf()` (líneas 1145-1146):**
```python
_seccion_ubicacion_pdf(df_reporte, story, styles)       # línea 1145
_seccion_observaciones_pdf(df_reporte, story, styles)    # línea 1146
```
Se insertan **después** de `PageBreak()` (línea 1143) y **antes** de los gráficos operacionales (línea 1148). El flow es correcto: primera página con KPIs/rankings, segunda página con ubicación + observaciones + gráficos.

---

### 6b) Alineación con BD

**Verificación de columnas PDF contra `registros_perforacion`:**

```
OK  Banco
OK  Malla
OK  Fase
OK  Observaciones
OK  Descripción avería equipo
OK  Observación estado equipo
OK  Condición del terreno
OK  Número equipo
OK  Metros perforados
OK  Horas efectivas perforando
OK  Disponibilidad %
OK  Utilización
```

**Todas las 12 columnas requeridas por el PDF existen en la tabla.** No hay desalineación.

**Columnas adicionales en la tabla no usadas por el PDF** (selección):
- `tipo_sector`, `numero_precorte`, `identificador_sector`, `operador_codigo`, `operador_nombre`, `sectores_json`, `Sectores trabajados` — campos del módulo de sectores, no incluidos en el PDF.

---

## SECCIÓN 7 — RENDIMIENTO

### 7a) Índices de la BD

**Total de índices en `reportes_perforacion.db`: 43**

**Índices en `registros_perforacion` (tabla principal):**

| Índice | Columna(s) |
|--------|-----------|
| `idx_registros_fecha_turno` | `"Fecha turno"` |
| `idx_registros_turno` | `"Turno"` |
| `idx_registros_numero_equipo` | `"Número equipo"` |
| `idx_registros_operador` | `"Operador"` |
| `idx_registros_banco` | `"Banco"` |
| `idx_registros_malla` | `"Malla"` |
| `idx_registros_fecha_turno_turno_equipo_operador` | Compuesto (4 columnas) |

**Índices en otras tablas críticas:**
- `alertas_inteligentes`: fecha, estado, equipo, operador
- `ciclos_perforacion`: id_fuente, único (ident_registro, id_fuente)
- `registros_excel_operacional`: id_fuente, único (5 columnas)
- `acciones_correctivas`: fecha, estado, equipo, responsable
- `auditoria_ediciones`: registro_id, changed_at

---

### 7b) Columnas sin índice usadas en filtros

**Columnas en WHERE que NO tienen índice dedicado:**

| Columna | Uso en WHERE | Índice existente |
|---------|-------------|-----------------|
| `Fase` | Sí (en `consultar_historial_filtrado`) | **NO** |
| `Código operador` | Sí (búsqueda de operador por código) | **NO** |
| `Modelo equipo` | Sí (filtro historial) | **NO** |
| `Tipo detención` | Sí (filtro tipos detención) | **NO** |
| `Tipo de perforación` | Sí (filtro dashboard) | **NO** |

**Columnas con índice que sí se usan en filtros:**
`Fecha turno` ✓, `Turno` ✓, `Número equipo` ✓, `Operador` ✓, `Banco` ✓, `Malla` ✓

**Nota:** Con solo 245 filas actuales en `registros_perforacion`, la falta de índice en `Fase` no impacta el rendimiento. El impacto potencial está en `registros_excel_operacional` (9.707 filas) y `ciclos_perforacion` (6.669 filas), pero esas tablas tienen sus propios índices de fuente.

---

### 7c) Funciones con `@cache_data`

**Total de funciones cacheadas en el proyecto: 26**

| Archivo | Cantidad | Funciones cacheadas (muestra) |
|---------|----------|------------------------------|
| `db.py` | 14 | `leer_registros`, `consultar_historial_filtrado`, `obtener_rango_fechas`, `obtener_valores_distintos_columna`, `consultar_alertas_operacionales_filtradas`, `consultar_resumen_operacional_equipos_filtrado`, etc. |
| `data.py` | 2 | 2 funciones de carga |
| `services/ortomosaico_service.py` | 3 | `@st.cache_data` |
| `services/monthly_service.py` | 2 | `@st.cache_data` |
| `services/malla_service.py` | 1 | `@st.cache_data` |
| `ui/data_status.py` | 1 | `@st.cache_data(show_spinner=False)` |
| `db.py` (resource) | 1 | `@cache_resource` (conexión DB) |

**Uso de `@cache_resource` en `db.py` línea 144:** La función de conexión a la BD está cacheada como recurso, lo que es correcto para gestión de conexiones SQLite.

**Funciones sin cache que podrían beneficiarse:**
- `services/kpi_service.py` — no tiene ninguna función cacheada a pesar de calcular KPIs desde DataFrames completos
- `services/data_quality_service.py` — `evaluar_calidad_datos()` (263 líneas) se ejecuta sin cache

---

## SECCIÓN 8 — ROADMAP PRIORIZADO

| Prioridad | Acción | Impacto | Esfuerzo estimado | Archivos afectados |
|-----------|--------|---------|-------------------|--------------------|
| **ALTA** | Migrar 37 instancias de `use_container_width` a `width='stretch'` (deprecado tras 2025-12-31, ya pasado) | Puede romper la UI en versiones futuras de Streamlit | 1-2 horas | `dashboard.py`, `pages/03`, `01`, `04`, `05`, `09`, `ui/filters.py`, `sectores_widget.py`, `ortomosaico_ui.py` |
| **ALTA** | Reemplazar `st.components.v1.html` por `st.iframe` en `ui/theme.py:27` (deprecado tras 2026-06-01, ya pasado) | Generará error en próximas versiones de Streamlit | 30 min | `ui/theme.py` |
| **ALTA** | Normalizar los 9 códigos de operador con prefijo `M-` y el duplicado `94964` en `registros_perforacion` | Reportes de operadores inconsistentes, búsquedas fallidas | 2-3 horas (migración SQL + script) | `db.py`, `services/operator_admin_service.py`, scripts de migración |
| **ALTA** | Corregir strings con encoding roto en `ui/filters.py` líneas 142, 160, 273, 292, 376 (`Tipo de perforaciÃ³n`, `Tipo detenciÃ³n`) | Filtros de tipo de perforación y detención no funcionan correctamente contra BD | 1 hora | `ui/filters.py` |
| **MEDIA** | Resolver error recurrente de `Permission denied: reportes_perforacion.xlsx` (7 errores el 2026-07-03) | Pérdida silenciosa de exportación a Excel cada vez que el archivo está abierto | 2 horas | `services/export_service.py`, `db.py` — implementar escritura a archivo temporal y rename |
| **MEDIA** | Unificar la lógica de filtros Banco/Malla/Fase usando `ubicacion_service` en todos los módulos | Comportamiento inconsistente entre dashboard, historial y PDF | 3-4 horas | `ui/filters.py`, `pages/16_Auditoria_Historial.py`, `pages/17_Edicion_Controlada_Auditoria.py` |
| **MEDIA** | Agregar `format_func` descriptivo para el selector Banco (mostrar etiqueta `"Banco 2280"` en lugar de `"2280"` crudo) | UX degradada para operadores que no memorizan números de banco | 30 min | `ui/filters.py`, `pages/16_Auditoria_Historial.py` |
| **MEDIA** | Refactorizar las 6 funciones con >250 líneas (especialmente `main()` en `03_Avance_Operacional.py` con 570 líneas) | Mantenibilidad, testing y debugging muy dificultados | 1-2 días por función | `pages/03_Avance_Operacional.py`, `dashboard.py`, `services/malla_service.py` |
| **BAJA** | Agregar índice en columna `Fase` de `registros_perforacion` | Sin impacto hoy (245 filas), preventivo para escala | 15 min | `db.py` (en `crear_tablas()`) o script SQL directo |
| **BAJA** | Agregar `@cache_data` a `kpi_service.py` y `data_quality_service.py` | Mejora de rendimiento en recargas del dashboard | 1 hora | `services/kpi_service.py`, `services/data_quality_service.py` |
| **BAJA** | Eliminar archivos `compileall_*.log` y `streamlit_fase*.log` de la raíz (20+ archivos) | Limpieza del repositorio | 15 min | `.gitignore`, raíz del proyecto |
| **BAJA** | Añadir `python_requires` en un `pyproject.toml` para fijar Python 3.14 | Reproducibilidad del entorno | 30 min | Crear `pyproject.toml` |

---

## RESUMEN EJECUTIVO

**Sistema:** Aplicación Streamlit operacional de perforación minera.  
**Estado general:** Funcional en producción, sin crashes activos, buena cobertura de tests (55 archivos).

### 3 problemas más urgentes:

**1. DEPRECACIONES STREAMLIT BLOQUEANTES (plazo vencido)**  
`use_container_width` (37 instancias, deprecado 2025-12-31) y `st.components.v1.html` (1 instancia, deprecado 2026-06-01) ya superaron su fecha límite. En la próxima actualización de Streamlit, la UI puede quebrarse silenciosamente o generar errores. Prioridad inmediata antes de actualizar Streamlit.

**2. INCONSISTENCIA DE CÓDIGOS DE OPERADOR**  
9 códigos con prefijo `M-` (legado Excel) y 1 código `94964` duplicado de `009464` no están normalizados en la tabla `operadores`. Esto hace que los filtros por operador en el dashboard devuelvan resultados incompletos y los reportes de rendimiento por operador mezclen datos. Un operador (Jhan Calderon) aparece bajo 3 códigos distintos.

**3. ERROR RECURRENTE `Permission denied` EN EXPORTACIÓN XLSX**  
Cada vez que `reportes_perforacion.xlsx` está abierto en Excel, el sistema falla silenciosamente en escribir el backup automático (7 errores documentados el 2026-07-03). El registro en SQLite sí se guarda, pero el operador que tiene el Excel abierto bloquea todos los guardados simultáneos. La solución es escribir a un archivo temporal y hacer rename atómico.

---

*Informe generado el 2026-07-11 mediante análisis estático de solo lectura. Total de archivos analizados: 22 páginas, 28 servicios, 15 módulos UI, 66 archivos de test, 3 tablas BD principales con 245+9.707+6.669 registros.*
