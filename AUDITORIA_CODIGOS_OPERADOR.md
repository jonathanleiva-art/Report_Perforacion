# Auditoría de Códigos de Operador
**Fecha:** 2026-07-11 | **Modo:** Solo lectura — sin modificaciones a la BD  
**Base de datos:** `reportes_perforacion.db` (13.956 KB)

---

## 1. Estructura de almacenamiento de operadores

Existen **cuatro tablas** con datos de operador:

| Tabla | Filas | Columnas de operador | Rol |
|-------|-------|----------------------|-----|
| `operadores` | 22 | `codigo_operador` (PK), `nombre_operador` | Catálogo canónico |
| `registros_perforacion` | 245 | `"Código operador"` (bruto), `operador_codigo` (normalizado), `"Operador"` (nombre bruto), `operador_nombre` | Registros de turno activos |
| `reportes` | 50 | `"Código operador"`, `"Operador"` | Espejo/subconjunto de registros_perforacion (mismo período) |
| `ciclos_perforacion` | 6.669 | `operador_codigo_original`, `operador_codigo_normalizado`, `operador_nombre` | Ciclos individuales de perforación |

**Conclusión:** Existe una tabla `operadores` formal con PK único. Sin embargo, `registros_perforacion` guarda tanto el código bruto original como el código ya normalizado por `normalizar_codigo_operador()` de `operators.py`. La normalización es correcta en la mayoría de casos pero produce falsos positivos en dos registros.

---

## 2. Catálogo formal (tabla `operadores`) — 22 registros activos

| Código canónico | Nombre | Alta |
|-----------------|--------|------|
| 001654 | Hermes Moraga | 2026-06-08 |
| 002036 | Carlos Rondon | 2026-06-04 |
| 002268 | Diego Huerta | 2026-06-03 |
| 002281 | Yerko Rojas | 2026-06-08 |
| 005195 | Geronimo Gonzalez | 2026-06-08 |
| 005925 | Henry Latus | 2026-06-08 |
| 006010 | Oscar Barraza | 2026-06-08 |
| 007494 | Jhon Tapia | 2026-06-03 |
| 007540 | Javier Herrera | 2026-06-03 |
| 007630 | Patricio Saez | 2026-06-08 |
| 008086 | Jonathan Leiva | 2026-06-04 |
| 009234 | Diego Aracena | 2026-06-03 |
| 009464 | Jhan Calderon | 2026-06-04 |
| 009608 | Nicolas Torres | 2026-06-04 |
| 009939 | Mauricio Mora | 2026-06-04 |
| 009983 | Eduardo de la paz Pereira | 2026-06-08 |
| 009992 | Edson Valenzuela | 2026-06-08 |
| 101108 | Juan Yáñez | 2026-06-08 |
| 203528 | Tereza Inostroza | 2026-06-03 |
| 203529 | Valeria Millan | 2026-06-04 |
| 203666 | Martina Díaz | 2026-06-03 |
| 204167 | Matías Toro | 2026-06-04 |

> **Ausente del catálogo:** `009698` — código que aparece en 12 registros de `registros_perforacion` bajo el nombre "Nicolas Torres". No tiene entrada en `operadores`. Ver sección 4.

---

## 3. Operadores con más de un código en registros_perforacion

Solo se consideran operadores que aparecen bajo **distintos códigos brutos** a lo largo del histórico.

### Tabla principal de diagnóstico

| Nombre operador | Código bruto | Código normalizado | Registros | Rango fechas | Equipos | Origen |
|---|---|---|---|---|---|---|
| **Carlos Rondon** | `M-2036` | `002036` | 9 | 2026-05-14 → 2026-05-26 | 9277 | Excel legado |
| **Carlos Rondon** | `002036` | `002036` | 12 | 2026-06-11 → 2026-06-24 | 9245,9259,9272,9277 | Sistema actual |
| **Jhan Calderon** | `M-9464` | `009464` | 14 | 2026-05-14 → 2026-05-27 | 9272,9274 | Excel legado |
| **Jhan Calderon** | `009464` | `009464` | 12 | 2026-06-11 → 2026-06-24 | 9259,9339 | Sistema actual |
| **Jhan Calderon** | `94964` | `002268` ⚠️ | 1 | 2026-06-19 | 9339 | **ERROR de tipeo** |
| **Jonathan Leiva** | `M-8086` | `008086` | 11 | 2026-05-14 → 2026-05-27 | 9245 | Excel legado |
| **Jonathan Leiva** | `008086` | `008086` | 14 | 2026-06-11 → 2026-06-24 | 9245,9259,9272,9277 | Sistema actual |
| **Matías Toro** | `M-204167` | `204167` | 15 | 2026-05-14 → 2026-05-27 | 9259,9339 | Excel legado |
| **Matías Toro** | `204167` | `204167` | 15 | 2026-06-11 → 2026-06-24 | 9259,9274 | Sistema actual |
| **Mauricio Mora** | `M-9939` | `009939` | 14 | 2026-05-14 → 2026-05-27 | 9272,9274 | Excel legado |
| **Mauricio Mora** | `009939` | `009939` | 14 | 2026-06-11 → 2026-06-24 | 9259,9272 | Sistema actual |
| **Nicolas Torres** | `M-9608` | `009608` | 1 | 2026-05-14 | 9339 | Excel legado |
| **Nicolas Torres** | `M-9698` | `009698` ⚠️ | 12 | 2026-05-16 → 2026-05-27 | 9339 | **CÓDIGO FANTASMA** |
| **Nicolas Torres** | `009608` | `009608` | 1 | 2026-06-11 | 9339 | Sistema actual |
| **Valeria Millan** | `M-203529` | `203529` | 8 | 2026-05-17 → 2026-05-27 | 9245,9277 | Excel legado |
| **Valeria Millan** | `203529` | `203529` | 13 | 2026-06-12 → 2026-06-24 | 9245,9274,9277 | Sistema actual |

> **Patrones normales (variantes M- / sin M-):** Carlos Rondon, Jonathan Leiva, Matías Toro, Mauricio Mora, Valeria Millan — todos tienen el mismo código normalizado en ambas variantes. La función `normalizar_codigo_operador()` los une correctamente al quitar el prefijo `M-`.

---

## 4. Los 9 códigos con prefijo "M-" — diagnóstico completo

| Código M- bruto | Código normalizado | Nombre | Registros RP | Registros Rep. | Rango | Equipo(s) | ¿Correcto? |
|---|---|---|---|---|---|---|---|
| `M-203529` | `203529` | Valeria Millan | 8 | 4 | 2026-05-17 → 2026-05-27 | 9245, 9277 | ✅ Sí |
| `M-2036` | `002036` | Carlos Rondon | 9 | 7 | 2026-05-14 → 2026-05-26 | 9277 | ✅ Sí |
| `M-204167` | `204167` | Matías Toro | 14 | 9 | 2026-05-14 → 2026-05-27 | 9259 | ✅ Sí |
| `M-204167` (1 reg.) | `204167` | **Nicolas Torres** ⚠️ | 1 | — | 2026-05-15 | 9339 | ❌ Cross-contamination |
| `M-8086` | `008086` | Jonathan Leiva | 11 | 7 | 2026-05-14 → 2026-05-27 | 9245 | ✅ Sí |
| `M-9464` | `009464` | Jhan Calderon | 14 | 8 | 2026-05-14 → 2026-05-27 | 9272, 9274 | ✅ Sí |
| `M-9608` | `009608` | Nicolas Torres | 1 | 1 | 2026-05-14 | 9339 | ✅ Sí |
| `M-9698` | `009698` ⚠️ | Nicolas Torres | 12 | 6 | 2026-05-16 → 2026-05-27 | 9339 | ❌ Código fantasma |
| `M-9939` | `009939` | Mauricio Mora | 14 | 8 | 2026-05-14 → 2026-05-27 | 9272, 9274 | ✅ Sí |

**Contexto:** Todos los códigos `M-` pertenecen al período **2026-05-14 a 2026-05-27** (primera carga desde Excel). Después de esa fecha el sistema genera códigos de 6 dígitos directamente. La función `normalizar_codigo_operador()` en `operators.py` quita el prefijo `M-` y rellena con ceros a la izquierda, unificando ambas variantes en runtime.

---

## 5. Anomalías críticas detectadas

### ANOMALÍA A — Código `94964` (id=1164)
**Gravedad: ALTA — produce asignación a operador incorrecto**

```
Registro id=1164
  Fecha turno:      2026-06-19 (Turno Día)
  Equipo:           9339
  "Operador":       "Jhan Calderon"          ← nombre correcto en el campo bruto
  "Código operador": "94964"                 ← tipeo erróneo de "009464"
  operador_codigo:  "002268"                 ← normalizado como Diego Huerta ← INCORRECTO
  operador_nombre:  "Diego Huerta"           ← nombre asignado incorrectamente
```

**Causa:** El código `94964` tiene 5 dígitos → `normalizar_codigo_operador("94964")` produce `"094964"` → no existe en `operadores` → se usa el campo `"Operador"` bruto para resolver → pero el campo bruto dice `"Jhan Calderon"`, no un código → en algún punto del flujo el sistema lo resolvió como `002268`. El código correcto es `009464` (transposición del dígito inicial: `94964` → `9|4964` en lugar de `9464`).

**Impacto:** 1 registro. Los KPIs de Jhan Calderon pierden 151,2 metros perforados ese día; Diego Huerta los gana incorrectamente.

---

### ANOMALÍA B — Código `M-9698` / `009698` (12 registros)
**Gravedad: MEDIA — código inexistente en catálogo**

```
Registros id: 999, 1007, 1013, 1018, 1021, 1026, 1033, 1040, 1047, 1053, 1058, 1064
  Período:          2026-05-16 → 2026-05-27
  Equipo:           9339 (todos)
  "Operador":       "Nicolas Torres"
  "Código operador": "M-9698"
  operador_codigo:  "009698"                 ← NO existe en tabla operadores
  operador_nombre:  "Nicolas Torres"         ← resuelto por nombre, no por código
```

**Causa probable:** `M-9698` es un tipeo de `M-9608` (dígitos `698` vs `608` — el `6` y el `9` están intercambiados). El código real de Nicolas Torres es `009608`, que sí existe en el catálogo. El nombre "Nicolas Torres" se resolvió correctamente porque el campo `"Operador"` bruto lo tenía explícito, pero el código normalizado quedó como `009698` (fantasma).

**Impacto:** 12 registros de Nicolas Torres en equipo 9339 tienen un código huérfano. Los filtros por código no los encontrarán si se busca `009608`.

---

### ANOMALÍA C — `M-204167` + "Nicolas Torres" (id=993, 1 registro)
**Gravedad: BAJA — cross-contamination de una sola noche**

```
Registro id=993
  Fecha turno:      2026-05-15 (Noche)
  Equipo:           9339
  "Operador":       "Nicolas Torres"
  "Código operador": "M-204167"             ← pertenece a Matías Toro
  operador_codigo:  "204167"                ← Matías Toro
  operador_nombre:  "Matías Toro"           ← asignado a Toro por el código
```

**Contexto:** El 14/05 Nicolas Torres operó el equipo 9339 con `M-9608` (correcto). El 15/05 se registró `M-204167` (Matías Toro) con nombre "Nicolas Torres" — probable error manual de quien llenó la planilla Excel. El 16/05 en adelante aparece `M-9698` (el código fantasma). Este registro le suma producción a Matías Toro y se la quita a Nicolas Torres.

---

## 6. Resumen ejecutivo: tabla de decisiones propuestas

| # | Nombre operador | Código(s) encontrados | Canónico propuesto | Registros afectados (por código) | Rango de fechas | Acción recomendada |
|---|---|---|---|---|---|---|
| 1 | Carlos Rondon | `M-2036` (9), `002036` (12) | **002036** | 9 registros con M-2036 | 2026-05-14 a 2026-05-26 | Sin cambio urgente; normalización ya correcta en runtime |
| 2 | Diego Huerta | `002268` (12), `""` (1), `94964` (1) ⚠️ | **002268** | 1 registro mal asignado (94964) | 2026-06-19 | Corregir id=1164: cod_bruto→`009464`, cod_norm→`009464`, nombre→`Jhan Calderon` |
| 3 | Jhan Calderon | `M-9464` (14), `009464` (12), `94964` (1→mal asignado) | **009464** | 1 registro robado (id=1164) | 2026-06-19 | Ver fila anterior + recuperar el registro en KPIs de Calderon |
| 4 | Jonathan Leiva | `M-8086` (11), `008086` (14) | **008086** | — | 2026-05-14 a 2026-06-24 | Sin cambio urgente |
| 5 | Matías Toro | `M-204167` (14), `204167` (15), `M-204167`+Torres (1) ⚠️ | **204167** | 1 registro ajeno (id=993) | 2026-05-15 | Corregir id=993: cod_bruto→`M-9608`, cod_norm→`009608`, nombre→`Nicolas Torres` |
| 6 | Mauricio Mora | `M-9939` (14), `009939` (14) | **009939** | — | 2026-05-14 a 2026-06-24 | Sin cambio urgente |
| 7 | Nicolas Torres | `M-9608` (1), `M-9698` (12) ⚠️, `009608` (1) | **009608** | 12 registros con código fantasma | 2026-05-16 a 2026-05-27 | Corregir 12 registros (M-9698→M-9608, 009698→009608) + agregar 009698→009608 al catálogo si se prefiere no cambiar brutos |
| 8 | Nicolas Torres | `M-204167` (1, cross) ⚠️ | **009608** | 1 registro con código ajeno | 2026-05-15 | Ídem anomalía C |
| 9 | Valeria Millan | `M-203529` (8), `203529` (13) | **203529** | — | 2026-05-17 a 2026-06-24 | Sin cambio urgente |

---

## 7. Codes M- en ciclos_perforacion

Los ciclos usan `operador_codigo_original` (dígitos sin prefijo M-, ej: `"9464"`) y `operador_codigo_normalizado` (zero-padded, ej: `"009464"`). **No contienen códigos M-** — el prefijo nunca llegó a esta tabla. Los operadores con nombre resuelto son los mismos 13 del catálogo conocido. Los registros sin nombre (8 entradas) tienen códigos: `000001`, `000003`, `001573`, `004011`, `000750`, `010108`, `280173`, `203671`, `203672` — corresponden a operadores históricos anteriores al período 2026, no cubiertos por el catálogo actual.

---

## 8. Función de normalización (operators.py)

```python
def normalizar_codigo_operador(codigo):
    # Quita "M-" → elimina puntos y guiones → extrae solo dígitos → zfill(6)
    texto = re.sub(r"^\s*M\s*-\s*", "", str(codigo).strip().upper())
    digitos = re.sub(r"\D+", "", texto)
    return digitos.zfill(6) if len(digitos) < 6 else digitos
```

**Comportamiento con los casos anómalos:**
- `"94964"` → dígitos=`"94964"` (5) → `"094964"` → no en catálogo → no resuelve nombre → queda como `002268` por una ruta de fallback no explicada en los datos disponibles. Requiere revisión del flujo de importación.
- `"M-9698"` → dígitos=`"9698"` (4) → `"009698"` → no en catálogo → nombre resuelto por campo `"Operador"` = "Nicolas Torres" (correcto en texto, incorrecto en código).

---

## 9. Acciones pendientes (sin ejecutar)

1. **Corrección id=1164** (`94964` → Jhan Calderon):
   - `"Código operador"` = `"009464"`
   - `operador_codigo` = `"009464"`
   - `"Operador"` ya es `"Jhan Calderon"` (correcto)
   - `operador_nombre` = `"Jhan Calderon"`
   - Aplica en: `registros_perforacion` y `reportes` (si existe espejo)

2. **Corrección 12 registros M-9698** (Nicolas Torres):
   - `"Código operador"` = `"M-9608"` (o mantener `"M-9698"` como histórico)
   - `operador_codigo` = `"009608"`
   - Aplica en: `registros_perforacion` y `reportes`

3. **Corrección id=993** (`M-204167` / Nicolas Torres):
   - `"Código operador"` = `"M-9608"` (o `"009608"`)
   - `operador_codigo` = `"009608"`
   - `operador_nombre` = `"Nicolas Torres"`
   - Aplica en: `registros_perforacion` y `reportes`

4. **Opcional:** Agregar `009698` como alias de `009608` en `operadores` (para búsquedas históricas) o eliminarlo del todo.

5. **Códigos M- en bruto** (`M-2036`, `M-8086`, etc.): No requieren corrección urgente porque `normalizar_codigo_operador()` los unifica en runtime. Podrían limpiarse para consistencia visual.

---

*Documento generado el 2026-07-11. Sin ningún UPDATE, INSERT ni DELETE ejecutado sobre la base de datos.*
