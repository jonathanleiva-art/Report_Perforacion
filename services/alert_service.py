import pandas as pd

from schema import columnas_equivalentes
from services import kpi_service


def evaluar_alertas_operacionales(df, horas_turno=12):
    if df.empty:
        return {"mensajes": [], "detalle": pd.DataFrame(), "sin_alertas": False}

    mensajes = []
    tipos_alerta = pd.Series("", index=df.index, dtype=str)

    evaluar_inconsistencia_disponibilidad_mantencion(df, mensajes, tipos_alerta)
    evaluar_baja_utilizacion(df, mensajes, tipos_alerta)
    evaluar_bajo_rendimiento(df, mensajes, tipos_alerta)
    evaluar_inconsistencia_horas_turno(df, mensajes, tipos_alerta, horas_turno)

    return {
        "mensajes": mensajes,
        "detalle": construir_detalle_alertas(df, tipos_alerta),
        "sin_alertas": not mensajes,
    }


def evaluar_inconsistencia_disponibilidad_mantencion(df, mensajes, tipos_alerta):
    disponibilidad = serie_numerica(df, *columnas_equivalentes("disponibilidad"))
    mantencion = serie_numerica(df, *columnas_equivalentes("horas_mantencion"))
    if disponibilidad.empty or mantencion.empty:
        return

    conflicto_mantencion = disponibilidad.ge(99.99) & mantencion.gt(0)
    if not conflicto_mantencion.any():
        return

    mensajes.append((
        "error",
        f"{int(conflicto_mantencion.sum())} registro(s) con disponibilidad 100% "
        "y horas de mantención programada.",
    ))
    tipos_alerta.loc[conflicto_mantencion] = tipos_alerta.loc[conflicto_mantencion].apply(
        lambda valor: agregar_tipo_alerta(valor, "Disponibilidad 100% con mantención")
    )


def evaluar_baja_utilizacion(df, mensajes, tipos_alerta):
    utilizacion = serie_numerica(df, *columnas_equivalentes("utilizacion"))
    if utilizacion.empty:
        return

    utilizacion_baja = utilizacion.lt(50)
    if not utilizacion_baja.any():
        return

    mensajes.append((
        "warning",
        f"{int(utilizacion_baja.sum())} registro(s) con utilización muy baja "
        f"(< 50%). Promedio: {formato_numero(utilizacion.mean(), 2, '%')}.",
    ))
    tipos_alerta.loc[utilizacion_baja] = tipos_alerta.loc[utilizacion_baja].apply(
        lambda valor: agregar_tipo_alerta(valor, "Utilización muy baja")
    )


def evaluar_bajo_rendimiento(df, mensajes, tipos_alerta):
    metros, _, rendimiento = totales_productivos(df)
    if metros > 0 and rendimiento < 10:
        mensajes.append((
            "warning",
            f"Rendimiento bajo: {formato_numero(rendimiento, 2)} m/h "
            f"con {formato_numero(metros, 2)} metros productivos.",
        ))
        rendimiento_fila = serie_numerica(df, *columnas_equivalentes("rendimiento"))
        if not rendimiento_fila.empty:
            rendimiento_bajo = rendimiento_fila.gt(0) & rendimiento_fila.lt(10)
            tipos_alerta.loc[rendimiento_bajo] = tipos_alerta.loc[rendimiento_bajo].apply(
                lambda valor: agregar_tipo_alerta(valor, "Rendimiento bajo")
            )
    elif metros == 0:
        mensajes.append(("warning", "No hay metros productivos para calcular rendimiento operacional."))


def evaluar_inconsistencia_horas_turno(df, mensajes, tipos_alerta, horas_turno):
    horas = serie_numerica(df, "Horas turno")
    if horas.empty:
        return

    turnos_invalidos = (horas - horas_turno).abs().gt(0.01)
    if not turnos_invalidos.any():
        return

    mensajes.append((
        "warning",
        f"{int(turnos_invalidos.sum())} registro(s) con horas de turno distintas "
        f"de {formato_numero(horas_turno, 0)} h.",
    ))
    tipos_alerta.loc[turnos_invalidos] = tipos_alerta.loc[turnos_invalidos].apply(
        lambda valor: agregar_tipo_alerta(valor, "Horas turno distintas de 12")
    )


def evaluar_baja_disponibilidad(df, umbral=60):
    disponibilidad = serie_numerica(df, *columnas_equivalentes("disponibilidad"))
    return disponibilidad.lt(umbral) if not disponibilidad.empty else pd.Series(False, index=df.index)


def evaluar_equipos_sin_marcacion(df):
    horas = serie_numerica(df, *columnas_equivalentes("sin_marcacion"))
    sin_marcacion_horas = horas.gt(0) if not horas.empty else pd.Series(False, index=df.index)
    if "Tipo detención" not in df.columns:
        return sin_marcacion_horas
    sin_marcacion_tipo = df["Tipo detención"].astype(str).str.contains("Sin marcación", case=False, na=False)
    return sin_marcacion_horas | sin_marcacion_tipo


def evaluar_detenciones_altas(df, horas_turno=12, proporcion=0.35):
    horas_no_efectivas = serie_numerica(df, *columnas_equivalentes("horas_no_efectivas"))
    horas_averia = serie_numerica(df, *columnas_equivalentes("horas_averia"))
    if horas_no_efectivas.empty:
        horas_no_efectivas = pd.Series(0, index=df.index)
    if horas_averia.empty:
        horas_averia = pd.Series(0, index=df.index)
    umbral = max(float(horas_turno) * float(proporcion), 0)
    return (horas_no_efectivas + horas_averia).ge(umbral)


def normalizar_nombre_columna(nombre):
    return kpi_service.normalizar_nombre_columna(nombre)


def buscar_columna(df, *candidatos):
    return kpi_service.buscar_columna(df, *candidatos)


def serie_numerica(df, *columnas):
    return kpi_service.serie_numerica(df, *columnas)


def totales_productivos(df):
    return kpi_service.totales_productivos(df)


def formato_numero(valor, decimales=2, sufijo=""):
    numero = pd.to_numeric(pd.Series([valor]), errors="coerce").fillna(0).iloc[0]
    return f"{numero:,.{decimales}f}{sufijo}"


def agregar_tipo_alerta(valor, alerta):
    return f"{valor}, {alerta}" if valor else alerta


def construir_detalle_alertas(df, tipos_alerta):
    indices_alerta = tipos_alerta[tipos_alerta.astype(str).str.strip().ne("")].index
    if len(indices_alerta) == 0:
        return pd.DataFrame()

    base = df.loc[indices_alerta].copy()
    columnas_detalle = [
        ("Fecha", [*columnas_equivalentes("fecha_turno"), "Fecha"]),
        ("Turno", columnas_equivalentes("turno")),
        ("Equipo", ["Equipo", "Modelo equipo"]),
        ("Número de equipo", columnas_equivalentes("numero_equipo")),
        ("Operador", columnas_equivalentes("operador")),
        ("Disponibilidad %", columnas_equivalentes("disponibilidad")),
        ("Utilización %", columnas_equivalentes("utilizacion")),
        ("Rendimiento m/h", columnas_equivalentes("rendimiento")),
        ("Mantención programada", columnas_equivalentes("horas_mantencion")),
        ("Total horas turno", ["Horas turno"]),
    ]

    detalle = pd.DataFrame(index=base.index)
    for salida, candidatos in columnas_detalle:
        columna = buscar_columna(base, *candidatos)
        if columna:
            detalle[salida] = base[columna]

    detalle["Tipo de alerta"] = tipos_alerta.loc[indices_alerta].values
    detalle["Recomendación operacional"] = detalle["Tipo de alerta"].apply(recomendacion_alerta)
    if "Fecha" in detalle.columns:
        detalle["Fecha"] = pd.to_datetime(detalle["Fecha"], errors="coerce").dt.strftime("%d-%m-%Y")

    return detalle.reset_index(drop=True)


def recomendacion_alerta(tipo_alerta):
    recomendaciones = {
        "Utilización muy baja": "Revisar detenciones, tiempos no efectivos y continuidad operacional.",
        "Rendimiento bajo": "Revisar tipo de terreno, parámetros de perforación y condición de aceros.",
        "Disponibilidad 100% con mantención": "Revisar cálculo de disponibilidad; la mantención debe afectar la disponibilidad del equipo.",
        "Horas turno distintas de 12": "Revisar suma de horas efectivas, no efectivas y averías.",
    }
    return " ".join(
        recomendaciones[alerta]
        for alerta in [parte.strip() for parte in str(tipo_alerta).split(",") if parte.strip()]
        if alerta in recomendaciones
    )
