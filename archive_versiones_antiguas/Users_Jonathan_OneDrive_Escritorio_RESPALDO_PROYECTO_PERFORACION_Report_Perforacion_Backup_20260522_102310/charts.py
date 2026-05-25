import pandas as pd
import plotly.express as px

from metrics import calcular_rendimiento_consolidado

COLOR_SEQUENCE = px.colors.qualitative.Safe


def aplicar_layout_operacional(fig, height=520, tickangle=0):
    fig.update_layout(
        height=height,
        margin=dict(l=120, r=80, t=80, b=120),
        title=dict(x=0.02, xanchor="left"),
        uniformtext_minsize=10,
        uniformtext_mode="hide",
    )
    fig.update_xaxes(automargin=True, tickangle=tickangle)
    fig.update_yaxes(automargin=True)
    return fig


def fig_ranking_operadores(df_productivo):
    data = calcular_rendimiento_consolidado(df_productivo, ["Operador"]).sort_values(
        "Rendimiento m/h",
        ascending=True,
    )
    if data.empty:
        return None

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
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
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
    if df.empty or "Utilización %" not in df.columns:
        return None

    data = df.groupby(["Modelo equipo", "Número equipo"], as_index=False)["Utilización %"].mean()
    data["Utilización %"] = data["Utilización %"].round(2)
    data = data[data["Utilización %"] > 0].copy()
    if data.empty:
        return None

    data["Equipo"] = data["Modelo equipo"].astype(str) + " " + data["Número equipo"].astype(str)
    data = data.sort_values("Utilización %", ascending=False)
    fig = px.bar(
        data,
        x="Equipo",
        y="Utilización %",
        title="Utilización promedio por equipo",
        text="Utilización %",
        color="Modelo equipo",
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig.update_layout(xaxis_title="Equipo", yaxis_title="Utilización promedio %")
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
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_traces(textinfo="label+percent+value")
    fig.update_layout(
        height=520,
        margin=dict(l=80, r=80, t=80, b=80),
        title=dict(x=0.02, xanchor="left"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5),
    )
    return fig
