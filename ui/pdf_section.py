import pandas as pd
import streamlit as st

from audit import audit_log
from data import reparar_texto
from pdf_report import generar_pdf as generar_pdf_report
from ui.formatting import dataframe_visible, texto_visible
from utils import EXCEL_PATH


TURNO_LABELS = {
    "1": "Día",
    "2": "Noche",
    "DIA": "Día",
    "DÍA": "Día",
    "NOCHE": "Noche",
}

TURNOS_PDF_OPCIONES = ["Día", "Noche", "Día y Noche"]
MENSAJE_SIN_DATOS_PDF = "No existen registros para el rango de fechas y turnos seleccionados."


def _normalizar_turno_pdf(turno):
    texto = reparar_texto(turno).strip()
    upper = texto.upper()
    if upper in {"1", "DIA", "DÍA"}:
        return "1"
    if upper in {"2", "NOCHE"}:
        return "2"
    return texto


def _etiqueta_turno_pdf(valor_normalizado):
    return TURNO_LABELS.get(str(valor_normalizado).upper(), texto_visible(valor_normalizado))


def _normalizar_rango_pdf(rango, fechas_disponibles):
    if isinstance(rango, (tuple, list)):
        valores = [valor for valor in rango if valor is not None]
        if len(valores) >= 2:
            return valores[0], valores[-1]
        if len(valores) == 1:
            return valores[0], valores[0]
    if rango is None:
        fecha = fechas_disponibles[-1]
        return fecha, fecha
    return rango, rango


def _turnos_incluidos_pdf(seleccion):
    seleccion = seleccion or ["Día y Noche"]
    if "Día y Noche" in seleccion:
        return ["1", "2"], "Dia_Noche", "Día y Noche"
    turnos = []
    if "Día" in seleccion:
        turnos.append("1")
    if "Noche" in seleccion:
        turnos.append("2")
    if not turnos:
        turnos = ["1", "2"]
    etiqueta = " y ".join(_etiqueta_turno_pdf(turno) for turno in turnos)
    archivo = "_".join("Dia" if turno == "1" else "Noche" for turno in turnos)
    return turnos, archivo, etiqueta


def _filtrar_pdf_por_rango_turno(df_fuente, fecha_inicio, fecha_fin, turnos):
    fechas_df = pd.to_datetime(df_fuente["Fecha turno"], errors="coerce").dt.date
    turnos_df = df_fuente["Turno"].astype(str).map(_normalizar_turno_pdf)
    return df_fuente[
        (fechas_df >= fecha_inicio)
        & (fechas_df <= fecha_fin)
        & (turnos_df.isin(turnos))
    ].copy()


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

    fechas_disponibles = sorted(fechas.unique())
    col_fecha, col_turno, col_boton = st.columns([1, 1, 1])
    with col_fecha:
        rango_pdf = st.date_input(
            "Rango de fechas PDF",
            value=(fechas_disponibles[-1], fechas_disponibles[-1]),
            min_value=fechas_disponibles[0],
            max_value=fechas_disponibles[-1],
            format="DD/MM/YYYY",
            key="rango_fechas_pdf",
        )
    fecha_inicio_pdf, fecha_fin_pdf = _normalizar_rango_pdf(rango_pdf, fechas_disponibles)
    with col_turno:
        seleccion_turnos_pdf = st.multiselect(
            "Turnos PDF",
            TURNOS_PDF_OPCIONES,
            default=["Día y Noche"],
            key="turnos_pdf",
        )
    turnos_pdf, turno_archivo_pdf, turnos_pdf_visible = _turnos_incluidos_pdf(seleccion_turnos_pdf)

    df_pdf = _filtrar_pdf_por_rango_turno(df_fuente, fecha_inicio_pdf, fecha_fin_pdf, turnos_pdf)

    ultimo_registro = df_fuente.tail(1).copy()
    st.caption(f"SQLite oficial para PDF: {EXCEL_PATH.parent}")
    c_info_1, c_info_2, c_info_3 = st.columns(3)
    c_info_1.metric("Registros PDF", len(df_pdf))
    c_info_2.metric("Rango seleccionado", f"{fecha_inicio_pdf.strftime('%d-%m-%Y')} a {fecha_fin_pdf.strftime('%d-%m-%Y')}")
    c_info_3.metric("Turnos seleccionados", turnos_pdf_visible)

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
        df_pdf = _filtrar_pdf_por_rango_turno(df_fuente, fecha_inicio_pdf, fecha_fin_pdf, turnos_pdf)

        if df_pdf.empty:
            audit_log.registrar_generacion_pdf(
                turno=turnos_pdf_visible,
                resultado="rechazado",
                detalle=MENSAJE_SIN_DATOS_PDF,
            )
            st.warning(MENSAJE_SIN_DATOS_PDF)
            return

        try:
            ruta_pdf = generar_pdf_report(
                df_pdf,
                (fecha_inicio_pdf, fecha_fin_pdf),
                turnos_pdf_visible,
                df_fuente,
                fuente_datos=st.session_state.get("dashboard_data_source_label", "Fuente activa"),
                turno_archivo=turno_archivo_pdf,
            )
        except Exception as exc:
            audit_log.registrar_generacion_pdf(
                turno=turnos_pdf_visible,
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
