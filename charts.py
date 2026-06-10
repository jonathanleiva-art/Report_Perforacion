import pandas as pd
import plotly.express as px

from metrics import calcular_disponibilidad, calcular_kpis_consolidados_dataframe, calcular_rendimiento_consolidado, calcular_utilizacion
from services import catalog_service
from services import executive_service
from services import kpi_service
from utils import EQUIPOS, HORAS_TURNO, limpiar_entero

COLOR_SEQUENCE = ["#5B9BD5", "#E67E22", "#4CAF50", "#E0A052", "#7C8EA6", "#D65A5A"]
CHART_BG = "#10151B"
CHART_PLOT_BG = "#0C1117"
CHART_TEXT = "#E8EEF6"
CHART_MUTED = "#9AA8BA"
CHART_GRID = "rgba(148, 163, 184, 0.16)"
CHART_AXIS = "rgba(226, 232, 240, 0.42)"


EQUIPO_COLORS = {
    "Sandvik D75KS": "#1F77B4",
    "SmartROC D65": "#0F766E",
    "FlexiROC D65": "#F59E0B",
}


def aplicar_layout_operacional(fig, height=520, tickangle=0):
    fig.update_layout(
        height=height,
        margin=dict(l=120, r=115, t=80, b=120),
        title=dict(x=0.02, xanchor="left"),
        template="plotly_dark",
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_PLOT_BG,
        font=dict(color=CHART_TEXT, family="Barlow, Arial, sans-serif"),
        title_font=dict(color=CHART_TEXT, size=18),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(148, 163, 184, 0.20)",
            borderwidth=1,
            font=dict(color=CHART_TEXT),
        ),
        uniformtext_minsize=10,
        uniformtext_mode="hide",
    )
    fig.update_xaxes(
        automargin=True,
        tickangle=tickangle,
        color=CHART_TEXT,
        gridcolor=CHART_GRID,
        linecolor=CHART_AXIS,
        zerolinecolor=CHART_GRID,
        title_font=dict(color=CHART_MUTED),
        tickfont=dict(color=CHART_TEXT),
    )
    fig.update_yaxes(
        automargin=True,
        color=CHART_TEXT,
        gridcolor=CHART_GRID,
        linecolor=CHART_AXIS,
        zerolinecolor=CHART_GRID,
        title_font=dict(color=CHART_MUTED),
        tickfont=dict(color=CHART_TEXT),
    )
    fig.update_traces(textfont=dict(color=CHART_TEXT), cliponaxis=False)
    return fig


def orden_equipos():
    return {
        (modelo, limpiar_entero(numero)): indice
        for indice, (modelo, numero) in enumerate(
            (item for modelo, numeros in EQUIPOS.items() for item in [(modelo, numero) for numero in numeros])
        )
    }


def columna_disponible(df, *nombres):
    for nombre in nombres:
        if nombre in df.columns:
            return nombre
    return None


def columna_operador_visual(df):
    if "operador_nombre" in df.columns:
        valores = df["operador_nombre"].fillna("").astype(str).str.strip()
        if valores.ne("").any():
            return "operador_nombre"
    return "Operador"


def resumen_kpi_equipos(df):
    columnas = [
        "Modelo equipo",
        "Número equipo",
        "Equipo",
        "Metros perforados",
        "Pozos perforados",
        "Disponibilidad %",
        "Utilización",
        "Rendimiento consolidado m/h",
        "Horas efectivas perforando",
        "Horas avería equipo",
    ]
    if df.empty or not {"Modelo equipo", "Número equipo"}.issubset(df.columns):
        return pd.DataFrame(columns=columnas)

    base = df.copy()
    base["Número equipo"] = base["Número equipo"].astype(str).apply(limpiar_entero)
    pozos_col = columna_disponible(base, "Pozos perforados turno", "Cantidad pozos perforados")
    averia_col = columna_disponible(base, "Horas detención mecánica", "Avería")

    filas = []
    orden = orden_equipos()
    for (modelo, numero), grupo in base.groupby(["Modelo equipo", "Número equipo"], dropna=False):
        numero_limpio = limpiar_entero(numero)
        kpis = kpi_service.calcular_kpis_operacionales_grupo(grupo)
        metros = kpis["metros"]
        horas = kpis["horas_efectivas_productivas"]
        rendimiento = kpis["rendimiento"]
        pozos = pd.to_numeric(grupo.get(pozos_col, 0), errors="coerce").fillna(0).sum() if pozos_col else 0
        horas_averia = pd.to_numeric(grupo.get(averia_col, 0), errors="coerce").fillna(0).sum() if averia_col else 0
        disponibilidad = kpis["disponibilidad"]
        utilizacion = kpis["utilizacion_productiva"]
        filas.append({
            "Modelo equipo": modelo,
            "Número equipo": numero_limpio,
            "Equipo": f"{modelo} {numero_limpio}",
            "Metros perforados": round(metros, 2),
            "Pozos perforados": round(pozos, 0),
            "Disponibilidad %": round(disponibilidad, 2),
            "Utilización": round(utilizacion, 2),
            "Rendimiento consolidado m/h": round(rendimiento, 2),
            "Horas efectivas perforando": round(horas, 2),
            "Horas avería equipo": round(horas_averia, 2),
            "_orden": orden.get((str(modelo), numero_limpio), 999),
        })

    if not filas:
        return pd.DataFrame(columns=columnas)

    data = pd.DataFrame(filas).sort_values(["_orden", "Equipo"]).drop(columns=["_orden"])
    return data[columnas]


def fig_kpi_equipo(df, columna, titulo, sufijo="", color="#1F77B4"):
    data = resumen_kpi_equipos(df)
    if data.empty or columna not in data.columns:
        return None

    data = data[pd.to_numeric(data[columna], errors="coerce").fillna(0) > 0].copy()
    if data.empty:
        return None

    data[columna] = pd.to_numeric(data[columna], errors="coerce").fillna(0).round(2)
    data = data.sort_values(columna, ascending=True)
    fig = px.bar(
        data,
        x=columna,
        y="Equipo",
        orientation="h",
        title=titulo,
        text=columna,
        color="Modelo equipo",
        color_discrete_map=EQUIPO_COLORS,
        hover_data={
            "Modelo equipo": True,
            "Número equipo": True,
            columna: ":.2f",
        },
    )
    text_template = "%{text:.0f}" if columna == "Pozos perforados" else "%{text:.2f}" + sufijo
    fig.update_traces(texttemplate=text_template, textposition="outside", cliponaxis=False)
    fig.update_layout(
        xaxis_title=titulo,
        yaxis_title="Equipo",
        showlegend=True,
        legend_title_text="Modelo",
    )
    aplicar_layout_operacional(fig, height=max(420, 120 + 58 * len(data)))
    return fig


def fig_ranking_operadores(df_productivo):
    operador_col = columna_operador_visual(df_productivo)
    data = calcular_rendimiento_consolidado(df_productivo, [operador_col]).sort_values(
        "Rendimiento m/h",
        ascending=True,
    )
    if data.empty:
        return None
    if operador_col != "Operador":
        data = data.rename(columns={operador_col: "Operador"})

    fig = px.bar(
        data,
        x="Rendimiento m/h",
        y="Operador",
        orientation="h",
        title="Ranking de rendimiento por operador",
        text="Rendimiento m/h",
        hover_data={
            "Metros perforados": ":.2f",
            "Horas efectivas perforando": ":.2f",
            "Rendimiento m/h": ":.2f",
        },
        color_discrete_sequence=["#1F77B4"],
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="inside", insidetextanchor="end")
    fig.update_layout(xaxis_title="Rendimiento consolidado m/h", yaxis_title="Operador")
    aplicar_layout_operacional(fig, height=max(520, 90 + 42 * len(data)))
    return fig


def fig_rendimiento_equipo(df_productivo):
    data = calcular_rendimiento_consolidado(
        df_productivo,
        ["Modelo equipo", "Número equipo"],
    )
    if data.empty:
        return None

    data["Equipo"] = data["Modelo equipo"].astype(str) + " " + data["Número equipo"].astype(str)
    data = data.sort_values("Rendimiento m/h", ascending=False)
    fig = px.bar(
        data,
        x="Equipo",
        y="Rendimiento m/h",
        title="Rendimiento consolidado por equipo",
        text="Rendimiento m/h",
        color="Modelo equipo",
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(xaxis_title="Equipo", yaxis_title="Rendimiento m/h")
    aplicar_layout_operacional(fig, tickangle=-30)
    return fig


def fig_metros_equipo(df_productivo):
    if df_productivo.empty:
        return None

    data = df_productivo.groupby(["Modelo equipo", "Número equipo"], as_index=False)["Metros perforados"].sum()
    data["Metros perforados"] = data["Metros perforados"].round(2)
    data = data[data["Metros perforados"] > 0].copy()
    if data.empty:
        return None

    data["Equipo"] = data["Modelo equipo"].astype(str) + " " + data["Número equipo"].astype(str)
    data = data.sort_values("Metros perforados", ascending=False)
    fig = px.bar(
        data,
        x="Equipo",
        y="Metros perforados",
        title="Metros perforados por equipo",
        text="Metros perforados",
        color="Modelo equipo",
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(xaxis_title="Equipo", yaxis_title="Metros perforados")
    aplicar_layout_operacional(fig, tickangle=-30)
    return fig


def fig_utilizacion_equipo(df):
    if df.empty:
        return None

    data = resumen_kpi_equipos(df)
    data = data[data["Utilización"] > 0].copy()
    if data.empty:
        return None

    data = data.sort_values("Utilización", ascending=False)
    fig = px.bar(
        data,
        x="Equipo",
        y="Utilización",
        title="Utilización promedio por equipo",
        text="Utilización",
        color="Modelo equipo",
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig.update_layout(xaxis_title="Equipo", yaxis_title="Utilización promedio %")
    aplicar_layout_operacional(fig, tickangle=-30)
    return fig


def fig_utilizacion_disponibilidad_equipo(df):
    if df.empty:
        return None

    data = resumen_kpi_equipos(df)
    if data.empty:
        return None

    base = data.melt(
        id_vars=["Equipo", "Modelo equipo"],
        value_vars=["Utilización", "Disponibilidad %"],
        var_name="Indicador",
        value_name="Porcentaje",
    )
    base = base[base["Porcentaje"] > 0].copy()
    if base.empty:
        return None

    fig = px.bar(
        base,
        x="Equipo",
        y="Porcentaje",
        color="Indicador",
        barmode="group",
        title="Utilización vs disponibilidad por equipo",
        text="Porcentaje",
        color_discrete_map={
            "Utilización": "#0F766E",
            "Disponibilidad %": "#2563EB",
        },
        hover_data={
            "Modelo equipo": True,
            "Equipo": True,
            "Porcentaje": ":.2f",
        },
    )
    fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig.update_layout(xaxis_title="Equipo", yaxis_title="Porcentaje (%)", legend_title_text="Indicador")
    aplicar_layout_operacional(fig, tickangle=-30)
    return fig


def fig_distribucion_horas(df):
    if df.empty:
        return None

    columnas = {
        "Horas efectivas perforando": "Horas efectivas perforando",
        "Horas avería equipo": "Horas detención mecánica",
        "Horas no efectivas": "Horas detención No efectivas",
    }
    valores = {}
    for etiqueta, columna in columnas.items():
        valores[etiqueta] = pd.to_numeric(df.get(columna, 0), errors="coerce").fillna(0).sum()

    data = pd.Series(valores).replace([float("inf"), -float("inf")], 0).fillna(0)
    data = data[data > 0].round(2)
    if data.empty:
        return None

    fig = px.pie(
        names=data.index,
        values=data.values,
        title="Distribución de horas del turno",
        hole=0.45,
        color_discrete_sequence=["#4CAF50", "#E0A052", "#D65A5A", "#5B9BD5", "#E67E22"],
    )
    fig.update_traces(
        textinfo="label+percent+value",
        textfont=dict(color=CHART_TEXT),
        marker=dict(line=dict(color=CHART_BG, width=2)),
    )
    fig.update_layout(
        height=520,
        margin=dict(l=80, r=80, t=80, b=80),
        title=dict(x=0.02, xanchor="left"),
        template="plotly_dark",
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_PLOT_BG,
        font=dict(color=CHART_TEXT, family="Barlow, Arial, sans-serif"),
        title_font=dict(color=CHART_TEXT, size=18),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.18,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=CHART_TEXT),
        ),
    )
    return fig


def fig_evolucion_diaria_metros_ejecutivo(df):
    if df.empty or "Fecha turno" not in df.columns or "Metros perforados" not in df.columns:
        return None

    base = df.copy()
    base["Fecha turno"] = pd.to_datetime(base["Fecha turno"], errors="coerce")
    base = base.dropna(subset=["Fecha turno"])
    if base.empty:
        return None

    data = base.groupby(base["Fecha turno"].dt.date, as_index=False)["Metros perforados"].sum()
    if data.empty:
        return None

    data = data.rename(columns={"Fecha turno": "Fecha"})
    fig = px.line(
        data,
        x="Fecha",
        y="Metros perforados",
        markers=True,
        title="Evolución diaria de metros perforados",
        color_discrete_sequence=["#2563EB"],
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=9))
    fig.update_layout(xaxis_title="Fecha", yaxis_title="Metros perforados")
    aplicar_layout_operacional(fig, height=460)
    return fig


def fig_ranking_operadores_metros(df):
    if df.empty:
        return None

    data = executive_service.ranking_operadores_metraje(df)
    if data.empty:
        return None

    data = data.sort_values("Metros perforados", ascending=True)
    fig = px.bar(
        data,
        x="Metros perforados",
        y="Operador",
        orientation="h",
        title="Ranking de operadores por metros perforados",
        text="Metros perforados",
        color_discrete_sequence=["#1F77B4"],
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="inside", insidetextanchor="end")
    fig.update_layout(xaxis_title="Metros perforados", yaxis_title="Operador")
    aplicar_layout_operacional(fig, height=max(420, 90 + 42 * len(data)))
    return fig


def fig_pareto_detenciones(df):
    if df.empty:
        return None

    data = executive_service.ranking_causas_detencion(df)
    if data.empty or "Cantidad" not in data.columns:
        return None

    data = data.sort_values("Cantidad", ascending=False).head(10).copy()
    if data.empty:
        return None

    columna_detencion = "Detención/observación" if "Detención/observación" in data.columns else "Causa detención"
    if columna_detencion not in data.columns:
        return None

    data["Acumulado %"] = data["Cantidad"].cumsum() / data["Cantidad"].sum() * 100
    fig = px.bar(
        data,
        x=columna_detencion,
        y="Cantidad",
        title="Pareto de detenciones principales",
        text="Cantidad",
        color_discrete_sequence=["#0F766E"],
    )
    fig.add_scatter(
        x=data[columna_detencion],
        y=data["Acumulado %"],
        mode="lines+markers",
        name="Acumulado %",
        line=dict(color="#DC2626", width=3),
        yaxis="y2",
    )
    if fig.data:
        fig.data[0].update(textposition="outside")
    fig.update_layout(
        xaxis_title="Detención/observación",
        yaxis_title="Cantidad",
        yaxis2=dict(
            title="Acumulado %",
            overlaying="y",
            side="right",
            range=[0, 105],
            showgrid=False,
            color=CHART_TEXT,
            tickfont=dict(color=CHART_TEXT),
            title_font=dict(color=CHART_MUTED),
        ),
        legend_title_text="",
    )
    aplicar_layout_operacional(fig, height=520, tickangle=-25)
    return fig


def tabla_pareto_impacto_horas_perdidas(df):
    if df.empty:
        return None

    columna_causa = columna_disponible(df, "Tipo detención", "Causa detención", "Detención/observación")
    if not columna_causa:
        return None

    horas_no_efectivas = kpi_service.serie_numerica(
        df,
        "Horas detención No efectivas",
        "Horas no efectivas",
    )
    horas_averia = kpi_service.serie_numerica(
        df,
        "Horas detención mecánica",
        "Horas avería equipo",
        "Avería",
    )
    horas_perdidas = horas_no_efectivas.reindex(df.index, fill_value=0) + horas_averia.reindex(df.index, fill_value=0)

    registros = []
    for indice, valor in df[columna_causa].fillna("").astype(str).items():
        causas = [catalog_service.normalizar_causa_detencion(parte) for parte in valor.split(",")]
        causas = [causa for causa in causas if causa]
        if not causas:
            continue

        horas = float(horas_perdidas.loc[indice])
        if horas <= 0:
            continue

        horas_por_causa = horas / len(causas)
        for causa in causas:
            registros.append({"Causa": causa, "Eventos": 1, "Horas perdidas": horas_por_causa})

    if not registros:
        return None

    data = pd.DataFrame(registros)
    data = (
        data.groupby("Causa", as_index=False)
        .sum()
        .sort_values("Horas perdidas", ascending=False)
    )
    total_horas = data["Horas perdidas"].sum()
    if total_horas <= 0:
        return None

    data["Promedio h/evento"] = data["Horas perdidas"] / data["Eventos"].replace(0, pd.NA)
    data["% impacto"] = data["Horas perdidas"] / total_horas * 100
    data = data.fillna(0)
    return data


def fig_pareto_impacto_horas_perdidas(df):
    data = tabla_pareto_impacto_horas_perdidas(df)
    if data is None or data.empty:
        return None

    total_horas = data["Horas perdidas"].sum()
    data = data.head(10).copy()
    data["Horas etiqueta"] = data["Horas perdidas"].round(1)
    data["Acumulado %"] = data["Horas perdidas"].cumsum() / total_horas * 100

    fig = px.bar(
        data,
        x="Causa",
        y="Horas perdidas",
        title="Pareto de impacto operacional por horas perdidas",
        text="Horas etiqueta",
        color_discrete_sequence=["#E0A052"],
    )
    fig.add_scatter(
        x=data["Causa"],
        y=data["Acumulado %"],
        mode="lines+markers",
        name="Acumulado %",
        line=dict(color="#DC2626", width=3),
        marker=dict(size=8),
        yaxis="y2",
    )
    if fig.data:
        fig.data[0].update(texttemplate="%{text:.1f}", textposition="outside")
    fig.update_layout(
        xaxis_title="Causa detención / actividad no efectiva",
        yaxis_title="Horas perdidas",
        yaxis2=dict(
            title="Acumulado %",
            overlaying="y",
            side="right",
            range=[0, 105],
            showgrid=False,
            color=CHART_TEXT,
            tickfont=dict(color=CHART_TEXT),
            title_font=dict(color=CHART_MUTED),
        ),
        legend_title_text="",
    )
    aplicar_layout_operacional(fig, height=540, tickangle=-25)
    return fig


def tabla_impacto_categoria_detencion(df):
    data = tabla_pareto_impacto_horas_perdidas(df)
    if data is None or data.empty:
        return None

    data = data.copy()
    data["Categoría"] = data["Causa"].apply(catalog_service.clasificar_categoria_detencion)
    resumen = (
        data.groupby("Categoría", as_index=False)[["Eventos", "Horas perdidas"]]
        .sum()
        .sort_values("Horas perdidas", ascending=False)
    )
    total_horas = resumen["Horas perdidas"].sum()
    if total_horas <= 0:
        return None

    resumen["Promedio h/evento"] = resumen["Horas perdidas"] / resumen["Eventos"].replace(0, pd.NA)
    resumen["% impacto"] = resumen["Horas perdidas"] / total_horas * 100
    return resumen.fillna(0)


def causas_detencion_sin_categoria(df):
    data = tabla_pareto_impacto_horas_perdidas(df)
    if data is None or data.empty:
        return []

    data = data.copy()
    data["Categoría"] = data["Causa"].apply(catalog_service.clasificar_categoria_detencion)
    sin_categoria = data[data["Categoría"].eq("Sin Clasificar")]
    if sin_categoria.empty:
        return []

    return sin_categoria.sort_values("Horas perdidas", ascending=False)["Causa"].tolist()


def fig_impacto_categoria_detencion(df):
    data = tabla_impacto_categoria_detencion(df)
    if data is None or data.empty:
        return None

    data = data.copy()
    data["Etiqueta"] = data.apply(
        lambda fila: f"{fila['Horas perdidas']:.1f} h ({fila['% impacto']:.1f}%)",
        axis=1,
    )
    fig = px.bar(
        data,
        x="Categoría",
        y="Horas perdidas",
        title="Impacto operacional por categoría",
        text="Etiqueta",
        color="Categoría",
        custom_data=["% impacto"],
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig.update_traces(textposition="outside", hovertemplate="<b>%{x}</b><br>Horas perdidas: %{y:.1f}<br>% impacto: %{customdata[0]:.1f}%<extra></extra>")
    fig.update_layout(
        xaxis_title="Categoría",
        yaxis_title="Horas perdidas",
        legend_title_text="Categoría",
    )
    aplicar_layout_operacional(fig, height=480, tickangle=-15)
    return fig


def fig_alertas_operacionales_ejecutivo(detalle_alertas):
    if detalle_alertas is None or getattr(detalle_alertas, "empty", True):
        return None

    columnas = ["Tipo de alerta", "causa", "Causa", "Alerta", "alerta"]
    columna = next((nombre for nombre in columnas if nombre in detalle_alertas.columns), None)
    if not columna:
        return None

    valores = []
    for valor in detalle_alertas[columna].dropna().astype(str):
        for parte in valor.split(","):
            texto = parte.strip()
            if texto:
                valores.append(texto)
    if not valores:
        return None

    conteo = pd.Series(valores).value_counts().reset_index()
    conteo.columns = ["Alerta", "Cantidad"]
    conteo = conteo.head(10).sort_values("Cantidad", ascending=True)

    fig = px.bar(
        conteo,
        x="Cantidad",
        y="Alerta",
        orientation="h",
        title="Alertas operacionales principales",
        text="Cantidad",
        color_discrete_sequence=["#DC2626"],
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="Cantidad", yaxis_title="")
    aplicar_layout_operacional(fig, height=max(420, 90 + 40 * len(conteo)))
    return fig
