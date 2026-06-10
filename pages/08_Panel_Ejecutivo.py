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
from services import executive_service
from ui.formatting import dataframe_visible, texto_visible
from utils import EXCEL_PATH


COLOR_SEMAFORO = {
    "verde": "#16A34A",
    "amarillo": "#D97706",
    "rojo": "#DC2626",
}


def filtros_ejecutivos():
    with app.st.sidebar:
        app.st.header("Filtros ejecutivos")
        rango = app.st.date_input("Fecha", value=None, key="ejecutivo_fecha")
        turno = app.st.multiselect(
            "Turno",
            db.obtener_valores_distintos_columna("Turno"),
            format_func=texto_visible,
            key="ejecutivo_turno",
        )
        equipo = app.st.multiselect(
            "Equipo",
            db.obtener_valores_distintos_columna("Modelo equipo"),
            format_func=texto_visible,
            key="ejecutivo_equipo",
        )
        operador = app.st.multiselect(
            "Operador",
            db.obtener_valores_distintos_columna("Operador"),
            format_func=lambda valor: texto_visible(etiqueta_operador(valor)),
            key="ejecutivo_operador",
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
    }


def mostrar_kpis(kpis):
    filas = [
        [
            ("Metros perforados", f"{kpis['metros_perforados_totales']:,.2f}"),
            ("Horas efectivas", f"{kpis['horas_efectivas']:,.2f} h"),
            ("Horas no efectivas", f"{kpis['horas_no_efectivas']:,.2f} h"),
            ("Disponibilidad", f"{kpis['disponibilidad_promedio']:,.2f}%"),
        ],
        [
            ("Utilización", f"{kpis['utilizacion_promedio']:,.2f}%"),
            ("Rendimiento", f"{kpis['rendimiento_promedio']:,.2f} m/h"),
            ("Equipos activos", f"{kpis['equipos_activos']:,}"),
            ("Operadores", f"{kpis['operadores_registrados']:,}"),
        ],
    ]
    for fila in filas:
        columnas = app.st.columns(4)
        for columna, (titulo, valor) in zip(columnas, fila):
            columna.metric(titulo, valor)


def mostrar_semaforo(salud):
    semaforo = salud["semaforo"]
    color = COLOR_SEMAFORO.get(semaforo["estado"], "#64748B")
    app.st.markdown(
        f"""
        <div style="border-left: 8px solid {color}; padding: 14px 18px; background: #F8FAFC; border-radius: 6px;">
            <div style="font-size: 0.85rem; color: #475569;">Índice de salud operacional</div>
            <div style="font-size: 2.2rem; font-weight: 700; color: {color};">{salud['indice']:.2f} / 100</div>
            <div style="font-size: 1.05rem; font-weight: 600;">{texto_visible(semaforo['titulo'])}</div>
            <div style="color: #475569;">{texto_visible(semaforo['mensaje'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    detalle = pd.DataFrame([salud["detalle"]]).rename(columns={
        "utilizacion": "Utilización",
        "disponibilidad": "Disponibilidad",
        "rendimiento": "Rendimiento",
        "horas_no_efectivas": "Horas no efectivas",
        "alertas": "Alertas",
    })
    app.st.dataframe(dataframe_visible(detalle), width="stretch", hide_index=True)


def mostrar_rankings(rankings):
    app.st.subheader("Rankings operacionales")
    col1, col2 = app.st.columns(2)
    with col1:
        app.st.caption("Equipos con mejor rendimiento")
        mostrar_tabla_o_vacio(rankings["mejor_rendimiento_equipos"])
    with col2:
        app.st.caption("Equipos con menor utilización")
        mostrar_tabla_o_vacio(rankings["menor_utilizacion_equipos"])

    col3, col4 = app.st.columns(2)
    with col3:
        app.st.caption("Operadores con mayor metraje")
        mostrar_tabla_o_vacio(rankings["mayor_metraje_operadores"])
    with col4:
        app.st.caption("Principales detenciones/observaciones")
        mostrar_tabla_o_vacio(rankings["principales_causas_detencion"])


def mostrar_tabla_o_vacio(df):
    if df is None or df.empty:
        app.st.info("Sin datos suficientes.")
    else:
        app.st.dataframe(dataframe_visible(df), width="stretch", hide_index=True)


def mostrar_tendencia(tendencia):
    app.st.subheader("Tendencia semanal")
    if tendencia is None or tendencia.empty:
        app.st.info("Se requieren al menos 7 fechas con registros para mostrar tendencia.")
        return

    app.st.line_chart(
        tendencia.set_index("Periodo")[["Metros perforados", "Utilización promedio %", "Disponibilidad promedio %", "Rendimiento m/h"]]
    )
    app.st.dataframe(dataframe_visible(tendencia), width="stretch", hide_index=True)


def mostrar_alertas(resultado):
    alertas = resultado.get("alertas", {})
    mensajes = alertas.get("mensajes", [])
    detalle = alertas.get("detalle", pd.DataFrame())
    app.st.subheader("Alertas ejecutivas")
    if not mensajes and (detalle is None or detalle.empty):
        app.st.info("No se detectan alertas operacionales para los filtros seleccionados.")
        return
    for nivel, mensaje in mensajes:
        if nivel == "error":
            app.st.error(texto_visible(mensaje))
        elif nivel == "warning":
            app.st.warning(texto_visible(mensaje))
        else:
            app.st.info(texto_visible(mensaje))
    if detalle is not None and not detalle.empty:
        app.st.dataframe(dataframe_visible(detalle), width="stretch", hide_index=True)


def main():
    if not app.requerir_acceso():
        return
    render_page_header(app.st, "Panel Ejecutivo")
    app.st.caption(
        f"Vista rápida para jefatura | Fuente SQLite: {db.DB_PATH.name} | Excel respaldo: {EXCEL_PATH.name}"
    )

    filtros = filtros_ejecutivos()
    resultado = executive_service.consultar_panel_ejecutivo(**filtros)
    if resultado["total_registros"] == 0:
        app.st.info("No hay registros operacionales para los filtros seleccionados.")
        return

    mostrar_kpis(resultado["kpis"])
    mostrar_semaforo(resultado["salud"])
    mostrar_rankings(resultado["rankings"])
    mostrar_tendencia(resultado["tendencia"])
    mostrar_alertas(resultado)


main()

