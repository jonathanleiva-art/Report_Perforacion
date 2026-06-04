from datetime import date
from pathlib import Path
import sys

import plotly.express as px


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from ui.page_header import render_page_header
from ui.data_source import FUENTE_MANUAL, seleccionar_fuente_datos
from services.ciclos_service import (
    obtener_ranking_equipos_mensual_ciclos,
    obtener_ranking_operadores_mensual_ciclos,
    obtener_resumen_mensual_ciclos,
)
from services.monthly_service import (
    obtener_ranking_equipos_mensual,
    obtener_ranking_operadores_mensual,
    obtener_resumen_mensual,
)


MESES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

COLOR_BARRA = "#2563EB"
COLOR_UTILIZACION = "#0F766E"
COLOR_RENDIMIENTO = "#D97706"


def _formato_numero(valor, decimales=2):
    return f"{float(valor or 0):,.{decimales}f}"


def _mostrar_kpis(resumen):
    filas = [
        [
            ("Metros perforados acumulados", f"{_formato_numero(resumen['metros_totales'])} m"),
            ("Cantidad de registros", f"{int(resumen['cantidad_registros']):,}"),
            ("Horas efectivas", f"{_formato_numero(resumen['horas_efectivas_totales'])} h"),
            ("Horas no efectivas", f"{_formato_numero(resumen['horas_no_efectivas_totales'])} h"),
            ("Horas de averias", f"{_formato_numero(resumen['horas_averias_totales'])} h"),
        ],
        [
            ("Disponibilidad promedio", f"{_formato_numero(resumen['disponibilidad_promedio'])}%"),
            ("Utilización promedio", f"{_formato_numero(resumen['utilizacion_promedio'])}%"),
            ("Rendimiento promedio", f"{_formato_numero(resumen['rendimiento_promedio'])} m/h"),
            ("Equipos distintos", f"{int(resumen['equipos_distintos']):,}"),
            ("Operadores distintos", f"{int(resumen['operadores_distintos']):,}"),
        ],
    ]
    for fila in filas:
        columnas = app.st.columns(5)
        for columna, (titulo, valor) in zip(columnas, fila):
            columna.metric(titulo, valor)


def _diagnostico(resumen):
    if int(resumen["cantidad_registros"]) == 0:
        return "No existen registros operacionales para el mes seleccionado."

    utilizacion = float(resumen["utilizacion_promedio"] or 0)
    if utilizacion >= 75:
        return "Utilización mensual dentro de rango favorable."
    if utilizacion >= 60:
        return "Utilización mensual en rango medio, requiere seguimiento."
    return "Utilización mensual baja, se recomienda revisar tiempos no efectivos y detenciones."


def _tabla_ranking(df, columna_nombre):
    if df.empty:
        return df
    columnas = {
        columna_nombre: "Equipo" if columna_nombre == "numero_equipo" else "Operador",
        "metros_totales": "Metros",
        "utilizacion_promedio": "Utilización",
        "disponibilidad_promedio": "Disponibilidad %",
        "rendimiento_promedio": "Rendimiento m/h",
        "cantidad_registros": "Registros",
    }
    return df[list(columnas.keys())].rename(columns=columnas)


def _mostrar_rankings(ranking_equipos, ranking_operadores):
    app.st.subheader("Ranking mensual por equipo")
    if ranking_equipos.empty:
        app.st.info("No existen datos suficientes para generar rankings mensuales.")
    else:
        lider = ranking_equipos.iloc[0]
        app.st.success(
            f"El equipo con mayor metraje acumulado es {lider['numero_equipo']} "
            f"con {_formato_numero(lider['metros_totales'])} metros."
        )
        app.st.dataframe(_tabla_ranking(ranking_equipos, "numero_equipo"), width="stretch", hide_index=True)

    app.st.subheader("Ranking mensual por operador")
    if ranking_operadores.empty:
        app.st.info("No existen datos suficientes para generar rankings mensuales.")
    else:
        lider = ranking_operadores.iloc[0]
        app.st.success(
            f"El operador con mayor metraje acumulado es {lider['operador']} "
            f"con {_formato_numero(lider['metros_totales'])} metros."
        )
        app.st.dataframe(_tabla_ranking(ranking_operadores, "operador"), width="stretch", hide_index=True)


def _fig_barra_horizontal(df, *, x, y, titulo, etiqueta_x, color):
    data = df.copy()
    data[x] = data[x].astype(float).round(2)
    data = data.sort_values(x, ascending=True)
    fig = px.bar(
        data,
        x=x,
        y=y,
        orientation="h",
        title=titulo,
        text=x,
        color_discrete_sequence=[color],
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside", cliponaxis=False)
    fig.update_layout(
        height=max(420, min(680, 90 + len(data) * 42)),
        margin=dict(l=120, r=80, t=70, b=70),
        xaxis_title=etiqueta_x,
        yaxis_title="",
        showlegend=False,
        uniformtext_minsize=10,
        uniformtext_mode="hide",
    )
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    return fig


def _mostrar_graficos(ranking_equipos, ranking_operadores):
    app.st.subheader("Gráficos mensuales")

    if ranking_equipos.empty and ranking_operadores.empty:
        app.st.info("No existen datos suficientes para generar graficos mensuales.")
        return

    col1, col2 = app.st.columns(2)
    with col1:
        app.st.caption("Metros perforados por equipo")
        if ranking_equipos.empty:
            app.st.info("Sin datos por equipo para el mes seleccionado.")
        else:
            fig = _fig_barra_horizontal(
                ranking_equipos,
                x="metros_totales",
                y="numero_equipo",
                titulo="Metros perforados por equipo",
                etiqueta_x="Metros",
                color=COLOR_BARRA,
            )
            app.st.plotly_chart(fig, use_container_width=True)

    with col2:
        app.st.caption("Metros perforados por operador")
        if ranking_operadores.empty:
            app.st.info("Sin datos por operador para el mes seleccionado.")
        else:
            fig = _fig_barra_horizontal(
                ranking_operadores,
                x="metros_totales",
                y="operador",
                titulo="Metros perforados por operador",
                etiqueta_x="Metros",
                color=COLOR_BARRA,
            )
            app.st.plotly_chart(fig, use_container_width=True)

    col3, col4 = app.st.columns(2)
    with col3:
        app.st.caption("Utilización promedio por equipo")
        if ranking_equipos.empty:
            app.st.info("Sin datos de utilizacion por equipo.")
        else:
            fig = _fig_barra_horizontal(
                ranking_equipos,
                x="utilizacion_promedio",
                y="numero_equipo",
                titulo="Utilización promedio por equipo",
                etiqueta_x="Utilización",
                color=COLOR_UTILIZACION,
            )
            app.st.plotly_chart(fig, use_container_width=True)

    with col4:
        app.st.caption("Rendimiento promedio por equipo")
        if ranking_equipos.empty:
            app.st.info("Sin datos de rendimiento por equipo.")
        else:
            fig = _fig_barra_horizontal(
                ranking_equipos,
                x="rendimiento_promedio",
                y="numero_equipo",
                titulo="Rendimiento promedio por equipo",
                etiqueta_x="Rendimiento m/h",
                color=COLOR_RENDIMIENTO,
            )
            app.st.plotly_chart(fig, use_container_width=True)


def main():
    if not app.requerir_acceso():
        return
    render_page_header(app.st, "Análisis Mensual")
    app.st.caption("Resumen operacional mensual consolidado desde SQLite.")

    hoy = date.today()
    fuente = seleccionar_fuente_datos(app.st, key="analisis_mensual_fuente")
    with app.st.sidebar:
        app.st.header("Periodo")
        anio = app.st.number_input(
            "Año",
            min_value=2000,
            max_value=2100,
            value=hoy.year,
            step=1,
            key="analisis_mensual_anio",
        )
        mes = app.st.selectbox(
            "Mes",
            list(MESES.keys()),
            index=hoy.month - 1,
            format_func=lambda valor: MESES[valor],
            key="analisis_mensual_mes",
        )

    if fuente != FUENTE_MANUAL:
        id_fuente = app.st.session_state.get("dashboard_data_source_id")
        solo_activas = id_fuente is None
        resumen = obtener_resumen_mensual_ciclos(int(anio), int(mes), id_fuente=id_fuente, solo_activas=solo_activas)
        ranking_equipos = obtener_ranking_equipos_mensual_ciclos(int(anio), int(mes), id_fuente=id_fuente, solo_activas=solo_activas)
        ranking_operadores = obtener_ranking_operadores_mensual_ciclos(int(anio), int(mes), id_fuente=id_fuente, solo_activas=solo_activas)
    else:
        resumen = obtener_resumen_mensual(int(anio), int(mes))
        ranking_equipos = obtener_ranking_equipos_mensual(int(anio), int(mes))
        ranking_operadores = obtener_ranking_operadores_mensual(int(anio), int(mes))

    app.st.subheader(f"Periodo: {MESES[int(mes)]} {int(anio)}")
    app.st.caption(f"Fuente de datos activa: {fuente}")
    app.st.caption(f"Rango consultado: {resumen['fecha_inicio']} a {resumen['fecha_fin']}")
    _mostrar_kpis(resumen)

    app.st.subheader("Diagnóstico automatico")
    mensaje = _diagnostico(resumen)
    if int(resumen["cantidad_registros"]) == 0:
        app.st.info(mensaje)
    elif float(resumen["utilizacion_promedio"] or 0) >= 75:
        app.st.success(mensaje)
    elif float(resumen["utilizacion_promedio"] or 0) >= 60:
        app.st.warning(mensaje)
    else:
        app.st.error(mensaje)

    _mostrar_rankings(ranking_equipos, ranking_operadores)
    _mostrar_graficos(ranking_equipos, ranking_operadores)


if __name__ == "__main__":
    main()

