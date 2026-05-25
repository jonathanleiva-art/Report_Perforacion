import pandas as pd
import plotly.express as px

from metrics import calcular_disponibilidad, calcular_rendimiento_consolidado, calcular_utilizacion
from utils import EQUIPOS, HORAS_TURNO, limpiar_entero

COLOR_SEQUENCE = px.colors.qualitative.Safe


EQUIPO_COLORS = {
    "Sandvik D75KS": "#1F77B4",
    "SmartROC D65": "#0F766E",
    "FlexiROC D65": "#F59E0B",
}


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


def resumen_kpi_equipos(df):
    columnas = [
        "Modelo equipo",
        "Número equipo",
        "Equipo",
        "Metros perforados",
        "Pozos perforados",
        "Disponibilidad %",
        "Utilización %",
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
    mantencion_col = columna_disponible(base, "Mantención Programada", "Mantencion Programada", "Mantención")
    standby_col = columna_disponible(base, "Standby por falta de tajo/Patio")
    sin_marcacion_col = columna_disponible(base, "Sin marcación")

    filas = []
    orden = orden_equipos()
    for (modelo, numero), grupo in base.groupby(["Modelo equipo", "Número equipo"], dropna=False):
        metros = pd.to_numeric(grupo.get("Metros perforados", 0), errors="coerce").fillna(0).sum()
        horas = pd.to_numeric(grupo.get("Horas efectivas perforando", 0), errors="coerce").fillna(0).sum()
        pozos = pd.to_numeric(grupo.get(pozos_col, 0), errors="coerce").fillna(0).sum() if pozos_col else 0
        horas_averia = pd.to_numeric(grupo.get(averia_col, 0), errors="coerce").fillna(0).sum() if averia_col else 0
        horas_mantencion = pd.to_numeric(grupo.get(mantencion_col, 0), errors="coerce").fillna(0).sum() if mantencion_col else 0
        horas_standby = pd.to_numeric(grupo.get(standby_col, 0), errors="coerce").fillna(0).sum() if standby_col else 0
        horas_sin_marcacion = pd.to_numeric(grupo.get(sin_marcacion_col, 0), errors="coerce").fillna(0).sum() if sin_marcacion_col else 0
        rendimiento = metros / horas if horas > 0 else 0
        horas_programadas = HORAS_TURNO * max(len(grupo), 1)
        disponibilidad = calcular_disponibilidad(
            horas_averia,
            horas_turno=horas_programadas,
            horas_mantencion=horas_mantencion,
            horas_standby=horas_standby,
            horas_sin_marcacion=horas_sin_marcacion,
        )
        utilizacion = calcular_utilizacion(horas, horas_turno=horas_programadas)
        numero_limpio = limpiar_entero(numero)
        filas.append({
            "Modelo equipo": modelo,
            "Número equipo": numero_limpio,
            "Equipo": f"{modelo} {numero_limpio}",
            "Metros perforados": round(metros, 2),
            "Pozos perforados": round(pozos, 0),
            "Disponibilidad %": round(disponibilidad, 2),
            "Utilización %": round(utilizacion, 2),
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
    if df.empty:
        return None

    data = resumen_kpi_equipos(df)
    data = data[data["Utilización %"] > 0].copy()
    if data.empty:
        return None

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
