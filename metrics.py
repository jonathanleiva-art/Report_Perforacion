import pandas as pd

from utils import HORAS_TURNO


def calcular_rendimiento_consolidado(df, group_cols=None):
    columnas_base = ["Metros perforados", "Horas efectivas perforando"]
    if df.empty or not set(columnas_base).issubset(df.columns):
        if group_cols:
            return pd.DataFrame(columns=list(group_cols) + columnas_base + ["Rendimiento m/h"])
        return 0.0

    base = df.copy()
    base["Metros perforados"] = pd.to_numeric(base["Metros perforados"], errors="coerce").fillna(0)
    base["Horas efectivas perforando"] = pd.to_numeric(
        base["Horas efectivas perforando"],
        errors="coerce",
    ).fillna(0)
    base = base[
        (base["Metros perforados"] > 0)
        & (base["Horas efectivas perforando"] > 0)
    ].copy()

    if group_cols:
        if base.empty:
            return pd.DataFrame(columns=list(group_cols) + columnas_base + ["Rendimiento m/h"])

        resultado = base.groupby(list(group_cols), as_index=False).agg({
            "Metros perforados": "sum",
            "Horas efectivas perforando": "sum",
        })
        resultado["Rendimiento m/h"] = (
            resultado["Metros perforados"] / resultado["Horas efectivas perforando"]
        )
        resultado = resultado.replace([float("inf"), -float("inf")], 0).fillna(0)
        resultado["Metros perforados"] = resultado["Metros perforados"].round(2)
        resultado["Horas efectivas perforando"] = resultado["Horas efectivas perforando"].round(2)
        resultado["Rendimiento m/h"] = resultado["Rendimiento m/h"].round(2)
        return resultado[resultado["Rendimiento m/h"] > 0].copy()

    total_horas = base["Horas efectivas perforando"].sum()
    if total_horas <= 0:
        return 0.0

    return float(base["Metros perforados"].sum() / total_horas)


def calcular_utilizacion(horas_efectivas, horas_turno=HORAS_TURNO):
    if horas_turno <= 0:
        return 0.0

    return max(float(horas_efectivas), 0.0) / horas_turno * 100


def calcular_horas_no_disponibles(
    horas_averia=0,
    horas_mantencion=0,
    horas_standby=0,
    horas_sin_marcacion=0,
):
    # Standby por falta de frente/patio y registros sin produccion no sacan al equipo
    # de disponibilidad. Se conservan los parametros por compatibilidad con llamados
    # existentes, pero solo averia y mantencion afectan disponibilidad.
    return sum(
        max(float(valor or 0), 0.0)
        for valor in (horas_averia, horas_mantencion)
    )


def calcular_disponibilidad(
    horas_averia=0,
    horas_turno=HORAS_TURNO,
    horas_mantencion=0,
    horas_standby=0,
    horas_sin_marcacion=0,
):
    if horas_turno <= 0:
        return 0.0

    no_disponibles = calcular_horas_no_disponibles(
        horas_averia=horas_averia,
        horas_mantencion=horas_mantencion,
        horas_standby=horas_standby,
        horas_sin_marcacion=horas_sin_marcacion,
    )
    disponibles = max(horas_turno - min(no_disponibles, horas_turno), 0.0)
    return disponibles / horas_turno * 100


def registros_productivos(df):
    if df.empty or not {"Metros perforados", "Horas efectivas perforando"}.issubset(df.columns):
        return pd.DataFrame(columns=df.columns)

    return df[
        (pd.to_numeric(df["Metros perforados"], errors="coerce").fillna(0) > 0)
        & (pd.to_numeric(df["Horas efectivas perforando"], errors="coerce").fillna(0) > 0)
    ].copy()
