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


def _seleccion_o_todo(seleccion, opciones):
    if not seleccion:
        return list(opciones)
    validas = [valor for valor in seleccion if valor in opciones]
    return validas or list(opciones)


def _normalizar_rango_fechas(rango, rango_defecto):
    if isinstance(rango, (tuple, list)):
        valores = [valor for valor in rango if valor is not None]
        if len(valores) >= 2:
            return valores[0], valores[-1]
        if len(valores) == 1:
            return valores[0], valores[0]
    if rango is None:
        if isinstance(rango_defecto, (tuple, list)) and len(rango_defecto) == 2:
            return rango_defecto[0], rango_defecto[1]
        return None, None
    return rango, rango


def _contar_seguro(**filtros):
    try:
        return db.contar_historial_filtrado(**filtros)
    except Exception:
        return 0


def _restablecer_filtros_dashboard(claves):
    for clave in claves:
        st.session_state.pop(clave, None)
    st.session_state.pop("dashboard_sql_filters", None)
    st.rerun()


def aplicar_filtros(df):
    if df.empty and not db.DB_PATH.exists():
        return df

    rango_defecto = db.obtener_rango_fechas()
    claves_widgets = [
        "dashboard_fecha",
        "dashboard_equipos",
        "dashboard_operadores",
        "dashboard_turnos",
        "dashboard_tipos_detencion",
        "dashboard_bancos",
        "dashboard_mallas",
        "dashboard_fases",
        "dashboard_tipos_perforacion",
    ]
    with st.sidebar:
        st.header("Filtros")
        if st.button("Restablecer filtros", use_container_width=True):
            _restablecer_filtros_dashboard(claves_widgets)

        if all(valor is not None for valor in rango_defecto):
            rango = st.date_input(
                "Rango de fechas",
                value=rango_defecto,
                min_value=rango_defecto[0],
                max_value=rango_defecto[1],
                format="DD/MM/YYYY",
                key="dashboard_fecha",
            )
        else:
            rango = st.date_input("Rango de fechas", value=None, format="DD/MM/YYYY", key="dashboard_fecha")

        equipos = _opciones_desde_sql("Equipo") or sorted(df.get("Equipo", pd.Series(dtype=str)).dropna().astype(str).unique())
        operadores = _opciones_desde_sql("Operador") or sorted(df.get("Operador", pd.Series(dtype=str)).dropna().astype(str).unique())
        turnos = _opciones_desde_sql("Turno") or sorted(df.get("Turno", pd.Series(dtype=str)).dropna().astype(str).unique())
        bancos = _opciones_desde_sql("Banco") or sorted(df.get("Banco", pd.Series(dtype=str)).dropna().astype(str).unique())
        mallas = _opciones_desde_sql("Malla") or sorted(df.get("Malla", pd.Series(dtype=str)).dropna().astype(str).unique())
        fases = _opciones_desde_sql("Fase") or sorted(df.get("Fase", pd.Series(dtype=str)).dropna().astype(str).unique())
        tipos_perforacion = _opciones_desde_sql("Tipo de perforación") or sorted(df.get("Tipo de perforación", pd.Series(dtype=str)).dropna().astype(str).unique())
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

        filtro_equipos = st.multiselect("Equipo", equipos, default=equipos, key="dashboard_equipos")
        filtro_operadores = st.multiselect("Operador", operadores, default=operadores, key="dashboard_operadores")
        filtro_turnos = st.multiselect("Turno", turnos, default=turnos, format_func=texto_visible, key="dashboard_turnos")
        filtro_tipos_detencion = st.multiselect(
            "Tipo detención",
            tipos_detencion,
            default=tipos_detencion,
            format_func=texto_visible,
            key="dashboard_tipos_detencion",
        )
        filtro_bancos = st.multiselect("Banco", bancos, default=bancos, key="dashboard_bancos")
        filtro_mallas = st.multiselect("Malla", mallas, default=mallas, key="dashboard_mallas")
        filtro_fases = st.multiselect("Fase", fases, default=fases, key="dashboard_fases")
        filtro_tipos_perforacion = st.multiselect(
            "Tipo de perforación",
            tipos_perforacion,
            default=tipos_perforacion,
            key="dashboard_tipos_perforacion",
        )

    filtro_equipos = _seleccion_o_todo(filtro_equipos, equipos)
    filtro_operadores = _seleccion_o_todo(filtro_operadores, operadores)
    filtro_turnos = _seleccion_o_todo(filtro_turnos, turnos)
    filtro_tipos_detencion = _seleccion_o_todo(filtro_tipos_detencion, tipos_detencion)
    filtro_bancos = _seleccion_o_todo(filtro_bancos, bancos)
    filtro_mallas = _seleccion_o_todo(filtro_mallas, mallas)
    filtro_fases = _seleccion_o_todo(filtro_fases, fases)
    filtro_tipos_perforacion = _seleccion_o_todo(filtro_tipos_perforacion, tipos_perforacion)

    filtros_sql = {
        "fecha_inicio": None,
        "fecha_fin": None,
        "turnos": filtro_turnos,
        "equipos": filtro_equipos,
        "operadores": filtro_operadores,
        "tipos_detencion": filtro_tipos_detencion,
        "banco": filtro_bancos,
        "malla": filtro_mallas,
        "fase": filtro_fases,
        "tipo_perforacion": filtro_tipos_perforacion,
    }
    filtros_sql["fecha_inicio"], filtros_sql["fecha_fin"] = _normalizar_rango_fechas(rango, rango_defecto)

    st.session_state["dashboard_sql_filters"] = filtros_sql

    diagnostico = {
        "total_base": _contar_seguro(),
        "por_fecha": _contar_seguro(
            fecha_inicio=filtros_sql.get("fecha_inicio"),
            fecha_fin=filtros_sql.get("fecha_fin"),
        ),
        "por_equipo": _contar_seguro(equipos=filtro_equipos),
        "por_operador": _contar_seguro(operadores=filtro_operadores),
        "resultado_final": 0,
        "fecha_inicio": filtros_sql.get("fecha_inicio"),
        "fecha_fin": filtros_sql.get("fecha_fin"),
        "equipos": filtro_equipos,
        "operadores": filtro_operadores,
        "turnos": filtro_turnos,
        "tipos_detencion": filtro_tipos_detencion,
        "banco": filtro_bancos,
        "malla": filtro_mallas,
        "fase": filtro_fases,
        "tipo_perforacion": filtro_tipos_perforacion,
    }

    if db.DB_PATH.exists():
        try:
            filtrado = db.consultar_historial_filtrado(**filtros_sql)
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

    diagnostico["resultado_final"] = len(filtrado)
    st.session_state["dashboard_filter_diagnostics"] = diagnostico

    return filtrado
