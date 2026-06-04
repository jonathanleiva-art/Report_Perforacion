import pandas as pd
from unicodedata import normalize

from utils import HORAS_TURNO


def _numero_no_negativo(valor):
    try:
        numero = pd.to_numeric(valor, errors="coerce")
    except TypeError:
        numero = 0.0
    if pd.isna(numero):
        return 0.0
    return max(float(numero), 0.0)


def _serie_no_negativa(valor, index=None):
    if isinstance(valor, pd.Series):
        return pd.to_numeric(valor, errors="coerce").fillna(0).clip(lower=0)
    if index is None:
        return _numero_no_negativo(valor)
    return pd.Series(_numero_no_negativo(valor), index=index, dtype=float)


def calcular_horas_disponibles(
    horas_totales=HORAS_TURNO,
    horas_averia=0,
    horas_mantencion=0,
):
    if isinstance(horas_totales, pd.Series):
        index = horas_totales.index
        totales = _serie_no_negativa(horas_totales)
        averia = _serie_no_negativa(horas_averia, index=index)
        mantencion = _serie_no_negativa(horas_mantencion, index=index)
        return (totales - averia - mantencion).clip(lower=0)

    totales = _numero_no_negativo(horas_totales)
    no_disponibles = _numero_no_negativo(horas_averia) + _numero_no_negativo(horas_mantencion)
    return max(totales - no_disponibles, 0.0)


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


def calcular_utilizacion(
    horas_efectivas,
    horas_disponibles=None,
    horas_turno=HORAS_TURNO,
    horas_averia=0,
    horas_mantencion=0,
):
    if horas_disponibles is None:
        horas_disponibles = calcular_horas_disponibles(
            horas_turno,
            horas_averia=horas_averia,
            horas_mantencion=horas_mantencion,
        )
    disponibles = _numero_no_negativo(horas_disponibles)
    if disponibles <= 0:
        return 0.0

    return _numero_no_negativo(horas_efectivas) / disponibles * 100


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

    disponibles = calcular_horas_disponibles(
        horas_turno,
        horas_averia=horas_averia,
        horas_mantencion=horas_mantencion,
    )
    return disponibles / horas_turno * 100


def calcular_disponibilidad_consolidada(horas_totales, horas_averia=0, horas_mantencion=0):
    totales = _numero_no_negativo(horas_totales)
    if totales <= 0:
        return 0.0
    disponibles = calcular_horas_disponibles(
        totales,
        horas_averia=horas_averia,
        horas_mantencion=horas_mantencion,
    )
    return disponibles / totales * 100


def calcular_utilizacion_consolidada(horas_efectivas, horas_totales, horas_averia=0, horas_mantencion=0):
    disponibles = calcular_horas_disponibles(
        horas_totales,
        horas_averia=horas_averia,
        horas_mantencion=horas_mantencion,
    )
    return calcular_utilizacion(horas_efectivas, horas_disponibles=disponibles)


def _normalizar_columna_kpi(valor):
    texto = str(valor or "").strip()
    reemplazos = {
        "Ã¡": "a", "Ã©": "e", "Ã­": "i", "Ã³": "o", "Ãº": "u", "Ã±": "n",
        "Ã": "A", "Ã‰": "E", "Ã": "I", "Ã“": "O", "Ãš": "U", "Ã‘": "N",
    }
    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)
    texto = normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return "".join(char for char in texto.lower() if char.isalnum())


def _columna_disponible(df, *candidatos):
    normalizadas = {_normalizar_columna_kpi(col): col for col in df.columns}
    for candidato in candidatos:
        columna = normalizadas.get(_normalizar_columna_kpi(candidato))
        if columna is not None:
            return columna
    return None


def serie_numerica_kpi(df, *columnas):
    if df is None or df.empty:
        return pd.Series(dtype=float)
    columna = _columna_disponible(df, *columnas)
    if columna is None:
        return pd.Series([0.0] * len(df), index=df.index, dtype=float)
    return pd.to_numeric(df[columna], errors="coerce").fillna(0.0)


def calcular_kpis_consolidados_dataframe(df, horas_totales_por_registro=HORAS_TURNO):
    if df is None or df.empty:
        return {
            "horas_totales": 0.0,
            "horas_disponibles": 0.0,
            "horas_efectivas": 0.0,
            "horas_averia": 0.0,
            "horas_mantencion": 0.0,
            "metros": 0.0,
            "disponibilidad": 0.0,
            "utilizacion": 0.0,
            "rendimiento": 0.0,
        }

    horas_totales = serie_numerica_kpi(df, "Horas Totales", "Total horas ingresadas", "Horas turno")
    if horas_totales.empty or float(horas_totales.sum()) <= 0:
        horas_totales = pd.Series(float(horas_totales_por_registro), index=df.index, dtype=float)

    horas_averia = serie_numerica_kpi(df, "Horas detención mecánica", "Horas detencion mecanica", "Horas avería equipo", "Horas averia equipo", "Avería")
    horas_mantencion = serie_numerica_kpi(df, "Mantención Programada", "Mantencion Programada", "Horas MP", "horas_mp")
    horas_efectivas = serie_numerica_kpi(df, "Horas efectivas perforando")
    metros = serie_numerica_kpi(df, "Metros perforados")
    horas_disponibles = calcular_horas_disponibles(
        horas_totales,
        horas_averia=horas_averia,
        horas_mantencion=horas_mantencion,
    )

    total_horas = float(horas_totales.sum())
    total_disponibles = float(horas_disponibles.sum())
    total_efectivas = float(horas_efectivas.sum())
    total_metros = float(metros.sum())
    return {
        "horas_totales": round(total_horas, 2),
        "horas_disponibles": round(total_disponibles, 2),
        "horas_efectivas": round(total_efectivas, 2),
        "horas_averia": round(float(horas_averia.sum()), 2),
        "horas_mantencion": round(float(horas_mantencion.sum()), 2),
        "metros": round(total_metros, 2),
        "disponibilidad": round(total_disponibles / total_horas * 100, 2) if total_horas > 0 else 0.0,
        "utilizacion": round(total_efectivas / total_disponibles * 100, 2) if total_disponibles > 0 else 0.0,
        "rendimiento": round(total_metros / total_efectivas, 2) if total_efectivas > 0 else 0.0,
    }


def registros_productivos(df):
    if df.empty or not {"Metros perforados", "Horas efectivas perforando"}.issubset(df.columns):
        return pd.DataFrame(columns=df.columns)

    return df[
        (pd.to_numeric(df["Metros perforados"], errors="coerce").fillna(0) > 0)
        & (pd.to_numeric(df["Horas efectivas perforando"], errors="coerce").fillna(0) > 0)
    ].copy()
