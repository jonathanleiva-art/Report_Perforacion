import pandas as pd
from unicodedata import normalize

from utils import HORAS_TURNO, OPERADORES


def _normalizar_nombre_columna(nombre):
    texto = normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode("ascii")
    return texto.lower().strip()


def _buscar_columna(df, *candidatos):
    columnas_normalizadas = {_normalizar_nombre_columna(col): col for col in df.columns}
    for candidato in candidatos:
        columna = columnas_normalizadas.get(_normalizar_nombre_columna(candidato))
        if columna:
            return columna

    return None


def _serie_numerica(df, *columnas):
    columna = _buscar_columna(df, *columnas)
    if not columna:
        return pd.Series(dtype=float)

    return pd.to_numeric(df[columna], errors="coerce").fillna(0)


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


def calcular_disponibilidad(horas_averia, horas_turno=HORAS_TURNO):
    if horas_turno <= 0:
        return 0.0

    disponibles = max(horas_turno - max(float(horas_averia), 0.0), 0.0)
    return disponibles / horas_turno * 100


def totales_productivos(df):
    if df.empty or not {"Metros perforados", "Horas efectivas perforando"}.issubset(df.columns):
        return 0, 0, 0

    metros = pd.to_numeric(df["Metros perforados"], errors="coerce").fillna(0)
    horas = pd.to_numeric(df["Horas efectivas perforando"], errors="coerce").fillna(0)
    productivos = (metros > 0) & (horas > 0)
    total_metros = metros[productivos].sum()
    total_horas = horas[productivos].sum()
    rendimiento = total_metros / total_horas if total_horas > 0 else 0

    return total_metros, total_horas, rendimiento


def resumen_general_operadores(df):
    columnas = [
        "Operador",
        "Disponibilidad promedio",
        "Utilización promedio",
        "Rendimiento consolidado m/h",
        "Metros totales perforados",
    ]
    operadores = sorted(set(OPERADORES) | set(df.get("Operador", pd.Series(dtype=str)).dropna().astype(str)))
    filas = []

    for operador in operadores:
        df_operador = df[df["Operador"].astype(str) == operador].copy() if "Operador" in df.columns else pd.DataFrame()
        disponibilidad = _serie_numerica(df_operador, "Disponibilidad %")
        utilizacion = _serie_numerica(df_operador, "Utilización %", "Utilizacion %")
        total_metros, _, rendimiento = totales_productivos(df_operador)

        filas.append({
            "Operador": operador,
            "Disponibilidad promedio": round(disponibilidad.mean(), 2) if not disponibilidad.empty else 0.0,
            "Utilización promedio": round(utilizacion.mean(), 2) if not utilizacion.empty else 0.0,
            "Rendimiento consolidado m/h": round(rendimiento, 2),
            "Metros totales perforados": round(total_metros, 2),
        })

    return pd.DataFrame(filas, columns=columnas).sort_values(
        "Metros totales perforados",
        ascending=False,
    )


def resumen_general_equipos(df):
    columnas = [
        "Modelo equipo",
        "Número equipo",
        "Disponibilidad promedio",
        "Utilización promedio",
        "Rendimiento consolidado m/h",
        "Metros totales perforados",
        "Horas efectivas perforando",
        "Horas avería equipo",
        "Horas no efectivas",
    ]
    if df.empty or not {"Modelo equipo", "Número equipo"}.issubset(df.columns):
        return pd.DataFrame(columns=columnas)

    filas = []
    for (modelo, numero), df_equipo in df.groupby(["Modelo equipo", "Número equipo"], dropna=False):
        total_metros, total_horas, rendimiento = totales_productivos(df_equipo)
        disponibilidad = _serie_numerica(df_equipo, "Disponibilidad %")
        utilizacion = _serie_numerica(df_equipo, "Utilización %", "Utilizacion %")
        horas_averia = _serie_numerica(df_equipo, "Horas detención mecánica", "Avería").sum()
        horas_no_efectivas = _serie_numerica(df_equipo, "Horas detención No efectivas").sum()

        filas.append({
            "Modelo equipo": modelo,
            "Número equipo": numero,
            "Disponibilidad promedio": round(disponibilidad.mean(), 2) if not disponibilidad.empty else 0.0,
            "Utilización promedio": round(utilizacion.mean(), 2) if not utilizacion.empty else 0.0,
            "Rendimiento consolidado m/h": round(rendimiento, 2),
            "Metros totales perforados": round(total_metros, 2),
            "Horas efectivas perforando": round(total_horas, 2),
            "Horas avería equipo": round(horas_averia, 2),
            "Horas no efectivas": round(horas_no_efectivas, 2),
        })

    return pd.DataFrame(filas, columns=columnas).sort_values(
        "Metros totales perforados",
        ascending=False,
    )


def tipo_acero(modelo):
    return "Tricono" if str(modelo).strip() == "Sandvik D75KS" else "Bit"


def orden_modelo_acero(modelo):
    orden = {
        "Sandvik D75KS": 1,
        "FlexiROC D65": 2,
        "SmartROC D65": 3,
    }
    return orden.get(str(modelo).strip(), 99)


def numeros_bit_tricono(df):
    columna = _buscar_columna(df, "Número serie Tricono/Bit")
    if not columna:
        return ""

    valores = []
    for valor in df[columna].dropna().astype(str):
        texto = valor.strip()
        if texto and texto.lower() not in ("nan", "none", "nat") and texto not in valores:
            valores.append(texto)

    return ", ".join(valores)


def resumen_general_aceros(df):
    columnas = [
        "Modelo equipo",
        "Número equipo",
        "Tipo acero",
        "Número Bit / Tricono",
        "Metros totales perforados",
        "Rendimiento consolidado m/h",
    ]
    if df.empty or not {"Modelo equipo", "Número equipo"}.issubset(df.columns):
        return pd.DataFrame(columns=columnas)

    filas = []
    for (modelo, numero), df_equipo in df.groupby(["Modelo equipo", "Número equipo"], dropna=False):
        total_metros, _, rendimiento = totales_productivos(df_equipo)
        filas.append({
            "Modelo equipo": modelo,
            "Número equipo": numero,
            "Tipo acero": tipo_acero(modelo),
            "Número Bit / Tricono": numeros_bit_tricono(df_equipo),
            "Metros totales perforados": round(total_metros, 2),
            "Rendimiento consolidado m/h": round(rendimiento, 2),
        })

    resumen = pd.DataFrame(filas, columns=columnas)
    resumen["_orden_modelo"] = resumen["Modelo equipo"].apply(orden_modelo_acero)
    resumen["_orden_numero"] = pd.to_numeric(resumen["Número equipo"], errors="coerce").fillna(999999)
    return resumen.sort_values(["_orden_modelo", "_orden_numero"]).drop(
        columns=["_orden_modelo", "_orden_numero"],
    )


def registros_productivos(df):
    if df.empty or not {"Metros perforados", "Horas efectivas perforando"}.issubset(df.columns):
        return pd.DataFrame(columns=df.columns)

    return df[
        (pd.to_numeric(df["Metros perforados"], errors="coerce").fillna(0) > 0)
        & (pd.to_numeric(df["Horas efectivas perforando"], errors="coerce").fillna(0) > 0)
    ].copy()
