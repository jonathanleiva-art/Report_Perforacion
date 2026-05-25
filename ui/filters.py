import pandas as pd
import streamlit as st

import db
from ui.formatting import texto_visible
from utils import TIPOS_DETENCION, opciones_desde_historial


def _opciones_desde_sql(columna):
    try:
        valores = db.obtener_valores_distintos_columna(columna)
    except Exception:
        valores = []
    return valores


def aplicar_filtros(df):
    if df.empty and not db.DB_PATH.exists():
        return df

    rango_defecto = db.obtener_rango_fechas()
    with st.sidebar:
        st.header("Filtros")

        if all(valor is not None for valor in rango_defecto):
            rango = st.date_input(
                "Rango de fechas",
                value=rango_defecto,
                min_value=rango_defecto[0],
                max_value=rango_defecto[1],
            )
        else:
            rango = st.date_input("Rango de fechas", value=None)

        equipos = _opciones_desde_sql("Equipo") or sorted(df.get("Equipo", pd.Series(dtype=str)).dropna().astype(str).unique())
        operadores = _opciones_desde_sql("Operador") or sorted(df.get("Operador", pd.Series(dtype=str)).dropna().astype(str).unique())
        turnos = _opciones_desde_sql("Turno") or sorted(df.get("Turno", pd.Series(dtype=str)).dropna().astype(str).unique())
        tipos_detencion = _opciones_desde_sql("Tipo detención")
        if not tipos_detencion:
            tipos_detencion = opciones_desde_historial(df, "Tipo detención", TIPOS_DETENCION)
        else:
            tipos_detencion = sorted(
                dict.fromkeys(
                    parte.strip()
                    for valor in tipos_detencion
                    for parte in str(valor).split(",")
                    if parte.strip()
                )
            )

        filtro_equipos = st.multiselect("Equipo", equipos, default=equipos)
        filtro_operadores = st.multiselect("Operador", operadores, default=operadores)
        filtro_turnos = st.multiselect("Turno", turnos, default=turnos, format_func=texto_visible)
        filtro_tipos_detencion = st.multiselect(
            "Tipo detención",
            tipos_detencion,
            default=tipos_detencion,
            format_func=texto_visible,
        )

    filtros_sql = {
        "fecha_desde": None,
        "fecha_hasta": None,
        "turno": filtro_turnos,
        "equipo": filtro_equipos,
        "operador": filtro_operadores,
        "banco": None,
        "malla": None,
    }
    if isinstance(rango, tuple) and len(rango) == 2:
        filtros_sql["fecha_desde"], filtros_sql["fecha_hasta"] = rango

    st.session_state["dashboard_sql_filters"] = filtros_sql

    if db.DB_PATH.exists():
        try:
            filtrado = db.consultar_historial_filtrado(
                fecha_desde=filtros_sql["fecha_desde"],
                fecha_hasta=filtros_sql["fecha_hasta"],
                turno=filtros_sql["turno"],
                equipo=filtros_sql["equipo"],
                operador=filtros_sql["operador"],
            )
        except Exception:
            filtrado = df.copy()
    else:
        filtrado = df.copy()

    if filtrado.empty:
        return filtrado

    if (
        filtro_tipos_detencion
        and "Tipo detención" in filtrado.columns
        and set(filtro_tipos_detencion) != set(tipos_detencion)
    ):
        seleccionados = set(filtro_tipos_detencion)
        filtrado = filtrado[
            filtrado["Tipo detención"].fillna("").astype(str).apply(
                lambda valor: bool(
                    seleccionados.intersection(
                        item.strip() for item in valor.split(",") if item.strip()
                    )
                )
            )
        ]

    return filtrado
