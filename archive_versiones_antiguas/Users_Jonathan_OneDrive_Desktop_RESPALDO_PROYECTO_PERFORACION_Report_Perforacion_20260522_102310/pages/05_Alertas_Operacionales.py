from pathlib import Path
import sys

import pandas as pd
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from data import leer_reportes
from schema import columnas_equivalentes
from services.alert_service import evaluar_alertas_operacionales
from utils import EXCEL_PATH


def dataframe_visible(df):
    if hasattr(app, "dataframe_visible"):
        return app.dataframe_visible(df)
    return df.copy()


def resolver_columna(df, clave):
    for nombre in columnas_equivalentes(clave):
        if nombre in df.columns:
            return nombre
    return None


def opciones_columna(df, clave):
    columna = resolver_columna(df, clave)
    if columna is None:
        return []
    serie = df[columna].dropna().astype(str).map(str.strip)
    return sorted(valor for valor in serie.unique() if valor)


def aplicar_filtros_alertas(df):
    if df.empty:
        return df

    filtrado = df.copy()
    col_fecha = resolver_columna(filtrado, "fecha_turno")
    col_turno = resolver_columna(filtrado, "turno")
    col_equipo = resolver_columna(filtrado, "modelo_equipo")
    col_numero = resolver_columna(filtrado, "numero_equipo")

    with st.sidebar:
        st.header("Filtros alertas")

        if col_fecha and filtrado[col_fecha].notna().any():
            fechas = pd.to_datetime(filtrado[col_fecha], errors="coerce", dayfirst=True)
            fechas_validas = fechas.dropna()
            if not fechas_validas.empty:
                min_fecha = fechas_validas.min().date()
                max_fecha = fechas_validas.max().date()
                rango = st.date_input(
                    "Fecha",
                    value=(min_fecha, max_fecha),
                    min_value=min_fecha,
                    max_value=max_fecha,
                    key="alertas_fecha",
                )
            else:
                rango = None
        else:
            rango = None

        turno = st.multiselect("Turno", opciones_columna(filtrado, "turno"), format_func=app.texto_visible, key="alertas_turno")
        equipo = st.multiselect("Equipo", opciones_columna(filtrado, "modelo_equipo"), format_func=app.texto_visible, key="alertas_equipo")
        numero = st.multiselect("Número de equipo", opciones_columna(filtrado, "numero_equipo"), format_func=app.texto_visible, key="alertas_numero")

    if rango and len(rango) == 2 and col_fecha:
        fechas = pd.to_datetime(filtrado[col_fecha], errors="coerce", dayfirst=True).dt.date
        filtrado = filtrado[(fechas >= rango[0]) & (fechas <= rango[1])]
    if turno and col_turno:
        filtrado = filtrado[filtrado[col_turno].astype(str).isin(turno)]
    if equipo and col_equipo:
        filtrado = filtrado[filtrado[col_equipo].astype(str).isin(equipo)]
    if numero and col_numero:
        filtrado = filtrado[filtrado[col_numero].astype(str).isin(numero)]

    return filtrado


def formatear_detalle(detalle):
    if detalle.empty:
        return detalle

    resultado = detalle.copy()
    columnas_fecha = [col for col in resultado.columns if "Fecha" in col]
    for columna in columnas_fecha:
        resultado[columna] = pd.to_datetime(resultado[columna], errors="coerce", dayfirst=True).dt.strftime("%d-%m-%Y")
    return resultado


def main():
    st.title("Sistema de Reporte de Perforación")
    st.caption(
        f"Alertas operacionales | Aplicación oficial: {EXCEL_PATH.parent} | Versión actual: {app.version_sistema()}"
    )

    df_reportes = leer_reportes()
    df_filtrado = aplicar_filtros_alertas(df_reportes)

    st.subheader("Alertas operacionales")
    st.caption("Fuente: reportes_perforacion.xlsx vía data.leer_reportes() y services.alert_service.evaluar_alertas_operacionales()")

    resultado = evaluar_alertas_operacionales(df_filtrado)
    mensajes = resultado.get("mensajes", [])
    detalle = resultado.get("detalle", pd.DataFrame())
    sin_alertas = bool(resultado.get("sin_alertas", False))

    if mensajes:
        for nivel, mensaje in mensajes:
            if nivel == "error":
                st.error(app.texto_visible(mensaje))
            elif nivel == "warning":
                st.warning(app.texto_visible(mensaje))
            else:
                st.info(app.texto_visible(mensaje))

    if sin_alertas or detalle.empty:
        st.info("No se detectaron alertas operacionales para los filtros seleccionados.")
    else:
        detalle = formatear_detalle(detalle)
        st.dataframe(dataframe_visible(detalle), width="stretch", hide_index=True)
        if "Recomendación operacional" in detalle.columns:
            st.caption("La tabla incluye la recomendación operacional asociada cuando aplica.")


main()
