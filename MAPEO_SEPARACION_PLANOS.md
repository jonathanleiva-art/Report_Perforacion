# Mapeo de Dependencias — Separación de Gestión de Planos y Ortomosaico

**Fecha:** 2026-07-12  
**Alcance:** `pages/04_Gestion_Planos.py` y `pages/05_Ortomosaico_Vista_Mina.py`  
**Estado:** Solo lectura — no se ha movido ni modificado ningún archivo  

---

## Índice

1. [Tablas de BD que leen/escriben](#1-tablas-de-bd)
2. [Tablas de referencia (solo lectura desde sistema principal)](#2-tablas-de-referencia)
3. [Funciones y constantes de módulos compartidos](#3-funciones-y-constantes-compartidas)
4. [Archivos físicos exclusivos](#4-archivos-físicos-exclusivos)
5. [Módulos del sistema principal que dependen de estos módulos](#5-dependencias-inversas)
6. [Clasificación final: mover / duplicar / sincronizar / riesgos](#6-clasificación-final)

---

## 1. Tablas de BD

### 1.1 — `pages/04_Gestion_Planos.py`

Todas las operaciones sobre tablas propias pasan por `services/malla_service.py`.

| Tabla | Operación | Descripción |
|---|---|---|
| `archivos_planos_malla` | R/W | Metadatos de PDFs de planos cargados (nombre, hash, fecha, ruta física) |
| `pozos_malla_control` | R/W | Pozos individuales de la malla de control (tipo, estado, coordenadas) |
| `planes_perforacion` | R/W | Planes de perforación (nombre, fase, banco, fechas) |
| `sectores_perforacion` | R/W | Sectores de un plan (tipo, metros planificados, estado) |
| `auditoria_planos_malla` | R/W | Historial de acciones sobre archivos de planos |
| `auditoria_sectores_perforacion` | R/W | Historial de cambios en sectores (quién, cuándo, qué cambió) |
| `mallas_avance` | R/W | Mallas históricas de avance (legacy/histórico) |
| `pozos_avance` | R/W | Pozos en mallas históricas |
| `planos_malla` | R/W | Planos históricos (legacy) |
| `pozos_plano_avance` | R/W | Pozos en planos históricos |
| `reportes_operador_avance` | R/W | Reportes fotográficos de operadores (legacy) |
| `pozos_reporte_operador_avance` | R/W | Pozos en reportes de operadores |
| `archivos_reportes_operador` | R/W | Metadatos de fotos/reportes cargados |
| `registros_perforacion` | **R+W** | **TABLA COMPARTIDA** — lee para calcular avance real (`malla_avance_service`); escribe columnas de clasificación (`tipo_sector`, `numero_precorte`, `identificador_sector`) vía `clasificacion_operacional_service` |

> **⚠ CRÍTICO:** `registros_perforacion` es la tabla core del sistema principal. El módulo de planos la lee Y la escribe (columnas de clasificación). Ver Sección 6.

### 1.2 — `pages/05_Ortomosaico_Vista_Mina.py`

| Tabla | Operación | Descripción |
|---|---|---|
| — | — | **No usa ninguna tabla SQLite.** Opera exclusivamente sobre archivos del sistema de ficheros (TIFF/PNG/JPG + JSON). |

---

## 2. Tablas de Referencia

Tablas que los módulos consultan pero cuyo origen y gestión pertenece al sistema principal. Si el nuevo sistema usa su propia base de datos, estas tablas deben sincronizarse o exponerse vía API.

| Tabla | Módulo | Uso | Frecuencia de cambio en origen |
|---|---|---|---|
| `registros_perforacion` | 04 (via `malla_avance_service`) | Lee metros perforados reales agrupados por fase/banco para calcular avance real vs planificado | Cada turno (diaria) |
| `registros_perforacion` | 04 (via `clasificacion_operacional_service`) | Lee registros sin clasificar para mostrarlos; escribe campos de clasificación de vuelta | Cada turno + cuando supervisor clasifica |

> **Nota:** `equipos_esperados()` no es una tabla, sino una función de `app_perforacion.py` que retorna la flota activa. El módulo 05 la usa para mostrar los equipos disponibles en el editor de ortomosaico. Si la flota cambia en el sistema principal, el ortomosaico refleja datos desactualizados.

---

## 3. Funciones y Constantes Compartidas

### 3.1 Imports de módulos compartidos

#### `pages/04_Gestion_Planos.py`
```python
import app_perforacion as app        # app.st, app.requerir_acceso()
import db                            # db.DB_PATH, db.conectar_db()
from ui.formatting import dataframe_visible, texto_visible
from ui.page_header import render_page_header
```

#### `pages/05_Ortomosaico_Vista_Mina.py`
```python
import app_perforacion as app        # app.st, app.requerir_acceso(), app.equipos_esperados()
from ui.components import section_header
from ui.page_header import render_page_header
```

#### `services/malla_service.py` (exclusivo de 04)
```python
import db                            # db.conectar_db(), db.DB_PATH
from config import PLANOS_MALLA_DIR, PLANOS_MALLA_PREVIEW_DIR, REPORTES_OPERADORES_DIR
```

#### `services/malla_avance_service.py` (exclusivo de 04)
```python
import db
from services import malla_service
```

#### `services/clasificacion_operacional_service.py` (exclusivo de 04)
```python
import db
```

#### `services/ortomosaico_service.py` (exclusivo de 05)
```python
# Solo librerías estándar + Pillow/Streamlit — NO importa db.py ni config.py
```

#### `ui/ortomosaico_ui.py` (exclusivo de 05)
```python
import plotly.graph_objects as go
from services import ortomosaico_service
```

### 3.2 Tabla de uso compartido por módulo

| Módulo / función | Usado por 04 | Usado por 05 | Usado por RESTO del sistema | Acción en separación |
|---|:---:|:---:|:---:|---|
| `db.conectar_db()` | ✓ | — | ✓ Todos | Duplicar o compartir vía paquete |
| `db.DB_PATH` | ✓ | — | ✓ Todos | Duplicar o apuntar a BD propia |
| `db.crear_tablas()` | ✓ (vía malla) | — | ✓ Todos | Duplicar DDL en nuevo sistema |
| `app.requerir_acceso()` | ✓ | ✓ | ✓ Todos | Duplicar o exponer como paquete auth |
| `app.equipos_esperados()` | — | ✓ | ✓ dashboard | Sincronizar flota o duplicar fuente |
| `app.st` | ✓ | ✓ | ✓ Todos | Es `streamlit` — no requiere acción |
| `config.PLANOS_MALLA_DIR` | ✓ (vía malla) | — | — | Reemplazar con nueva constante local |
| `config.PLANOS_MALLA_PREVIEW_DIR` | ✓ (vía malla) | — | — | Reemplazar con nueva constante local |
| `config.REPORTES_OPERADORES_DIR` | ✓ (vía malla) | — | — | Reemplazar con nueva constante local |
| `ui/formatting.py` | ✓ | — | ✓ Varios | Duplicar (11 líneas de código) |
| `ui/page_header.py` | ✓ | ✓ | ✓ Todos | Duplicar (componente visual simple) |
| `ui/components.py` | — | ✓ | ✓ Varios | Duplicar función `section_header` |

### 3.3 Constantes definidas en módulos exclusivos

Estas constantes viven en archivos que se van a mover — no están en módulos compartidos, por lo que no hay conflicto:

```python
# En malla_service.py (se mueve)
TIPOS_POZO_MALLA_CONTROL     = ("Producción", "Buffer", "Precorte", "Otro")
TIPOS_SECTOR_PERFORACION     = ("Producción", "Buffer 1", "Buffer 2", "Precorte", "Borde", "Otro")
ESTADOS_SECTOR_PERFORACION   = ("Planificado", "En ejecución", "Completado", "Detenido")
ESTADOS_POZO_VALIDOS         = ("pendiente", "perforado", "repaso", "colapsado", "no perforar")

# En enaex_pdf_extraction_service.py (se mueve)
TIPOS_SECTOR_ENAEX           = ("Producción", "Buffer 1", "Buffer 2", "Borde", "Precorte")

# En clasificacion_operacional_service.py (se mueve)
TIPOS_SECTOR                 = ("Producción", "Buffer 1", "Buffer 2", "Precorte", "Borde", "Otro")

# En ortomosaico_service.py (se mueve)
EXTENSIONES_SOPORTADAS       = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
MAX_PREVIEW_SIZE             = (2400, 1600)
```

---

## 4. Archivos Físicos Exclusivos

### 4.1 Módulo 04 — Gestión de Planos

| Ruta | Tipo | Origen | Quién lo crea |
|---|---|---|---|
| `data/planos_malla/` | Directorio | PDFs de planos subidos por el usuario | `registrar_archivo_plano_malla()` en malla_service |
| `data/planos_malla/preview/` | Directorio | PNG rasterizados desde cada PDF | `generar_preview_pdf_real()` — requiere PyMuPDF (fitz) |
| `data/reportes_operadores/` | Directorio | Fotos de reportes de operadores | `registrar_archivo_reporte_operador()` (feature latente) |

**Dependencias de librerías para archivos físicos:**
- `PyMuPDF` (`fitz`) — rasterización de PDF a PNG para preview
- `openpyxl` — generación de Excel de pozos (en memoria, no a disco)
- `Pillow` (`PIL`) — manipulación de imágenes para preview

### 4.2 Módulo 05 — Ortomosaico

| Ruta | Tipo | Origen | Quién lo crea |
|---|---|---|---|
| `ortomosaicos/` | Directorio | Imágenes maestras (TIFF/PNG/JPG) de la mina | Cargadas manualmente por el usuario |
| `ortomosaicos/*_preview.jpg` | Archivos JPG | Previews reducidas (2400×1600 máx) | `asegurar_preview()` en ortomosaico_service — automático al primer acceso |
| `data/posiciones_equipos_mapa.json` | JSON | Posiciones (x, y) de cada equipo en el mapa | Guardado cada vez que el usuario mueve un equipo en el editor |
| `data/zonas_mapa.json` | JSON | Polígonos de zonas dibujadas por el usuario | Guardado al dibujar o editar zonas en el editor |

**Estructura de los JSON:**
```json
// posiciones_equipos_mapa.json
{ "9259": {"x": 45.5, "y": 32.1}, "9272": {"x": 52.3, "y": 28.7} }

// zonas_mapa.json
[{ "id": 1234567890, "nombre": "Zona Producción 114",
   "color": "#F97316", "puntos": [{"x": "10", "y": "15"}, ...] }]
```

**Dependencias de librerías para archivos físicos:**
- `Pillow` (`PIL`) — generación de imagen con marcadores de equipos superpuestos
- `plotly` — visualización interactiva del ortomosaico en Streamlit

### 4.3 No hay shapefiles ni cachés geoespaciales

El sistema de ortomosaico usa imágenes ráster + coordenadas en píxeles relativas (no coordenadas geográficas reales). No hay `.shp`, `.geojson`, `.kml` ni cachés de proyección.

---

## 5. Dependencias Inversas

Módulos del sistema principal que hacen referencia a funcionalidades de estos dos módulos.

### 5.1 `dashboard.py` → `malla_service.resumen_avance_malla()`

```python
# dashboard.py línea 33
from services.malla_service import resumen_avance_malla
```

El dashboard muestra un widget de "Avance de malla" que llama a esta función. Es la **única dependencia inversa** en todo el sistema.

- **Función:** `resumen_avance_malla(db_path, malla_id=None)` — retorna dict con KPIs de avance (pozos perforados / planificados / porcentaje)
- **Impacto si se mueve malla_service:** el dashboard queda con un import roto
- **Opciones:** (a) mantener esta función en el sistema principal como stub que llama al nuevo; (b) exponer API REST desde el nuevo sistema; (c) mover la lógica mínima a un módulo compartido

### 5.2 `pages/03_Avance_Operacional.py` → tablas históricas de malla

Page 03 hace referencias a la tabla `avance_malla` (presumiblemente `mallas_avance`) mediante consultas SQL directas. Si estas tablas se mueven a una base de datos separada, la página 03 queda con queries rotas.

- **Impacto:** medio — page 03 es del sistema principal y no debería modificarse en la separación
- **Opción recomendada:** mantener las tablas históricas (`mallas_avance`, `pozos_avance`, etc.) en la BD del sistema principal, o mantener una BD compartida solo para estas tablas

### 5.3 Resto del sistema

| Módulo | Referencia | Tipo |
|---|---|---|
| `pages/01_Registro_Operacional.py` | Campo "Pozos perforados" | Solo texto UI — no es dependencia funcional |
| `pages/25_Editar_Registro.py` | Variable `pozos` local | Solo cálculo interno — no es dependencia |
| Todos los demás `pages/` | — | Sin referencia a planos/ortomosaico |

**Veredicto: CERO dependencias inversas funcionales adicionales** más allá de las dos mencionadas.

---

## 6. Clasificación Final

### ✅ Se puede mover tal cual (sin modificación)

| Archivo | Motivo |
|---|---|
| `pages/04_Gestion_Planos.py` | Sin dependencias externas excepto módulos listados abajo |
| `pages/05_Ortomosaico_Vista_Mina.py` | Sin dependencias externas excepto módulos listados abajo |
| `services/malla_service.py` | Todas sus tablas son propias (excepto la función usada por dashboard — ver riesgos) |
| `services/malla_avance_service.py` | Solo lee `registros_perforacion` — puede recibir conexión externa |
| `services/enaex_pdf_extraction_service.py` | Sin dependencias de BD ni config; solo fitz + pandas |
| `services/ortomosaico_service.py` | Sin dependencias de BD; solo Pillow + Path |
| `ui/ortomosaico_ui.py` | Solo depende de `ortomosaico_service` + plotly |
| `ortomosaicos/` (directorio) | Archivos ráster — portables |
| `data/planos_malla/` (directorio) | PDFs y previews — portables |
| `data/posiciones_equipos_mapa.json` | JSON simple — portable |
| `data/zonas_mapa.json` | JSON simple — portable |

### ⚠ Hay que duplicar o adaptar (no se puede mover directamente)

| Módulo / componente | Razón | Acción recomendada |
|---|---|---|
| `db.py` | Usado por TODO el sistema; no se puede mover | Crear `db_planos.py` en el nuevo sistema con las mismas funciones pero apuntando a BD propia |
| `config.py` | Las rutas `PLANOS_MALLA_DIR` etc. son relativas al proyecto principal | Crear `config.py` propio en nuevo sistema con rutas adaptadas |
| `app_perforacion.py` → `requerir_acceso()` | Sistema de autenticación del proyecto principal | Extraer lógica de auth a módulo independiente o duplicar en nuevo sistema |
| `app_perforacion.py` → `equipos_esperados()` | Retorna flota activa desde BD del sistema principal | Ver sección de sincronización |
| `ui/formatting.py` | 11 líneas; usado por varios módulos del sistema principal | Duplicar las dos funciones necesarias (`dataframe_visible`, `texto_visible`) |
| `ui/page_header.py` | Componente visual compartido por todas las páginas | Duplicar en nuevo sistema |
| `ui/components.py` → `section_header()` | Función simple compartida | Duplicar la función (1 función, ~5 líneas) |

### 🔄 Requiere sincronización entre sistemas

| Dato | Dirección | Frecuencia necesaria | Mecanismo sugerido |
|---|---|---|---|
| `registros_perforacion` (lectura de metros) | Principal → Nuevo | Diaria (por turno) | Vista de solo lectura en BD compartida, o API REST, o réplica SQLite |
| `registros_perforacion` (escritura de clasificación) | Nuevo → Principal | Al clasificar (ad-hoc) | **Riesgo mayor** — el nuevo sistema no debería escribir en BD del principal |
| Flota de equipos (`equipos_esperados()`) | Principal → Nuevo | Al cambiar flota (esporádico) | Archivo JSON de sincronización, o endpoint API |
| Avance de malla para dashboard | Nuevo → Principal | Cada vez que el dashboard carga | API REST desde nuevo sistema, o mantener función en BD compartida |

### 🚨 Riesgos detectados que hay que resolver antes de mover

#### Riesgo 1 — CRÍTICO: `clasificacion_operacional_service` escribe en `registros_perforacion`

El módulo de clasificación operacional (exclusivo de planos) añade columnas (`tipo_sector`, `numero_precorte`, `identificador_sector`) directamente a la tabla core del sistema principal. Si el nuevo sistema tiene su propia BD, no puede hacer esos writes.

**Opciones antes de mover:**
- (a) Mover la clasificación a una tabla separada (`clasificacion_operacional`) con FK a `id` de `registros_perforacion`, y sincronizar hacia el principal vía job
- (b) Exponer un endpoint en el sistema principal para recibir updates de clasificación desde el nuevo sistema
- (c) Mantener `clasificacion_operacional_service` en el sistema principal y exponer una API de escritura

#### Riesgo 2 — ALTO: `dashboard.py` tiene un import directo de `malla_service`

```python
from services.malla_service import resumen_avance_malla  # dashboard.py:33
```

Si `malla_service` se mueve, este import queda roto y el dashboard principal falla al iniciar.

**Opciones antes de mover:**
- (a) Crear un stub `services/malla_service.py` en el sistema principal que llame al nuevo sistema vía API
- (b) Duplicar solo `resumen_avance_malla()` en el sistema principal (la función es autocontenida si se le pasa la conexión)
- (c) Mantener la función en ambos sistemas (la BD de planos y la BD principal comparten las tablas históricas)

#### Riesgo 3 — ALTO: `pages/03_Avance_Operacional.py` accede a tablas de malla por SQL directo

Page 03 consulta tablas como `mallas_avance` directamente sobre la BD del sistema principal. Si esas tablas migran a otra BD, page 03 queda rota sin modificación.

**Opciones antes de mover:**
- (a) Mantener las tablas históricas de malla (`mallas_avance`, `pozos_avance`, etc.) EN la BD del sistema principal y replicarlas desde el nuevo
- (b) Modificar page 03 para usar una API de consulta en lugar de acceso directo a BD
- (c) Usar la misma BD SQLite para ambos sistemas (opción de menor riesgo si ambos corren en el mismo servidor)

#### Riesgo 4 — MEDIO: `equipos_esperados()` en `app_perforacion.py`

El módulo 05 (Ortomosaico) llama a `app.equipos_esperados()` para poblar el editor de posicionamiento. Esta función devuelve la flota activa del sistema principal. Si el nuevo sistema no tiene acceso a `app_perforacion.py`, el ortomosaico mostraría una flota vacía o desactualizada.

**Opción antes de mover:**
- Extraer la flota a un JSON de configuración que se sincroniza desde el sistema principal al nuevo (podría ser el mismo `data/posiciones_equipos_mapa.json` extendido con metadatos de flota)

#### Riesgo 5 — BAJO: Dependencia de `PyMuPDF` (`fitz`) con fallback silencioso

`malla_service.py` importa `fitz` con `fallback=None` — si no está instalado, la rasterización de PDFs falla silenciosamente. El nuevo sistema debe tener `PyMuPDF` en su entorno virtual.

---

## Resumen Visual

```
┌─────────────────────────────────────────────────────────────────┐
│                     SISTEMA PRINCIPAL                           │
│                                                                 │
│  pages/01..03, 06..25  │  dashboard.py  │  db.py  │  config.py │
│                         │               │          │            │
│         usa ─────────────► malla_service.resumen_avance_malla() │
│         usa ─────────────► registros_perforacion (tabla core)  │
│                         │                                       │
└─────────────┬───────────────────────────────────┬──────────────┘
              │ ⚠ Riesgo 2: import directo         │ ⚠ Riesgo 1/3
              │                                    │ sync tabla compartida
┌─────────────▼────────────────────────────────────▼──────────────┐
│                    NUEVO SISTEMA (propuesto)                     │
│                                                                  │
│  pages/04_Gestion_Planos.py                                      │
│  pages/05_Ortomosaico_Vista_Mina.py                              │
│                                                                  │
│  services/malla_service.py         (13 tablas propias)           │
│  services/malla_avance_service.py  (lee registros_perforacion)  │
│  services/clasificacion_operacional_service.py  (escribe en rp) │
│  services/enaex_pdf_extraction_service.py  (sin BD)             │
│  services/ortomosaico_service.py   (sin BD)                      │
│  ui/ortomosaico_ui.py              (sin BD)                      │
│                                                                  │
│  Datos físicos:                                                  │
│    ortomosaicos/                                                 │
│    data/planos_malla/                                            │
│    data/posiciones_equipos_mapa.json                             │
│    data/zonas_mapa.json                                          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Orden recomendado de trabajo pre-separación

1. **Resolver Riesgo 1** (clasificacion_operacional): mover el almacenamiento de clasificación a tabla propia antes de tocar nada más
2. **Resolver Riesgo 2** (dashboard import): crear stub en sistema principal que no dependa de malla_service siendo local
3. **Resolver Riesgo 3** (page 03 / tablas históricas): decidir si tablas históricas de malla van en BD compartida o se replican
4. **Resolver Riesgo 4** (equipos_esperados): exportar flota a JSON de configuración estático sincronizable
5. Con los 4 riesgos resueltos: la separación física de los archivos es trivial (solo mover + adaptar paths de config)
