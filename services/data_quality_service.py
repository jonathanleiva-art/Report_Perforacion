import pandas as pd

import db


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

    cols_dup = ["Fecha turno", "Turno", "Número equipo", "Operador"]
    if all(col in base.columns for col in cols_dup):
        base_dup = base.copy()
        base_dup["_clave_dup"] = (
            base_dup["Fecha turno"].fillna("").astype(str).str.strip()
            + "|"
            + base_dup["Turno"].fillna("").astype(str).str.strip()
            + "|"
            + base_dup["Número equipo"].fillna("").astype(str).str.strip()
            + "|"
            + base_dup["Operador"].fillna("").astype(str).str.strip()
        )
        duplicados = base_dup[base_dup["_clave_dup"].duplicated(keep=False)]
        if not duplicados.empty:
            observaciones.extend(
                _filas_a_observaciones(
                    base_dup,
                    duplicados.index.tolist(),
                    "Duplicado por Fecha turno + Turno + Número equipo + Operador",
                    "ERROR",
                    "Se detectó un registro duplicado por clave operacional.",
                    "Revisar captura duplicada antes de consolidar el historial.",
                    valor_observado="Clave duplicada",
                )
            )
    else:
        faltantes = [col for col in cols_dup if col not in base.columns]
        reglas_no_evaluadas.add("Duplicado por Fecha turno + Turno + Número equipo + Operador")
        observaciones.extend(
            _no_evaluada(
                "Duplicado por Fecha turno + Turno + Número equipo + Operador",
                cols_dup,
                faltantes,
            )
        )

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
        orden_estado = {"ERROR": 0, "WARNING": 1, "NO_EVALUADA": 2}
        for valor in detalle.sort_values(
            by="Estado",
            key=lambda s: s.map(orden_estado).fillna(3),
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
    orden = {"ERROR": 0, "WARNING": 1, "NO_EVALUADA": 2}
    resumen["_orden"] = resumen["Estado predominante"].map(orden).fillna(3)
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
