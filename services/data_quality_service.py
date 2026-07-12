import pandas as pd

import db
from schema import SQLITE_TECHNICAL_COLUMNS, columna_canonica, es_columna_canonica

# ---------------------------------------------------------------------------
# Reglas de negocio para asignación operador/máquina
#
# ESCENARIO A — mismo operador, >1 máquina, mismo turno+fecha
#   No es error automático: puede ser cobertura válida cuando falta personal.
#   Se reporta como WARNING "Doble asignación — requiere validación".
#   El supervisor debe confirmar en campo Observaciones.
#
# ESCENARIO B — misma máquina, >1 operador, mismo turno+fecha
#   Puede ser:
#     • Traslape de horas (suma horas > 12h turno) → ERROR: posible doble cobro
#     • Vacío de horas (suma horas < 12h turno)   → ERROR: quién cubrió el resto?
#     • Encadenamiento perfecto (suma ≈ 12h)       → WARNING "Relevo de turno"
#   Nota: al no existir campo hora_inicio/hora_fin, el encadenamiento se
#   infiere sumando Horas efectivas + Detención No efectivas + Detención mecánica.
#   Si esa suma falta, se reporta como WARNING por defecto.
# ---------------------------------------------------------------------------


def _columna_existente(df, *candidatos):
    for candidato in candidatos:
        if candidato in df.columns:
            return candidato
    return None


def _serie_texto(df, columna):
    if columna not in df.columns:
        return None
    return df[columna].fillna("").astype(str).str.strip()


def _serie_numerica(df, columna):
    if columna not in df.columns:
        return None
    return pd.to_numeric(df[columna], errors="coerce")


def _base_df(
    df=None,
    db_path=db.DB_PATH,
    fecha_desde=None,
    fecha_hasta=None,
    turno=None,
    equipo=None,
    operador=None,
):
    if df is not None:
        return df.copy()
    return db.consultar_historial_filtrado(
        db_path=db_path,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        turno=turno,
        equipo=equipo,
        operador=operador,
    )


def diagnosticar_contrato_columnas(df=None, columnas=None, ignorar_tecnicas=True):
    columnas = list(columnas if columnas is not None else getattr(df, "columns", []))
    tecnicas = set(SQLITE_TECHNICAL_COLUMNS) if ignorar_tecnicas else set()
    canonicas = []
    no_canonicas = []
    extras = []

    for columna in columnas:
        nombre = str(columna).strip()
        if not nombre or nombre in tecnicas:
            continue
        canonica = columna_canonica(nombre)
        if canonica != nombre:
            no_canonicas.append({
                "columna": nombre,
                "columna_canonica": canonica,
            })
        elif es_columna_canonica(nombre):
            canonicas.append(nombre)
        else:
            extras.append(nombre)

    return {
        "total_columnas": len(canonicas) + len(no_canonicas) + len(extras),
        "columnas_canonicas": canonicas,
        "columnas_no_canonicas": no_canonicas,
        "columnas_extra": extras,
        "total_no_canonicas": len(no_canonicas),
        "total_extra": len(extras),
    }


def _filas_a_observaciones(df, indices, regla, tipo, mensaje, recomendacion, valor_observado=None):
    if not indices:
        return []

    filas = df.loc[indices].copy()
    observaciones = []
    for idx, (_, fila) in zip(indices, filas.iterrows()):
        observaciones.append(
            {
                "fila": int(idx) + 1,
                "Fecha turno": fila.get("Fecha turno", ""),
                "Turno": fila.get("Turno", ""),
                "Modelo equipo": fila.get("Modelo equipo", ""),
                "Número equipo": fila.get("Número equipo", ""),
                "Operador": fila.get("Operador", ""),
                "Regla": regla,
                "Estado": tipo,
                "Mensaje": mensaje,
                "Recomendación operacional": recomendacion,
                "Valor observado": valor_observado,
            }
        )
    return observaciones


def _no_evaluada(regla, columnas_requeridas, faltantes):
    _ = columnas_requeridas
    return [
        {
            "fila": "",
            "Fecha turno": "",
            "Turno": "",
            "Modelo equipo": "",
            "Número equipo": "",
            "Operador": "",
            "Regla": regla,
            "Estado": "NO_EVALUADA",
            "Mensaje": f"Regla no evaluada por columna faltante: {', '.join(faltantes)}",
            "Recomendación operacional": "Verificar la estructura de datos antes de evaluar esta regla.",
            "Valor observado": "",
        }
    ]


def clasificar_estado_calidad(score):
    score = float(score or 0)
    if score >= 90:
        return {
            "estado": "excelente",
            "titulo": "Excelente",
            "mensaje": "La calidad de datos es sólida y no muestra desviaciones relevantes.",
            "color": "#16A34A",
        }
    if score >= 75:
        return {
            "estado": "aceptable",
            "titulo": "Aceptable",
            "mensaje": "La calidad es razonable, pero hay puntos puntuales que conviene revisar.",
            "color": "#2563EB",
        }
    if score >= 60:
        return {
            "estado": "observado",
            "titulo": "Observado",
            "mensaje": "Existen inconsistencias que requieren seguimiento operativo.",
            "color": "#D97706",
        }
    return {
        "estado": "critico",
        "titulo": "Crítico",
        "mensaje": "La calidad de datos requiere corrección prioritaria antes de consolidar reportes.",
        "color": "#DC2626",
    }


def _detectar_doble_asignacion_operador(base):
    """Escenario A: mismo operador en >1 máquina, mismo turno+fecha.
    Subdivide en dos subtipos según productividad real (Metros perforados):

    • Cobertura administrativa (auto-válida):
      0 o 1 equipo del grupo tiene metros > 0. El operador figura
      administrativamente en los demás sin producción real — patrón normal
      cuando falta personal disponible. No requiere confirmación manual.

    • Doble asignación real (requiere validación):
      2 o más equipos del grupo registran metros > 0 el mismo turno/fecha.
      Implica productividad simultánea en máquinas distintas — situación
      poco frecuente que debe revisarse para descartar error de digitación.

    Retorna (indices_cobertura, indices_simultanea, indices_copia).

    • indices_cobertura:  ≤1 equipo con metros > 0 → cobertura admin (INFO)
    • indices_simultanea: 2+ equipos con metros distintos entre sí → producción
                          simultánea en varias máquinas (WARNING — raro pero posible)
    • indices_copia:      2+ equipos con metros EXACTAMENTE iguales → alta
                          probabilidad de fila copiada en la planilla (WARNING)
    """
    cols = ["Fecha turno", "Turno", "Número equipo", "Operador"]
    if not all(col in base.columns for col in cols):
        return [], [], []

    col_metros = "Metros perforados"
    tiene_metros = col_metros in base.columns

    tmp = base.copy()
    tmp["_clave_op"] = (
        tmp["Fecha turno"].fillna("").astype(str).str.strip()
        + "|" + tmp["Turno"].fillna("").astype(str).str.strip()
        + "|" + tmp["Operador"].fillna("").astype(str).str.strip()
    )
    mask_op_valido = tmp["Operador"].fillna("").astype(str).str.strip().ne("")
    n_equipos = tmp.groupby("_clave_op")["Número equipo"].transform(
        lambda s: s.astype(str).str.strip().nunique()
    )
    candidatos = tmp[mask_op_valido & (n_equipos > 1)]

    indices_cobertura: list = []
    indices_simultanea: list = []
    indices_copia: list = []

    for _, grupo in candidatos.groupby("_clave_op"):
        if tiene_metros:
            metros = pd.to_numeric(grupo[col_metros], errors="coerce").fillna(0)
            metros_productivos = metros[metros > 0]
            equipos_con_metros = int((metros > 0).sum())
        else:
            metros_productivos = pd.Series([], dtype=float)
            equipos_con_metros = 0  # sin columna → tratar como cobertura

        if equipos_con_metros >= 2:
            # 2+ equipos productivos: distinguir por unicidad de valor
            if metros_productivos.nunique() == 1:
                # Todos los equipos productivos reportan el mismo valor exacto
                # → sospecha de copiado de fila en planilla Excel
                indices_copia.extend(grupo.index.tolist())
            else:
                # Valores distintos → producción simultánea en varias máquinas
                indices_simultanea.extend(grupo.index.tolist())
        else:
            # 0 o 1 equipo productivo → asignación administrativa válida
            indices_cobertura.extend(grupo.index.tolist())

    return indices_cobertura, indices_simultanea, indices_copia


_HORAS_TURNO_NOMINAL = 12.0
_HORAS_TOLERANCIA = 0.05


def _clasificar_conflicto_maquina(base):
    """Escenario B: misma máquina, >1 operador distinto, mismo turno+fecha.
    Devuelve (indices_error, indices_relevo).
    - indices_error  → traslape o vacío de horas → ANOMALÍA REAL
    - indices_relevo → horas encadenan ≈ 12h    → WARNING relevo válido
    """
    cols = ["Fecha turno", "Turno", "Número equipo", "Operador"]
    if not all(col in base.columns for col in cols):
        return [], []

    tmp = base.copy()
    tmp["_clave_maq"] = (
        tmp["Fecha turno"].fillna("").astype(str).str.strip()
        + "|" + tmp["Turno"].fillna("").astype(str).str.strip()
        + "|" + tmp["Número equipo"].fillna("").astype(str).str.strip()
    )
    col_hef = "Horas efectivas perforando"
    col_hne = "Horas detención No efectivas"
    col_hme = "Horas detención mecánica"

    indices_error: list = []
    indices_relevo: list = []

    for _, grupo in tmp.groupby("_clave_maq"):
        ops = grupo["Operador"].fillna("").astype(str).str.strip()
        if ops.nunique() <= 1:
            continue  # solo 1 operador, sin conflicto

        # Calcular horas totales declaradas por todos los operadores del grupo
        tiene_horas = all(col in grupo.columns for col in [col_hef, col_hne, col_hme])
        if tiene_horas:
            suma_h = (
                pd.to_numeric(grupo[col_hef], errors="coerce").fillna(0)
                + pd.to_numeric(grupo[col_hne], errors="coerce").fillna(0)
                + pd.to_numeric(grupo[col_hme], errors="coerce").fillna(0)
            ).sum()
            if suma_h > _HORAS_TURNO_NOMINAL + _HORAS_TOLERANCIA:
                # Traslape: la suma supera las horas del turno → ERROR
                indices_error.extend(grupo.index.tolist())
            elif suma_h < _HORAS_TURNO_NOMINAL - _HORAS_TOLERANCIA:
                # Vacío: nadie cubre todas las horas → ERROR
                indices_error.extend(grupo.index.tolist())
            else:
                # Encadenamiento perfecto ≈ 12h → relevo plausible
                indices_relevo.extend(grupo.index.tolist())
        else:
            # Sin columnas de hora: no se puede determinar → relevo por defecto
            indices_relevo.extend(grupo.index.tolist())

    return indices_error, indices_relevo


def evaluar_calidad_datos(
    df=None,
    *,
    db_path=db.DB_PATH,
    fecha_desde=None,
    fecha_hasta=None,
    turno=None,
    equipo=None,
    operador=None,
):
    base = _base_df(
        df=df,
        db_path=db_path,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        turno=turno,
        equipo=equipo,
        operador=operador,
    )

    if base is None or base.empty:
        detalle_vacio = pd.DataFrame(
            columns=[
                "fila",
                "Fecha turno",
                "Turno",
                "Modelo equipo",
                "Número equipo",
                "Operador",
                "Regla",
                "Estado",
                "Mensaje",
                "Recomendación operacional",
                "Valor observado",
            ]
        )
        return {
            "total_registros": 0,
            "errores": 0,
            "advertencias": 0,
            "reglas_no_evaluadas": 0,
            "detalle": detalle_vacio,
            "recomendacion_operacional": "No hay registros para evaluar.",
            "recomendaciones": [],
        }

    observaciones = []
    reglas_no_evaluadas = set()

    reglas_incompletos = [
        ("Fecha turno vacía", "Fecha turno", "ERROR", "Registro incompleto", "Completar la fecha del turno antes de operar."),
        ("Modelo equipo vacío", "Modelo equipo", "ERROR", "Registro incompleto", "Completar el modelo del equipo."),
        ("Número equipo vacío", "Número equipo", "ERROR", "Registro incompleto", "Completar el número del equipo."),
        ("Operador vacío", "Operador", "ERROR", "Registro incompleto", "Completar el operador del turno."),
        ("Turno vacío", "Turno", "ERROR", "Registro incompleto", "Completar el turno."),
        ("Metros perforados vacío o nulo", "Metros perforados", "ERROR", "Registro incompleto", "Ingresar metros perforados."),
        ("Horas efectivas perforando vacía", "Horas efectivas perforando", "ERROR", "Registro incompleto", "Ingresar horas efectivas perforando."),
        ("Horas detención No efectivas vacía", "Horas detención No efectivas", "ERROR", "Registro incompleto", "Ingresar horas de detención no efectivas."),
        ("Horas detención mecánica vacía", "Horas detención mecánica", "ERROR", "Registro incompleto", "Ingresar horas de detención mecánica."),
    ]

    for regla, columna, tipo, mensaje, recomendacion in reglas_incompletos:
        if columna not in base.columns:
            reglas_no_evaluadas.add(regla)
            observaciones.extend(_no_evaluada(regla, [columna], [columna]))
            continue

        if columna in {"Metros perforados", "Horas efectivas perforando", "Horas detención No efectivas", "Horas detención mecánica"}:
            serie_num = _serie_numerica(base, columna)
            mascara = serie_num.isna()
        else:
            serie_texto = _serie_texto(base, columna)
            mascara = serie_texto.eq("")
        indices = base.index[mascara].tolist()
        observaciones.extend(_filas_a_observaciones(base, indices, regla, tipo, mensaje, recomendacion))

    requeridas_suma = ["Horas efectivas perforando", "Horas detención No efectivas", "Horas detención mecánica"]
    if all(col in base.columns for col in requeridas_suma):
        suma = (
            _serie_numerica(base, "Horas efectivas perforando").fillna(0)
            + _serie_numerica(base, "Horas detención No efectivas").fillna(0)
            + _serie_numerica(base, "Horas detención mecánica").fillna(0)
        )
        indices = base.index[(suma.round(6) != 12)].tolist()
        observaciones.extend(
            _filas_a_observaciones(
                base,
                indices,
                "Horas totales distintas de 12",
                "WARNING",
                "La suma de horas del turno no coincide con 12.",
                "Revisar distribución de horas y completar el turno correctamente.",
                valor_observado="Suma distinta de 12",
            )
        )
    else:
        faltantes = [col for col in requeridas_suma if col not in base.columns]
        reglas_no_evaluadas.add("Horas totales distintas de 12")
        observaciones.extend(_no_evaluada("Horas totales distintas de 12", requeridas_suma, faltantes))

    reglas_consistencia = [
        (
            "Metros perforados = 0 con horas efectivas > 0",
            "WARNING",
            "Hay horas efectivas sin metros perforados.",
            "Revisar procedimiento operativo y parámetros de perforación.",
        ),
        (
            "Mantención Programada con horas efectivas > 0",
            "WARNING",
            "Se registró mantención programada junto con horas efectivas.",
            "Validar si la mantención corresponde al mismo turno o debe reclasificarse.",
        ),
        (
            "Disponibilidad 100% sin producción",
            "WARNING",
            "La disponibilidad quedó en 100% sin metros ni horas efectivas.",
            "Revisar captura de producción o clasificación operacional.",
        ),
        (
            "Rendimiento m/h <= 0 con metros > 0",
            "ERROR",
            "Se registraron metros con rendimiento nulo o negativo.",
            "Corregir horas efectivas o revisar el cálculo de rendimiento.",
        ),
        (
            "Rendimiento m/h sobre 120",
            "WARNING",
            "El rendimiento excede el umbral operativo esperado.",
            "Revisar metros, horas efectivas o posibles errores de captura.",
        ),
    ]

    for regla, tipo, mensaje, recomendacion in reglas_consistencia:
        if regla == "Metros perforados = 0 con horas efectivas > 0":
            cols = ["Metros perforados", "Horas efectivas perforando"]
            if not all(col in base.columns for col in cols):
                reglas_no_evaluadas.add(regla)
                observaciones.extend(_no_evaluada(regla, cols, [col for col in cols if col not in base.columns]))
                continue
            metros = _serie_numerica(base, "Metros perforados").fillna(0)
            horas = _serie_numerica(base, "Horas efectivas perforando").fillna(0)
            indices = base.index[(metros.eq(0)) & (horas.gt(0))].tolist()
        elif regla == "Mantención Programada con horas efectivas > 0":
            cols = ["Mantención Programada", "Horas efectivas perforando"]
            if not all(col in base.columns for col in cols):
                reglas_no_evaluadas.add(regla)
                observaciones.extend(_no_evaluada(regla, cols, [col for col in cols if col not in base.columns]))
                continue
            mantencion = _serie_numerica(base, "Mantención Programada").fillna(0)
            horas = _serie_numerica(base, "Horas efectivas perforando").fillna(0)
            indices = base.index[(mantencion.gt(0)) & (horas.gt(0))].tolist()
        elif regla == "Disponibilidad 100% sin producción":
            cols = ["Disponibilidad %", "Metros perforados", "Horas efectivas perforando"]
            if not all(col in base.columns for col in cols):
                reglas_no_evaluadas.add(regla)
                observaciones.extend(_no_evaluada(regla, cols, [col for col in cols if col not in base.columns]))
                continue
            disponibilidad = _serie_numerica(base, "Disponibilidad %").fillna(0)
            metros = _serie_numerica(base, "Metros perforados").fillna(0)
            horas = _serie_numerica(base, "Horas efectivas perforando").fillna(0)
            indices = base.index[(disponibilidad.eq(100)) & (metros.eq(0)) & (horas.eq(0))].tolist()
        elif regla == "Rendimiento m/h <= 0 con metros > 0":
            cols = ["Metros perforados", "Rendimiento m/h"]
            if not all(col in base.columns for col in cols):
                reglas_no_evaluadas.add(regla)
                observaciones.extend(_no_evaluada(regla, cols, [col for col in cols if col not in base.columns]))
                continue
            metros = _serie_numerica(base, "Metros perforados").fillna(0)
            rendimiento = _serie_numerica(base, "Rendimiento m/h")
            indices = base.index[(metros.gt(0)) & (rendimiento.fillna(0).le(0))].tolist()
        else:
            cols = ["Rendimiento m/h"]
            if "Rendimiento m/h" not in base.columns:
                reglas_no_evaluadas.add(regla)
                observaciones.extend(_no_evaluada(regla, cols, cols))
                continue
            rendimiento = _serie_numerica(base, "Rendimiento m/h").fillna(0)
            indices = base.index[rendimiento.gt(120)].tolist()

        observaciones.extend(_filas_a_observaciones(base, indices, regla, tipo, mensaje, recomendacion))

    # ── Duplicado exacto: mismo operador + misma máquina + mismo turno + fecha ──
    # Captura el caso de doble guardado accidental del mismo formulario.
    cols_dup = ["Fecha turno", "Turno", "Número equipo", "Operador"]
    if all(col in base.columns for col in cols_dup):
        base_dup = base.copy()
        base_dup["_clave_dup"] = (
            base_dup["Fecha turno"].fillna("").astype(str).str.strip()
            + "|" + base_dup["Turno"].fillna("").astype(str).str.strip()
            + "|" + base_dup["Número equipo"].fillna("").astype(str).str.strip()
            + "|" + base_dup["Operador"].fillna("").astype(str).str.strip()
        )
        duplicados = base_dup[base_dup["_clave_dup"].duplicated(keep=False)]
        if not duplicados.empty:
            observaciones.extend(
                _filas_a_observaciones(
                    base_dup,
                    duplicados.index.tolist(),
                    "Duplicado exacto por Fecha+Turno+Equipo+Operador",
                    "ERROR",
                    "Registro duplicado exacto: misma combinación de fecha, turno, equipo y operador.",
                    "Eliminar el registro duplicado antes de consolidar el historial.",
                    valor_observado="Clave duplicada exacta",
                )
            )
    else:
        faltantes = [col for col in cols_dup if col not in base.columns]
        reglas_no_evaluadas.add("Duplicado exacto por Fecha+Turno+Equipo+Operador")
        observaciones.extend(
            _no_evaluada("Duplicado exacto por Fecha+Turno+Equipo+Operador", cols_dup, faltantes)
        )

    # ── Escenario A: mismo operador en >1 máquina, mismo turno+fecha ──
    # Subdividido por productividad: cobertura admin (INFO) vs doble real (WARNING).
    cols_esc_a = ["Fecha turno", "Turno", "Número equipo", "Operador"]
    if all(col in base.columns for col in cols_esc_a):
        idx_a_cobertura, idx_a_simultanea, idx_a_copia = _detectar_doble_asignacion_operador(base)

        # Subtipo 1 — Cobertura administrativa: ≤1 equipo con metros > 0 → INFO (válida)
        if idx_a_cobertura:
            observaciones.extend(
                _filas_a_observaciones(
                    base,
                    idx_a_cobertura,
                    "Escenario A: Cobertura administrativa — valida",
                    "INFO",
                    "Operador asignado a multiples maquinas pero con produccion real en una sola (o ninguna). "
                    "Patron de cobertura administrativa — no requiere confirmacion manual.",
                    "Sin accion requerida. Verificar que el registro administrativo es intencional.",
                    valor_observado="Cobertura admin valida",
                )
            )

        # Subtipo 2 — Producción simultánea: 2+ equipos con metros distintos → WARNING
        if idx_a_simultanea:
            observaciones.extend(
                _filas_a_observaciones(
                    base,
                    idx_a_simultanea,
                    "Escenario A: Produccion simultanea en multiples equipos",
                    "WARNING",
                    "El operador registra produccion real con metros DISTINTOS en mas de una maquina el mismo turno.",
                    "Verificar si la produccion en cada equipo es real o si hay error de digitacion. "
                    "Registrar motivo en campo Observaciones.",
                    valor_observado="Produccion simultanea valores distintos",
                )
            )

        # Subtipo 3 — Posible copia: 2+ equipos con metros EXACTAMENTE iguales → WARNING
        if idx_a_copia:
            observaciones.extend(
                _filas_a_observaciones(
                    base,
                    idx_a_copia,
                    "Escenario A: Posible duplicado por copiado — verificar",
                    "WARNING",
                    "El operador tiene el mismo valor de metros perforados en mas de una maquina el mismo turno. "
                    "Alta probabilidad de fila copiada en la planilla de origen.",
                    "Corroborar con el reporte fisico de terreno. Corregir o eliminar la fila duplicada.",
                    valor_observado="Metros identicos en multiples equipos",
                )
            )
    else:
        faltantes = [col for col in cols_esc_a if col not in base.columns]
        reglas_no_evaluadas.add("Escenario A: Doble asignacion de operador")
        observaciones.extend(_no_evaluada("Escenario A: Doble asignacion de operador", cols_esc_a, faltantes))

    # ── Escenario B: misma máquina, >1 operador distinto, mismo turno+fecha ──
    # Se subclasfifica según suma de horas (traslape/vacío = ERROR, encadenado = WARNING).
    cols_esc_b = ["Fecha turno", "Turno", "Número equipo", "Operador"]
    if all(col in base.columns for col in cols_esc_b):
        idx_b_error, idx_b_relevo = _clasificar_conflicto_maquina(base)
        if idx_b_error:
            observaciones.extend(
                _filas_a_observaciones(
                    base,
                    idx_b_error,
                    "Escenario B: Conflicto de maquina — traslape o vacio de horas",
                    "ERROR",
                    "Dos operadores distintos registran la misma maquina en el mismo turno con horas incompatibles.",
                    "Revisar si hay traslape de horas (doble cobro) o vacio de cobertura sin explicacion.",
                    valor_observado="Conflicto operador/maquina",
                )
            )
        if idx_b_relevo:
            observaciones.extend(
                _filas_a_observaciones(
                    base,
                    idx_b_relevo,
                    "Escenario B: Relevo de turno — requiere validacion",
                    "WARNING",
                    "Dos operadores comparten la misma maquina con horas encadenadas (posible relevo valido).",
                    "Confirmar que el relevo fue planificado y registrar motivo en campo Observaciones.",
                    valor_observado="Posible relevo valido",
                )
            )
    else:
        faltantes = [col for col in cols_esc_b if col not in base.columns]
        reglas_no_evaluadas.add("Escenario B: Conflicto de maquina")
        observaciones.extend(_no_evaluada("Escenario B: Conflicto de maquina", cols_esc_b, faltantes))

    detalle = pd.DataFrame(observaciones)
    if not detalle.empty:
        detalle = detalle.drop_duplicates().reset_index(drop=True)

    if detalle.empty:
        detalle = pd.DataFrame(
            columns=[
                "fila",
                "Fecha turno",
                "Turno",
                "Modelo equipo",
                "Número equipo",
                "Operador",
                "Regla",
                "Estado",
                "Mensaje",
                "Recomendación operacional",
                "Valor observado",
            ]
        )

    errores = int((detalle["Estado"] == "ERROR").sum()) if "Estado" in detalle.columns else 0
    advertencias = int((detalle["Estado"] == "WARNING").sum()) if "Estado" in detalle.columns else 0

    recomendaciones = []
    if not detalle.empty and "Recomendación operacional" in detalle.columns:
        orden_estado = {"ERROR": 0, "WARNING": 1, "INFO": 2, "NO_EVALUADA": 3}
        for valor in detalle.sort_values(
            by="Estado",
            key=lambda s: s.map(orden_estado).fillna(4),
        )["Recomendación operacional"].dropna().astype(str):
            texto = valor.strip()
            if texto and texto not in recomendaciones:
                recomendaciones.append(texto)

    recomendacion_operacional = recomendaciones[0] if recomendaciones else "Sin observaciones relevantes."

    return {
        "total_registros": int(len(base)),
        "errores": errores,
        "advertencias": advertencias,
        "reglas_no_evaluadas": int(len(reglas_no_evaluadas)),
        "detalle": detalle,
        "recomendacion_operacional": recomendacion_operacional,
        "recomendaciones": recomendaciones,
    }


def _resumen_problemas(detalle, limite=5):
    columnas = ["Regla", "Cantidad", "Estado predominante", "Recomendación operacional"]
    if detalle is None or detalle.empty or "Regla" not in detalle.columns:
        return pd.DataFrame(columns=columnas)

    base = detalle.copy()
    base["Regla"] = base["Regla"].fillna("").astype(str)
    base["Estado"] = base.get("Estado", pd.Series(dtype=str)).fillna("").astype(str)
    base["Recomendación operacional"] = base.get("Recomendación operacional", pd.Series(dtype=str)).fillna("").astype(str)

    registros = []
    for regla, grupo in base.groupby("Regla", dropna=False):
        estados = grupo["Estado"].astype(str)
        if (estados == "ERROR").any():
            estado_predominante = "ERROR"
        elif (estados == "WARNING").any():
            estado_predominante = "WARNING"
        elif (estados == "INFO").any():
            estado_predominante = "INFO"
        else:
            estado_predominante = "NO_EVALUADA"
        recomendacion = next((valor for valor in grupo["Recomendación operacional"].tolist() if str(valor).strip()), "")
        registros.append(
            {
                "Regla": regla,
                "Cantidad": int(len(grupo)),
                "Estado predominante": estado_predominante,
                "Recomendación operacional": recomendacion,
            }
        )

    resumen = pd.DataFrame(registros)
    orden = {"ERROR": 0, "WARNING": 1, "INFO": 2, "NO_EVALUADA": 3}
    resumen["_orden"] = resumen["Estado predominante"].map(orden).fillna(4)
    resumen = resumen.sort_values(["_orden", "Cantidad", "Regla"], ascending=[True, False, True]).drop(columns=["_orden"])
    return resumen.head(int(limite)).reset_index(drop=True)


def _registros_criticos_priorizados(detalle):
    columnas = [
        "fila",
        "Fecha turno",
        "Turno",
        "Modelo equipo",
        "Número equipo",
        "Operador",
        "Regla",
        "Estado",
        "Mensaje",
        "Recomendación operacional",
        "Valor observado",
    ]
    if detalle is None or detalle.empty or "Estado" not in detalle.columns:
        return pd.DataFrame(columns=columnas)

    base = detalle.copy()
    filtro = base[base["Estado"].astype(str).eq("ERROR")].copy()
    if filtro.empty:
        return filtro.reset_index(drop=True)

    filtro["_prioridad"] = 0
    if "fila" in filtro.columns:
        filtro["_prioridad"] += pd.to_numeric(filtro["fila"], errors="coerce").fillna(0)
    if "Regla" in filtro.columns:
        filtro["_prioridad"] += filtro["Regla"].astype(str).map(
            lambda valor: 0 if "Duplicado" in valor else 1 if "vacía" in valor.lower() else 2
        )
    columnas_presentes = [col for col in columnas if col in filtro.columns]
    return (
        filtro.sort_values(["_prioridad", "Regla"], ascending=[True, True])[columnas_presentes]
        .drop(columns=["_prioridad"], errors="ignore")
        .reset_index(drop=True)
    )


def calcular_score_calidad(df):
    resultado = evaluar_calidad_datos(df=df)
    total = max(int(resultado.get("total_registros", 0)), 1)
    errores = int(resultado.get("errores", 0))
    advertencias = int(resultado.get("advertencias", 0))
    no_eval = int(resultado.get("reglas_no_evaluadas", 0))

    penalizacion = (errores * 12.0) + (advertencias * 4.0) + (no_eval * 1.5)
    penalizacion = penalizacion / total
    score = max(0.0, min(100.0, 100.0 - penalizacion))
    return round(score, 2)


def generar_resumen_ejecutivo_calidad(df):
    evaluacion = evaluar_calidad_datos(df=df)
    score = calcular_score_calidad(df)
    estado = clasificar_estado_calidad(score)
    detalle = evaluacion.get("detalle", pd.DataFrame())
    top_problemas = _resumen_problemas(detalle, limite=5)
    registros_criticos = _registros_criticos_priorizados(detalle)

    total = max(int(evaluacion.get("total_registros", 0)), 1)
    errores = int(evaluacion.get("errores", 0))
    advertencias = int(evaluacion.get("advertencias", 0))
    no_eval = int(evaluacion.get("reglas_no_evaluadas", 0))

    if score >= 90:
        recomendacion = "Mantener controles actuales y monitorear muestras puntuales."
    elif score >= 75:
        recomendacion = "Atender los problemas recurrentes y reforzar validaciones previas."
    elif score >= 60:
        recomendacion = "Corregir inconsistencias antes de consolidar reportes operativos."
    else:
        recomendacion = "Priorizar corrección inmediata de errores críticos y revisar la captura de datos."

    resumen = pd.DataFrame(
        [
            {
                "Score calidad": score,
                "Estado": estado["titulo"],
                "Analizados": int(evaluacion.get("total_registros", 0)),
                "Errores": errores,
                "Advertencias": advertencias,
                "Reglas no evaluadas": no_eval,
                "Recomendación operacional": recomendacion,
                "Penalización por registro": round((100 - score) / total, 4),
            }
        ]
    )

    return {
        "score": score,
        "estado": estado,
        "recomendacion_operacional": recomendacion,
        "resumen": resumen,
        "top_problemas": top_problemas,
        "registros_criticos": registros_criticos,
        "evaluacion": evaluacion,
    }
