import pandas as pd
import streamlit as st

from audit import audit_log
from data import reparar_texto
from pdf_report import generar_pdf as generar_pdf_report
from ui.formatting import dataframe_visible, texto_visible
from utils import EXCEL_PATH


def seccion_reporte_pdf(df):
    st.subheader("Reporte PDF por fecha y turno")
    df_fuente = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()

    if "Fecha turno" not in df_fuente.columns or "Turno" not in df_fuente.columns:
        st.info("No hay columnas suficientes para generar PDF por fecha y turno.")
        return

    fechas = pd.to_datetime(df_fuente["Fecha turno"], errors="coerce").dt.date.dropna()
    if fechas.empty:
        st.info("No hay fechas válidas para generar PDF.")
        return

    fechas_disponibles = sorted(fechas.unique(), reverse=True)
    col_fecha, col_turno, col_boton = st.columns([1, 1, 1])
    with col_fecha:
        fecha_pdf = st.selectbox("Fecha turno PDF", fechas_disponibles, format_func=lambda fecha: fecha.strftime("%d-%m-%Y"))
    turnos_pdf = sorted(
        dict.fromkeys(
            reparar_texto(turno)
            for turno in df_fuente["Turno"].dropna().astype(str)
            if reparar_texto(turno)
        )
    )
    with col_turno:
        turno_pdf = st.selectbox("Turno PDF", turnos_pdf, format_func=texto_visible)

    fechas_df = pd.to_datetime(df_fuente["Fecha turno"], errors="coerce").dt.date
    turnos_df = df_fuente["Turno"].astype(str).map(reparar_texto).str.strip()
    df_pdf = df_fuente[(fechas_df == fecha_pdf) & (turnos_df == turno_pdf)].copy()

    ultimo_registro = df_fuente.tail(1).copy()
    st.caption(f"SQLite oficial para PDF: {EXCEL_PATH.parent}")
    c_info_1, c_info_2, c_info_3 = st.columns(3)
    c_info_1.metric("Registros PDF", len(df_pdf))
    c_info_2.metric("Fecha seleccionada", fecha_pdf.strftime("%d-%m-%Y"))
    c_info_3.metric("Turno seleccionado", texto_visible(turno_pdf))

    if not ultimo_registro.empty:
        columnas_ultimo = [
            columna
            for columna in ["Fecha turno", "Modelo equipo", "Número equipo", "Operador", "Turno", "Metros perforados", "Hora registro"]
            if columna in ultimo_registro.columns
        ]
        st.caption("Último registro cargado desde SQLite oficial")
        st.dataframe(dataframe_visible(ultimo_registro[columnas_ultimo]), width="stretch", hide_index=True)

    columnas_preview = [
        columna
        for columna in [
            "Fecha turno",
            "Modelo equipo",
            "Número equipo",
            "Operador",
            "Turno",
            "Metros perforados",
            "Horas efectivas perforando",
            "Disponibilidad %",
            "Utilización",
            "Rendimiento m/h",
        ]
        if columna in df_pdf.columns
    ]
    if not df_pdf.empty and columnas_preview:
        st.caption("Datos que se usarán para generar el PDF")
        st.dataframe(dataframe_visible(df_pdf[columnas_preview]), width="stretch", hide_index=True)

    with col_boton:
        st.write("")
        st.write("")
        generar = st.button("Generar reporte PDF", type="primary")

    if generar:
        fechas_actualizadas = pd.to_datetime(df_fuente["Fecha turno"], errors="coerce").dt.date
        turnos_actualizados = df_fuente["Turno"].astype(str).map(reparar_texto).str.strip()
        df_pdf = df_fuente[(fechas_actualizadas == fecha_pdf) & (turnos_actualizados == turno_pdf)].copy()

        if df_pdf.empty:
            audit_log.registrar_generacion_pdf(
                turno=turno_pdf,
                resultado="rechazado",
                detalle="No hay registros para la fecha y turno seleccionados.",
            )
            st.warning("No hay registros para la fecha y turno seleccionados.")
            return

        try:
            ruta_pdf = generar_pdf_report(df_pdf, fecha_pdf, turno_pdf, df_fuente)
        except Exception as exc:
            audit_log.registrar_generacion_pdf(
                turno=turno_pdf,
                resultado="error",
                detalle=str(exc),
            )
            st.error(f"No se pudo generar el PDF: {exc}")
            return

        st.success(f"PDF generado correctamente: {ruta_pdf.name}")
        with open(ruta_pdf, "rb") as archivo_pdf:
            st.download_button(
                "Descargar reporte PDF",
                data=archivo_pdf,
                file_name=ruta_pdf.name,
                mime="application/pdf",
            )
