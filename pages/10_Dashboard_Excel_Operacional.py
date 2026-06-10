from pathlib import Path
import sys

import pandas as pd
import plotly.express as px


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from services import operational_excel_query_service as query_service
from ui.formatting import dataframe_visible, texto_visible
from ui.page_header import render_page_header


def _formato_fecha(valor):
    if not valor:
        return "Sin fecha"
    fecha = pd.to_datetime(valor, errors="coerce")
    if pd.notna(fecha):
        return fecha.strftime("%d/%m/%Y")
    return str(valor)


def _mostrar_kpis(resumen):
    fila_1 = app.st.columns(4)
    fila_1[0].metric("Metros totales", f"{resumen['metros_totales']:,.2f}")
    fila_1[1].metric("Registros", f"{resumen['registros']:,.0f}")
    fila_1[2].metric("Fecha minima", _formato_fecha(resumen["fecha_min"]))
    fila_1[3].metric("Fecha maxima", _formato_fecha(resumen["fecha_max"]))

    fila_2 = app.st.columns(4)
    fila_2[0].metric("Equipos", f"{resumen['equipos']:,.0f}")
    fila_2[1].metric("Operadores", f"{resumen['operadores']:,.0f}")
    fila_2[2].metric("Horas efectivas", f"{resumen['horas_efectivas']:,.2f}")
    fila_2[3].metric("Horas averia", f"{resumen['horas_averia']:,.2f}")

    fila_3 = app.st.columns(4)
    fila_3[0].metric("Horas MP", f"{resumen['horas_mp']:,.2f}")
    fila_3[1].metric("Disponibilidad promedio", f"{resumen['disponibilidad_promedio']:,.2f}%")
    fila_3[2].metric("Utilizacion promedio", f"{resumen['utilizacion_promedio']:,.2f}%")
    fila_3[3].metric("Rendimiento promedio m/h", f"{resumen['rendimiento_promedio_mh']:,.2f}")


def _mostrar_figura(fig, mensaje):
    if fig is None:
        app.st.info(mensaje)
    else:
        app.st.plotly_chart(fig, width="stretch")


def _fig_metros_por_equipo(ranking):
    if ranking.empty:
        return None
    data = ranking.head(20).sort_values("metros_totales", ascending=True)
    fig = px.bar(
        data,
        x="metros_totales",
        y="equipo",
        orientation="h",
        title="Metros por equipo",
        text="metros_totales",
        color_discrete_sequence=["#2563EB"],
    )
    fig.update_layout(xaxis_title="Metros", yaxis_title="Equipo")
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    return fig


def _fig_metros_por_operador(ranking):
    if ranking.empty:
        return None
    data = ranking.head(20).sort_values("metros_totales", ascending=True)
    fig = px.bar(
        data,
        x="metros_totales",
        y="operador",
        orientation="h",
        title="Metros por operador",
        text="metros_totales",
        color_discrete_sequence=["#0F766E"],
    )
    fig.update_layout(xaxis_title="Metros", yaxis_title="Operador")
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    return fig


def _fig_metros_por_fecha(df):
    if df.empty or "fecha_turno" not in df.columns:
        return None
    data = df.copy()
    data["fecha_turno"] = pd.to_datetime(data["fecha_turno"], errors="coerce")
    data = data.dropna(subset=["fecha_turno"])
    if data.empty:
        return None
    resumen = data.groupby(data["fecha_turno"].dt.date, as_index=False)["metros"].sum()
    resumen = resumen.rename(columns={"fecha_turno": "fecha"})
    fig = px.line(
        resumen,
        x="fecha",
        y="metros",
        markers=True,
        title="Metros por fecha",
        color_discrete_sequence=["#7C3AED"],
    )
    fig.update_layout(xaxis_title="Fecha", yaxis_title="Metros")
    return fig


def _fig_horas_por_tipo(df):
    if df.empty:
        return None
    columnas = {
        "Horas efectivas": "horas_efectivas",
        "Horas averia": "horas_averia",
        "Horas MP": "horas_mp",
    }
    disponibles = {nombre: columna for nombre, columna in columnas.items() if columna in df.columns}
    if not disponibles:
        return None
    data = pd.DataFrame({
        "Tipo": list(disponibles.keys()),
        "Horas": [
            float(pd.to_numeric(df[columna], errors="coerce").fillna(0).sum())
            for columna in disponibles.values()
        ],
    })
    data = data[data["Horas"] > 0]
    if data.empty:
        return None
    fig = px.bar(
        data,
        x="Tipo",
        y="Horas",
        title="Horas por tipo",
        text="Horas",
        color="Tipo",
    )
    fig.update_layout(xaxis_title="", yaxis_title="Horas", showlegend=False)
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    return fig


def _mostrar_info_fuente(fuente):
    columnas = [
        "id_fuente",
        "nombre_fuente",
        "tipo_fuente",
        "archivo_origen",
        "fecha_importacion",
        "total_registros",
        "fecha_min",
        "fecha_max",
        "estado",
    ]
    datos = {columna: fuente.get(columna) for columna in columnas if columna in fuente}
    app.st.dataframe(dataframe_visible(pd.DataFrame([datos])), width="stretch", hide_index=True)


def main():
    if not app.requerir_acceso():
        return
    render_page_header(
        app.st,
        "Dashboard Excel Operacional",
        "Vista separada para fuentes importadas tipo registro operacional Excel.",
    )

    fuentes = query_service.listar_fuentes_operacionales_importadas()
    if fuentes.empty:
        app.st.info("No hay fuentes operacionales Excel importadas disponibles.")
        return

    opciones = {
        f"{int(fila.id_fuente)} - {texto_visible(fila.nombre_fuente)}": int(fila.id_fuente)
        for fila in fuentes.itertuples()
    }
    seleccion = app.st.selectbox(
        "Fuente operacional Excel",
        options=list(opciones.keys()),
        key="dashboard_excel_operacional_fuente",
    )
    id_fuente = opciones[seleccion]
    fuente = fuentes[fuentes["id_fuente"].astype(int).eq(id_fuente)].iloc[0].to_dict()

    app.st.subheader("Informacion de la fuente")
    _mostrar_info_fuente(fuente)

    registros = query_service.cargar_registros_operacionales_por_fuente(id_fuente)
    if registros.empty:
        app.st.warning("Esta fuente esta importada, pero no contiene registros operacionales validos.")
        return

    resumen = query_service.calcular_resumen_operacional_excel(id_fuente)
    ranking_equipos = query_service.obtener_ranking_equipos_excel(id_fuente)
    ranking_operadores = query_service.obtener_ranking_operadores_excel(id_fuente)

    app.st.subheader("KPIs basicos")
    _mostrar_kpis(resumen)

    app.st.subheader("Graficos")
    col_1, col_2 = app.st.columns(2)
    with col_1:
        _mostrar_figura(_fig_metros_por_equipo(ranking_equipos), "Sin datos suficientes para metros por equipo.")
    with col_2:
        _mostrar_figura(_fig_metros_por_operador(ranking_operadores), "Sin datos suficientes para metros por operador.")

    col_3, col_4 = app.st.columns(2)
    with col_3:
        _mostrar_figura(_fig_metros_por_fecha(registros), "Sin datos suficientes para metros por fecha.")
    with col_4:
        _mostrar_figura(_fig_horas_por_tipo(registros), "Sin columnas suficientes para horas por tipo.")

    tabs = app.st.tabs(["Registros importados", "Ranking equipos", "Ranking operadores"])
    with tabs[0]:
        columnas = [
            "fecha_turno",
            "turno",
            "equipo",
            "operador",
            "metros",
            "horas_efectivas",
            "horas_averia",
            "horas_mp",
            "disponibilidad",
            "utilizacion",
            "rendimiento",
        ]
        visibles = [columna for columna in columnas if columna in registros.columns]
        app.st.dataframe(dataframe_visible(registros[visibles]), width="stretch", hide_index=True)
    with tabs[1]:
        app.st.dataframe(dataframe_visible(ranking_equipos), width="stretch", hide_index=True)
    with tabs[2]:
        app.st.dataframe(dataframe_visible(ranking_operadores), width="stretch", hide_index=True)


main()
