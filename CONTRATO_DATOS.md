# Contrato de Datos del Sistema de Perforación

Este documento define el contrato funcional de datos para captura, cálculo, validación, almacenamiento y visualización de reportes de perforación. El objetivo es mantener compatibilidad entre Streamlit, Excel, SQLite, dashboards, reportes PDF y pruebas automatizadas.

## Alcance

El sistema registra turnos de perforación de 12 horas por equipo, operador, fecha y turno. Cada registro combina identificación, ubicación, producción, distribución de horas, KPIs operacionales, observaciones y campos de compatibilidad histórica.

La fuente formal de columnas es `schema.py`. La construcción del payload de guardado está en `services/report_service.py`. Los cálculos operacionales están en `metrics.py` y `services/kpi_service.py`.

## Catálogos

### Equipos

| Modelo equipo | Números equipo |
|---|---|
| Sandvik D75KS | 9245, 9277 |
| SmartROC D65 | 9339 |
| FlexiROC D65 | 9274, 9272, 9259 |

### Operadores

| Operador | Código operador |
|---|---|
| Jonathan Leiva | M-8086 |
| Carlos Rondon | M-2036 |
| Jhan Calderon | M-9464 |
| Mauricio Mora | M-9939 |
| Nicolas Torres | M-9698 |
| Matías Toro | M-204167 |
| Valeria Millan | M-203529 |

### Tipos de detención

Valores visibles y aceptados:

- Falla Operacional
- Avería mecánica
- Cambio de aceros
- Geología
- Seguridad
- Colación
- Relleno de agua
- Combustible
- Traslado
- Cambio Turno
- Standby por falta de tajo/Patio
- Mantención Programada
- Tronadura
- Falta operador
- Otros

## Campos Oficiales

Los nombres visibles deben mantenerse en español correcto y UTF-8. No se deben renombrar columnas históricas sin declarar alias de compatibilidad.

| Campo | Tipo esperado | Descripción |
|---|---|---|
| Fecha turno | Fecha o texto ISO | Fecha operacional del turno. |
| Modelo equipo | Texto | Modelo del equipo perforador. |
| Número equipo | Texto | Identificador operacional del equipo. Se normaliza sin decimales. |
| Operador | Texto | Nombre del operador. |
| Turno | Texto | Turno reportado. |
| Código operador | Texto | Código asociado al operador. |
| Área operacional | Texto | Área o faena operacional. |
| Petróleo litros | Entero | Litros de combustible reportados. |
| Aceite litros | Entero | Litros de aceite, campo histórico/oficial cuando exista. |
| Horómetro inicial | Entero | Lectura inicial de horómetro. |
| Horómetro final | Entero | Lectura final de horómetro. |
| Diferencia horómetro | Entero | Diferencia entre horómetro final e inicial. |
| Horas de motor | Entero | Horas motor usadas por compatibilidad; normalmente igual a diferencia de horómetro. |
| Banco | Texto | Banco o bancos perforados. |
| Malla | Texto | Malla o mallas perforadas. |
| Fase | Texto | Fase o fases perforadas. |
| Horas turno | Entero | Duración programada del turno. Valor estándar: 12. |
| Tipo de perforación | Texto | Tipo o tipos de perforación. |
| Número precorte | Entero o vacío | Número de precorte si aplica. |
| Número serie Tricono/Bit | Texto | Serie del tricono o bit. |
| Condición del terreno | Texto | Condición operacional del terreno. |
| Tipo detención | Texto | Tipos de detención seleccionados. |
| Causa detención | Texto | Detalle de causa de detención. |
| Horas detención mecánica | Real | Horas de avería mecánica. |
| Horas detención No efectivas | Real | Horas no efectivas operacionales. |
| Horas efectivas perforando | Real | Horas efectivas productivas del turno. |
| Trabajando | Real | Campo histórico de horas trabajando. |
| Combustible | Real | Horas asociadas a combustible. |
| Relleno de agua | Real | Horas asociadas a relleno de agua. |
| Colación | Real | Horas asociadas a colación. |
| Traslado | Real | Horas asociadas a traslado. |
| Traslado de sector | Real | Campo histórico de traslado por sector. |
| Traslado pozo a pozo | Real | Campo histórico de traslado entre pozos. |
| Traslado largo | Real | Campo histórico de traslado largo. |
| Standby por falta de tajo/Patio | Real | Horas en standby por falta de frente, tajo o patio. |
| Cambio de aceros | Real | Horas por cambio de aceros. |
| Sin marcación | Real | Campo histórico de registros sin marcación. |
| Mantención Programada | Real | Horas de mantención programada. |
| Avería | Real | Horas de avería. |
| Cambio turno | Real | Horas por cambio de turno. |
| Falta operador | Entero o real | Horas por falta de operador. |
| Otros | Real | Horas en categoría Otros. Debe conservarse como campo independiente. |
| Total horas ingresadas | Entero o real | Suma total de horas ingresadas por el usuario. |
| Total distribución turno | Entero o real | Campo histórico de suma de distribución. |
| Diferencia distribución | Entero o real | Diferencia histórica de distribución. |
| Metros perforados | Real | Metros perforados en el turno. |
| Cantidad pozos perforados | Entero | Campo histórico de pozos. |
| Pozos perforados turno | Entero | Pozos perforados en el turno. |
| Metros totales operador | Real | Total agregado por operador. |
| Metros totales por equipo | Real | Total agregado por equipo. |
| Rendimiento m/h | Real | KPI de rendimiento. |
| Disponibilidad % | Real | KPI de disponibilidad. |
| Utilización | Real | KPI de utilización. |
| Observaciones | Texto | Observaciones generales. |
| Descripción avería equipo | Texto | Detalle de avería del equipo. |
| Observación estado equipo | Texto | Observación del estado operacional. |
| Equipo | Texto | Campo compuesto o auxiliar para visualización. |
| Fecha | Fecha o texto | Campo histórico de fecha. |
| Hora registro | Texto | Hora de creación o registro. |
| Falla Operacional | Entero o real | Horas o marca de falla operacional. |
| Geología | Entero o real | Horas o marca de geología. |
| Seguridad | Entero o real | Horas o marca de seguridad. |

## Contrato de Claves Internas de Horas

Las claves internas de formulario no son necesariamente iguales al nombre visible. Deben mantenerse estables porque alimentan `app_perforacion.py`, `ui/forms_sections.py`, `ui/form_helpers.py` y `services/report_service.py`.

| Clave interna | Campo visible |
|---|---|
| horas_efectivas | Horas efectivas perforando |
| horas_no_efectivas | Horas detención No efectivas |
| horas_averia | Avería y Horas detención mecánica |
| horas_combustible | Combustible |
| horas_agua | Relleno de agua |
| horas_colacion | Colación |
| horas_traslado | Traslado |
| horas_standby | Standby por falta de tajo/Patio |
| horas_tronadura | Tronadura |
| horas_mantencion | Mantención Programada |
| horas_cambio_turno | Cambio turno |
| horas_falta_operador | Falta operador |
| horas_otros | Otros |
| horas_cambios_aceros | Cambio de aceros |

Reglas de compatibilidad:

- `horas_otros` no se elimina ni se renombra. Es requerido por `app_perforacion.py`, `render_horas_turno` y el payload de guardado.
- `horas_cambios_aceros` es la clave propia para la categoría Cambio de aceros.
- `horas_cambio_aceros` puede aceptarse como alias histórico de entrada, pero la clave canónica nueva es `horas_cambios_aceros`.
- El acceso a claves opcionales de horas debe usar `.get(..., 0.0)` para evitar `KeyError` y preservar compatibilidad con formularios antiguos.

## KPIs

### Rendimiento m/h

Se calcula sobre registros productivos. Un registro es productivo si:

- `Metros perforados > 0`
- `Horas efectivas perforando > 0`

Fórmula consolidada:

```text
Rendimiento m/h = suma(Metros perforados productivos) / suma(Horas efectivas perforando productivas)
```

Si no existen horas efectivas productivas, el rendimiento es `0.0`.

### Utilización

Fórmula:

```text
Utilización = max(Horas efectivas perforando, 0) / Horas turno * 100
```

Si `Horas turno <= 0`, la utilización es `0.0`.

### Disponibilidad %

Solo la avería y la mantención programada reducen disponibilidad. Standby y registros sin marcación se conservan por compatibilidad histórica, pero no descuentan disponibilidad.

```text
Horas no disponibles = max(Avería, 0) + max(Mantención Programada, 0)
Horas disponibles = max(Horas turno - min(Horas no disponibles, Horas turno), 0)
Disponibilidad % = Horas disponibles / Horas turno * 100
```

Si `Horas turno <= 0`, la disponibilidad es `0.0`.

## Estados Operacionales

El estado operacional por equipo se calcula en `services/kpi_service.py`:

| Condición | Estado operacional | Marcación |
|---|---|---|
| Mantención Programada >= 12 y Horas efectivas perforando = 0 | Mantención Programada | Fuera de servicio programado |
| Avería >= 12 y Horas efectivas perforando = 0 | Avería | Fuera de servicio por avería |
| Horas efectivas perforando > 0 y existe Avería u Horas no efectivas | Operativo parcial | Con marcación |
| Horas efectivas perforando > 0 | Operativo | Con marcación |
| Horas standby > 0 y sin producción efectiva | Operativo | Standby por falta de tajo/Patio |
| Sin metros, sin pozos y sin horas efectivas | Sin marcación | Sin marcación |

La producción existe si al menos uno de estos valores es mayor que cero:

- Metros perforados
- Pozos perforados
- Horas efectivas perforando

## Validaciones de Guardado

Validaciones obligatorias antes de guardar:

- `Total horas ingresadas` debe ser igual a `Horas turno`.
- El turno estándar debe sumar `12.00 h`.
- `Operador` no puede estar vacío.
- `Fecha turno` debe ser una fecha válida.
- `Turno` no puede estar vacío.
- `Número equipo` no puede estar vacío.
- `Metros perforados` debe ser numérico y mayor o igual a cero.
- Los campos numéricos no deben contener valores negativos.
- No debe existir duplicado para la combinación `Fecha turno + Turno + Modelo equipo + Número equipo + Operador`.

## Alertas Operacionales

Las alertas no reemplazan las validaciones duras de guardado. Sirven para control operacional y revisión de calidad:

| Regla | Severidad | Criterio |
|---|---|---|
| Disponibilidad 100% con mantención | Error | `Disponibilidad % >= 99.99` y `Mantención Programada > 0` |
| Utilización muy baja | Warning | `Utilización < 50` |
| Rendimiento bajo | Warning | Metros productivos > 0 y rendimiento consolidado < 10 m/h |
| Sin metros productivos | Warning | Metros productivos = 0 |
| Horas turno distintas de 12 | Warning | Diferencia absoluta entre `Horas turno` y 12 mayor a 0.01 |
| Baja disponibilidad | Indicador | `Disponibilidad % < 60` |
| Detenciones altas | Indicador | `Horas detención No efectivas + Avería >= 35% de Horas turno` |
| Sin marcación | Indicador | `Sin marcación > 0` o `Tipo detención` contiene Sin marcación |

## Compatibilidad Histórica

El sistema conserva alias para columnas antiguas y variantes de nombres. Al normalizar columnas:

- Los datos históricos no deben perderse.
- Los encabezados visibles deben presentarse corregidos en español.
- Las columnas antiguas pueden mapearse a nombres oficiales mediante `COLUMN_ALIASES` y `COLUMN_EQUIVALENTS`.
- Las categorías `Otros` y `Cambio de aceros` deben permanecer separadas.

## Edición Controlada y Trazabilidad

Los registros históricos pueden corregirse desde la página `pages/06_Edicion_Auditoria.py` solo mediante edición auditada.

Reglas obligatorias:

- Todo registro editable debe tener un `id` persistido en SQLite.
- La búsqueda de registros puede filtrar por fecha, turno, equipo, operador y malla.
- Antes de guardar, la aplicación debe mostrar el registro seleccionado.
- No se permite guardar una edición sin motivo.
- No se deben borrar registros físicos desde el flujo de edición controlada.
- Cada campo modificado debe generar una fila de auditoría independiente.
- Los valores sin cambio real no deben generar auditoría.
- Después de una edición válida, SQLite queda como fuente oficial actualizada.
- Si existe respaldo Excel operativo, debe sincronizarse desde SQLite después de editar.

La tabla `auditoria_ediciones` registra:

| Campo | Descripción |
|---|---|
| id | Identificador interno de la fila de auditoría. |
| registro_id | ID del registro histórico editado. |
| changed_at | Fecha/hora del cambio en formato ISO. |
| campo | Nombre del campo modificado. |
| valor_anterior | Valor antes de la edición. |
| valor_nuevo | Valor después de la edición. |
| motivo | Motivo obligatorio informado por el usuario. |
| usuario | Usuario o canal que ejecutó la edición. |

Campos operacionales editables:

- Identificación: Fecha turno, Turno, Modelo equipo, Número equipo, Operador, Código operador, Área operacional.
- Ubicación: Banco, Malla, Fase, Tipo de perforación, Número precorte, Número serie Tricono/Bit, Condición del terreno.
- Producción: Petróleo litros, Horómetro inicial, Horómetro final, Diferencia horómetro, Horas de motor, Metros perforados, Pozos perforados turno.
- Detenciones y horas: Tipo detención, Causa detención, Horas detención mecánica, Horas detención No efectivas, Horas efectivas perforando, Combustible, Relleno de agua, Colación, Traslado, Standby por falta de tajo/Patio, Tronadura, Mantención Programada, Cambio de aceros, Avería, Cambio turno, Falta operador, Otros, Total horas ingresadas.
- KPIs y notas: Rendimiento m/h, Disponibilidad %, Utilización, Observaciones.

## Respaldo, Exportación y Recuperación

La página `pages/07_Respaldos_Exportacion.py` centraliza respaldos manuales, exportaciones e integridad operacional.

Política de respaldo:

- Los respaldos se guardan en `backup/`.
- Cada respaldo debe incluir fecha y hora en el nombre del archivo.
- No se deben sobrescribir respaldos antiguos. Si ya existe un nombre, se agrega sufijo incremental.
- La base SQLite se respalda como copia física del archivo `.db`.
- El Excel operacional se respalda como copia física del archivo `.xlsx`.
- La carpeta `reportes_pdf/` se respalda como archivo `.zip`.
- La restauración automática no está habilitada todavía; la estructura queda preparada para una fase posterior.

Exportaciones permitidas:

- Datos operacionales filtrados a Excel.
- Auditoría de ediciones a Excel.
- Descarga de `CONTRATO_DATOS.md` desde la interfaz.

Verificación de integridad:

| Criterio | Descripción |
|---|---|
| existe_base_datos | Confirma si existe el archivo SQLite oficial. |
| existe_excel | Confirma si existe el Excel operacional. |
| registros_sqlite | Cantidad de registros en SQLite. |
| registros_excel | Cantidad de registros en Excel después de normalización. |
| fecha_ultimo_registro | Máxima `Fecha turno` disponible en SQLite. |
| auditorias_ediciones | Cantidad de filas registradas en `auditoria_ediciones`. |

La verificación de integridad es informativa. No debe modificar datos ni ejecutar restauraciones automáticas.

## Panel Ejecutivo e Índice de Salud Operacional

La página `pages/08_Panel_Ejecutivo.py` resume la salud general de la operación para jefatura usando datos consultados desde SQLite. No debe cargar el Excel completo como fuente operacional.

KPIs ejecutivos:

| KPI | Regla |
|---|---|
| Metros perforados totales | Suma de `Metros perforados`. |
| Horas efectivas | Suma de `Horas efectivas perforando`. |
| Horas no efectivas | Suma de `Horas detención No efectivas` o equivalente `Horas no efectivas`. |
| Disponibilidad promedio | Promedio de `Disponibilidad %`. |
| Utilización promedio | Promedio de `Utilización`. |
| Rendimiento promedio | `Metros perforados productivos / Horas efectivas productivas`. |
| Equipos activos | Equipos con metros perforados u horas efectivas mayores a cero. |
| Operadores registrados | Operadores distintos con registros en el filtro. |

El índice de salud operacional es un valor de 0 a 100 compuesto por cinco factores:

| Factor | Peso | Objetivo o regla |
|---|---:|---|
| Utilización | 25% | 85% equivale a 100 puntos. |
| Disponibilidad | 25% | 90% equivale a 100 puntos. |
| Rendimiento | 20% | 15 m/h equivale a 100 puntos. |
| Horas no efectivas | 15% | Penaliza la proporción de horas no efectivas sobre horas totales. |
| Alertas operacionales | 15% | Penaliza la proporción de alertas sobre registros analizados. |

Fórmula:

```text
score_utilización = min(Utilización promedio / 85 * 100, 100)
score_disponibilidad = min(Disponibilidad promedio / 90 * 100, 100)
score_rendimiento = min(Rendimiento promedio / 15 * 100, 100)
score_horas = 100 - (Horas no efectivas / Horas totales * 100)
score_alertas = 100 - (Cantidad alertas / Cantidad registros * 100)

Índice salud =
  score_utilización * 0.25
  + score_disponibilidad * 0.25
  + score_rendimiento * 0.20
  + score_horas * 0.15
  + score_alertas * 0.15
```

Todos los puntajes parciales se limitan al rango 0-100.

Semáforo ejecutivo:

| Rango índice | Estado | Lectura |
|---:|---|---|
| 75 a 100 | Verde | Operación estable. |
| 50 a 74.99 | Amarillo | Atención requerida. |
| 0 a 49.99 | Rojo | Condición crítica. |

Rankings ejecutivos:

- Equipos con mejor rendimiento.
- Equipos con menor utilización.
- Operadores con mayor metraje.
- Principales causas de detención.

La tendencia semanal se muestra solo si existen al menos 7 fechas con registros válidos.

## Motor Inteligente de Alertas

La página `pages/09_Alertas_Inteligentes.py` consume el servicio `services/smart_alerts_service.py`. El motor trabaja sobre SQLite, persiste alertas y evita recalcular el histórico completo innecesariamente.

Persistencia:

- Las alertas se guardan en la tabla `alertas_inteligentes`.
- El avance incremental se controla con `alertas_inteligentes_control`.
- Cada alerta tiene `alert_key` única para no duplicar detecciones ya registradas.

Estados:

| Estado | Significado |
|---|---|
| pendiente | Alerta detectada y no reconocida todavía. |
| vista | Alerta revisada por el usuario. |
| atendida | Alerta reconocida y cerrada operativamente. |

Clasificación:

| Nivel | Uso |
|---|---|
| INFO | Desviación leve o de seguimiento. |
| PREVENTIVA | Requiere atención y prevención. |
| CRÍTICA | Riesgo operativo alto o condición deteriorada. |

Reglas del motor:

- Baja utilización: utilización por debajo del umbral operativo definido por el motor.
- Baja disponibilidad: disponibilidad por debajo del umbral operativo definido por el motor.
- Rendimiento bajo promedio: rendimiento menor al umbral base del motor o muy por debajo de la tendencia histórica.
- Exceso de horas no efectivas: tiempo no productivo por sobre el umbral de control.
- Exceso de repaso: presencia explícita de repaso o repetición de trabajo.
- Operador fuera de tendencia: caída relevante frente al comportamiento histórico del mismo operador.
- Equipo con detenciones recurrentes: repetición de detenciones en una ventana histórica reciente.
- Equipo con caída progresiva de rendimiento: secuencia descendente en la ventana reciente del equipo.
- Exceso de cambios de aceros: conteo o intensidad superior al umbral del motor.
- Diferencia anormal entre operadores del mismo equipo: dispersión excesiva entre rendimientos por operador en el mismo equipo.

Reglas de operación:

- El motor solo procesa registros nuevos o pendientes respecto del último `id` procesado.
- El historial se usa en ventanas acotadas por equipo y operador para contextualizar cada nuevo registro.
- Los cambios de estado de alertas no eliminan la alerta original.
- Las alertas pueden marcarse como `vista` o `atendida` sin perder el histórico.
- La interfaz debe permitir filtrar por fecha, turno, equipo, operador, criticidad y estado.

## Corrección de Texto Visible

La corrección de mojibake se centraliza en `text_utils.reparar_mojibake`. Las vistas deben pasar textos visibles, etiquetas y encabezados tabulares por helpers de formato cuando corresponda.

Casos cubiertos por contrato:

| Entrada dañada | Salida esperada |
|---|---|
| `D\\u00c3\\u00ada` | Día |
| `Mantenci\\u00c3\\u00b3n` | Mantención |
| `N\\u00c3\\u00bamero` | Número |
| `utilizaci\\u00c3\\u00b3n` | utilización |
| `maners\\u00c3\\u00b3` | manera |

Esta reparación aplica a texto visible y nombres de columnas. No debe alterar reglas de cálculo, valores numéricos ni históricos almacenados salvo normalización controlada de encabezados/etiquetas.

## Criterios de Evolución

Para agregar nuevos campos o categorías:

- Declarar el campo visible en `schema.py` si forma parte del contrato persistido.
- Agregar clave interna estable si proviene del formulario.
- Mantener alias de compatibilidad si reemplaza un nombre anterior.
- Agregar pruebas de payload, normalización y cálculo cuando afecte guardado, KPIs o dashboards.
- Evitar renombrar campos oficiales usados por Excel, SQLite, PDF o dashboards sin migración explícita.
