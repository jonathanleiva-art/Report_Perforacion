from pathlib import Path
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from ui.page_header import render_page_header
import db
from operators import etiqueta_operador
from services import smart_alerts_service
from ui.formatting import dataframe_visible, texto_visible
from utils import EXCEL_PATH


def filtros_alertas():
    with app.st.sidebar:
        app.st.header("Filtros alertas")
        rango = app.st.date_input("Fecha", value=None, key="smart_alertas_fecha")
        turno = app.st.multiselect(
            "Turno",
            db.obtener_valores_distintos_columna("Turno"),
            format_func=texto_visible,
            key="smart_alertas_turno",
        )
        equipo = app.st.multiselect(
            "Equipo",
            db.obtener_valores_distintos_columna("Modelo equipo"),
            format_func=texto_visible,
            key="smart_alertas_equipo",
        )
        operador = app.st.multiselect(
            "Operador",
            db.obtener_valores_distintos_columna("Operador"),
            format_func=lambda valor: texto_visible(etiqueta_operador(valor)),
            key="smart_alertas_operador",
        )
        criticidad = app.st.multiselect(
            "Criticidad",
            ["INFO", "PREVENTIVA", "CRÍTICA"],
            key="smart_alertas_criticidad",
        )
        estado = app.st.multiselect(
            "Estado",
            ["pendiente", "vista", "atendida"],
            default=["pendiente", "vista", "atendida"],
            key="smart_alertas_estado",
        )

    fecha_desde = fecha_hasta = None
    if isinstance(rango, tuple) and len(rango) == 2:
        fecha_desde, fecha_hasta = rango

    return {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "turno": turno,
        "equipo": equipo,
        "operador": operador,
        "criticidad": criticidad,
        "estado": estado,
    }


def _etiqueta_alerta(fila):
    partes = [
        f"#{int(fila['id'])}" if "id" in fila and pd.notna(fila["id"]) else "",
        str(fila.get("fecha_turno", "")),
        texto_visible(fila.get("equipo", "")),
        texto_visible(fila.get("operador", "")),
        texto_visible(fila.get("causa", "")),
        texto_visible(fila.get("criticidad", "")),
        texto_visible(fila.get("estado", "")),
    ]
    return " | ".join(parte for parte in partes if str(parte).strip())


def _resumen_superior(resumen):
    col1, col2, col3, col4 = app.st.columns(4)
    col1.metric("Alertas totales", resumen["total"])
    col2.metric("Pendientes", resumen["pendientes"])
    col3.metric("Vistas", resumen["vistas"])
    col4.metric("Atendidas", resumen["atendidas"])


def _boton_actualizar():
    if app.st.button("Actualizar motor", type="primary"):
        resultado = smart_alerts_service.ejecutar_motor_alertas()
        app.st.session_state["alertas_smart_ultima_ejecucion"] = resultado
        app.st.success(
            f"Motor ejecutado. Nuevas alertas: {resultado['nuevas_alertas']}, registros procesados: {resultado['registros_procesados']}."
        )
        app.st.rerun()


def _acciones_estado(alertas_df):
    if alertas_df.empty:
        return

    opciones = {
        _etiqueta_alerta(fila): fila["alert_key"]
        for _, fila in alertas_df.iterrows()
        if "alert_key" in fila
    }
    if not opciones:
        return

    seleccionadas = app.st.multiselect(
        "Seleccionar alertas",
        list(opciones.keys()),
        key="smart_alertas_seleccion",
    )
    claves = [opciones[label] for label in seleccionadas]
    col1, col2 = app.st.columns(2)
    with col1:
        if app.st.button("Marcar como vista", disabled=not claves, key="smart_alertas_vista"):
            afectadas = smart_alerts_service.marcar_alertas_estado(claves, "vista")
            app.st.success(f"Alertas actualizadas: {afectadas}")
            app.st.rerun()
    with col2:
        if app.st.button("Marcar como atendida", disabled=not claves, key="smart_alertas_atendida"):
            afectadas = smart_alerts_service.marcar_alertas_estado(claves, "atendida")
            app.st.success(f"Alertas actualizadas: {afectadas}")
            app.st.rerun()


def _tabla_alertas(alertas_df):
    columnas = [
        col
        for col in [
            "id",
            "fecha_turno",
            "turno",
            "equipo",
            "numero_equipo",
            "operador",
            "causa",
            "recomendacion",
            "criticidad",
            "estado",
        ]
        if col in alertas_df.columns
    ]
    if alertas_df.empty:
        app.st.info("No hay alertas para los filtros seleccionados.")
        return
    app.st.dataframe(dataframe_visible(alertas_df[columnas]), width="stretch", hide_index=True)


def main():
    if not app.requerir_acceso():
        return
    render_page_header(app.st, "Alertas Inteligentes")
    app.st.caption(
        f"Motor incremental sobre SQLite | Base: {db.DB_PATH.name} | Excel respaldo: {EXCEL_PATH.name}"
    )

    smart_alerts_service.ejecutar_motor_alertas()
    filtros = filtros_alertas()
    alertas_df = smart_alerts_service.obtener_alertas_inteligentes(**filtros)
    resumen = smart_alerts_service.resumen_alertas_inteligentes()

    _resumen_superior(resumen)
    _boton_actualizar()

    app.st.subheader("Alertas registradas")
    if alertas_df.empty:
        app.st.info("No hay alertas inteligentes para mostrar.")
        return

    _acciones_estado(alertas_df)
    _tabla_alertas(alertas_df)

    app.st.subheader("Detalle operativo")
    detalle = alertas_df[[
        col for col in [
            "fecha_turno",
            "equipo",
            "operador",
            "causa",
            "recomendacion",
            "criticidad",
            "estado",
            "regla",
            "valor_metrico",
            "valor_referencia",
        ] if col in alertas_df.columns
    ]].copy()
    app.st.dataframe(dataframe_visible(detalle), width="stretch", hide_index=True)


main()

