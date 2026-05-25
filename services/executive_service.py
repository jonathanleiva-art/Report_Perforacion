import pandas as pd

import db
from metrics import calcular_rendimiento_consolidado
from services.alert_service import evaluar_alertas_operacionales


OBJETIVO_UTILIZACION = 85.0
OBJETIVO_DISPONIBILIDAD = 90.0
OBJETIVO_RENDIMIENTO = 15.0


def consultar_panel_ejecutivo(
    db_path=db.DB_PATH,
    fecha_desde=None,
    fecha_hasta=None,
    turno=None,
    equipo=None,
    operador=None,
):
    filtros = {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "turno": turno,
        "equipo": equipo,
        "operador": operador,
    }
    df = db.consultar_historial_filtrado(db_path=db_path, **filtros)
    alertas = evaluar_alertas_operacionales(df) if not df.empty else {"mensajes": [], "detalle": pd.DataFrame(), "sin_alertas": False}
    kpis = calcular_kpis_ejecutivos(df)
    salud = calcular_indice_salud_operacional(
        utilizacion=kpis["utilizacion_promedio"],
        disponibilidad=kpis["disponibilidad_promedio"],
        rendimiento=kpis["rendimiento_promedio"],
        horas_no_efectivas=kpis["horas_no_efectivas"],
        horas_totales=max(kpis["horas_efectivas"] + kpis["horas_no_efectivas"], 0),
        cantidad_alertas=len(alertas.get("detalle", pd.DataFrame())),
        cantidad_registros=len(df),
    )
    return {
        "kpis": kpis,
        "salud": salud,
        "rankings": calcular_rankings(df),
        "tendencia": calcular_tendencia(df),
        "alertas": alertas,
        "total_registros": len(df),
    }


def calcular_kpis_ejecutivos(df):
    if df is None or df.empty:
        return {
            "metros_perforados_totales": 0.0,
            "horas_efectivas": 0.0,
            "horas_no_efectivas": 0.0,
            "disponibilidad_promedio": 0.0,
            "utilizacion_promedio": 0.0,
            "rendimiento_promedio": 0.0,
            "equipos_activos": 0,
            "operadores_registrados": 0,
        }

    metros = serie_numerica(df, "Metros perforados")
    horas_efectivas = serie_numerica(df, "Horas efectivas perforando")
    horas_no_efectivas = serie_numerica(df, "Horas detención No efectivas", "Horas no efectivas")
    disponibilidad = serie_numerica(df, "Disponibilidad %")
    utilizacion = serie_numerica(df, "Utilización %", "Utilizacion %")
    rendimiento = calcular_rendimiento_consolidado(df)

    equipo_col = buscar_columna(df, "Equipo", "Número equipo", "Modelo equipo")
    operador_col = buscar_columna(df, "Operador")

    equipos_activos = 0
    if equipo_col:
        activos = df.loc[(metros > 0) | (horas_efectivas > 0), equipo_col].dropna().astype(str).str.strip()
        equipos_activos = int(activos[activos.ne("")].nunique())

    operadores_registrados = 0
    if operador_col:
        operadores = df[operador_col].dropna().astype(str).str.strip()
        operadores_registrados = int(operadores[operadores.ne("")].nunique())

    return {
        "metros_perforados_totales": round(float(metros.sum()), 2),
        "horas_efectivas": round(float(horas_efectivas.sum()), 2),
        "horas_no_efectivas": round(float(horas_no_efectivas.sum()), 2),
        "disponibilidad_promedio": round(float(disponibilidad.mean()), 2) if not disponibilidad.empty else 0.0,
        "utilizacion_promedio": round(float(utilizacion.mean()), 2) if not utilizacion.empty else 0.0,
        "rendimiento_promedio": round(float(rendimiento), 2),
        "equipos_activos": equipos_activos,
        "operadores_registrados": operadores_registrados,
    }


def calcular_indice_salud_operacional(
    utilizacion,
    disponibilidad,
    rendimiento,
    horas_no_efectivas,
    horas_totales,
    cantidad_alertas,
    cantidad_registros,
):
    score_utilizacion = limitar_0_100(float(utilizacion or 0) / OBJETIVO_UTILIZACION * 100)
    score_disponibilidad = limitar_0_100(float(disponibilidad or 0) / OBJETIVO_DISPONIBILIDAD * 100)
    score_rendimiento = limitar_0_100(float(rendimiento or 0) / OBJETIVO_RENDIMIENTO * 100)

    if float(horas_totales or 0) <= 0:
        score_horas = 0.0
    else:
        proporcion_no_efectiva = max(float(horas_no_efectivas or 0), 0.0) / float(horas_totales)
        score_horas = limitar_0_100(100 - proporcion_no_efectiva * 100)

    if int(cantidad_registros or 0) <= 0:
        score_alertas = 100.0 if int(cantidad_alertas or 0) == 0 else 0.0
    else:
        alertas_por_registro = max(float(cantidad_alertas or 0), 0.0) / int(cantidad_registros)
        score_alertas = limitar_0_100(100 - alertas_por_registro * 100)

    indice = (
        score_utilizacion * 0.25
        + score_disponibilidad * 0.25
        + score_rendimiento * 0.20
        + score_horas * 0.15
        + score_alertas * 0.15
    )
    indice = round(limitar_0_100(indice), 2)
    return {
        "indice": indice,
        "semaforo": semaforo_operacional(indice),
        "detalle": {
            "utilizacion": round(score_utilizacion, 2),
            "disponibilidad": round(score_disponibilidad, 2),
            "rendimiento": round(score_rendimiento, 2),
            "horas_no_efectivas": round(score_horas, 2),
            "alertas": round(score_alertas, 2),
        },
    }


def semaforo_operacional(indice):
    if indice >= 75:
        return {
            "estado": "verde",
            "titulo": "Operación estable",
            "mensaje": "Los indicadores principales se mantienen dentro de rangos esperados.",
        }
    if indice >= 50:
        return {
            "estado": "amarillo",
            "titulo": "Atención requerida",
            "mensaje": "Existen desviaciones operacionales que requieren seguimiento.",
        }
    return {
        "estado": "rojo",
        "titulo": "Condición crítica",
        "mensaje": "La operación presenta deterioro relevante en KPIs o alertas.",
    }


def calcular_rankings(df):
    if df is None or df.empty:
        return {
            "mejor_rendimiento_equipos": pd.DataFrame(),
            "menor_utilizacion_equipos": pd.DataFrame(),
            "mayor_metraje_operadores": pd.DataFrame(),
            "principales_causas_detencion": pd.DataFrame(),
        }

    return {
        "mejor_rendimiento_equipos": ranking_equipos_rendimiento(df),
        "menor_utilizacion_equipos": ranking_equipos_menor_utilizacion(df),
        "mayor_metraje_operadores": ranking_operadores_metraje(df),
        "principales_causas_detencion": ranking_causas_detencion(df),
    }


def ranking_equipos_rendimiento(df):
    equipo_col = buscar_columna(df, "Equipo", "Número equipo", "Modelo equipo")
    if not equipo_col:
        return pd.DataFrame(columns=["Equipo", "Metros perforados", "Horas efectivas perforando", "Rendimiento m/h"])
    base = df.copy()
    base["Metros perforados"] = serie_numerica(base, "Metros perforados")
    base["Horas efectivas perforando"] = serie_numerica(base, "Horas efectivas perforando")
    base = base[(base["Metros perforados"] > 0) & (base["Horas efectivas perforando"] > 0)]
    if base.empty:
        return pd.DataFrame(columns=["Equipo", "Metros perforados", "Horas efectivas perforando", "Rendimiento m/h"])
    resultado = base.groupby(equipo_col, as_index=False).agg({
        "Metros perforados": "sum",
        "Horas efectivas perforando": "sum",
    })
    resultado["Rendimiento m/h"] = resultado["Metros perforados"] / resultado["Horas efectivas perforando"]
    resultado = resultado.rename(columns={equipo_col: "Equipo"})
    return resultado.round(2).sort_values("Rendimiento m/h", ascending=False).head(10)


def ranking_equipos_menor_utilizacion(df):
    equipo_col = buscar_columna(df, "Equipo", "Número equipo", "Modelo equipo")
    if not equipo_col:
        return pd.DataFrame(columns=["Equipo", "Utilización promedio %"])
    base = df.copy()
    base["Utilización %"] = serie_numerica(base, "Utilización %", "Utilizacion %")
    resultado = base.groupby(equipo_col, as_index=False).agg({"Utilización %": "mean"})
    resultado = resultado.rename(columns={equipo_col: "Equipo", "Utilización %": "Utilización promedio %"})
    return resultado.round(2).sort_values("Utilización promedio %", ascending=True).head(10)


def ranking_operadores_metraje(df):
    operador_col = buscar_columna(df, "Operador")
    if not operador_col:
        return pd.DataFrame(columns=["Operador", "Metros perforados"])
    base = df.copy()
    base["Metros perforados"] = serie_numerica(base, "Metros perforados")
    resultado = base.groupby(operador_col, as_index=False).agg({"Metros perforados": "sum"})
    resultado = resultado.rename(columns={operador_col: "Operador"})
    return resultado.round(2).sort_values("Metros perforados", ascending=False).head(10)


def ranking_causas_detencion(df):
    columnas = [col for col in ["Causa detención", "Tipo detención"] if col in df.columns]
    if not columnas:
        return pd.DataFrame(columns=["Causa detención", "Cantidad"])
    valores = []
    for columna in columnas:
        for valor in df[columna].dropna().astype(str):
            for parte in valor.split(","):
                texto = parte.strip()
                if texto:
                    valores.append(texto)
    if not valores:
        return pd.DataFrame(columns=["Causa detención", "Cantidad"])
    serie = pd.Series(valores, dtype=str)
    return (
        serie.value_counts()
        .rename_axis("Causa detención")
        .reset_index(name="Cantidad")
        .head(10)
    )


def calcular_tendencia(df):
    columnas = ["Periodo", "Metros perforados", "Utilización promedio %", "Disponibilidad promedio %", "Rendimiento m/h"]
    if df is None or df.empty or "Fecha turno" not in df.columns:
        return pd.DataFrame(columns=columnas)

    base = df.copy()
    base["Fecha turno"] = pd.to_datetime(base["Fecha turno"], errors="coerce")
    base = base.dropna(subset=["Fecha turno"])
    if base["Fecha turno"].dt.date.nunique() < 7:
        return pd.DataFrame(columns=columnas)

    base["Periodo"] = base["Fecha turno"].dt.to_period("W").astype(str)
    base["Metros perforados"] = serie_numerica(base, "Metros perforados")
    base["Horas efectivas perforando"] = serie_numerica(base, "Horas efectivas perforando")
    base["Utilización %"] = serie_numerica(base, "Utilización %", "Utilizacion %")
    base["Disponibilidad %"] = serie_numerica(base, "Disponibilidad %")
    tendencia = base.groupby("Periodo", as_index=False).agg({
        "Metros perforados": "sum",
        "Horas efectivas perforando": "sum",
        "Utilización %": "mean",
        "Disponibilidad %": "mean",
    })
    tendencia["Rendimiento m/h"] = tendencia.apply(
        lambda row: row["Metros perforados"] / row["Horas efectivas perforando"]
        if row["Horas efectivas perforando"] > 0 else 0,
        axis=1,
    )
    tendencia = tendencia.rename(columns={
        "Utilización %": "Utilización promedio %",
        "Disponibilidad %": "Disponibilidad promedio %",
    })
    return tendencia[columnas].round(2)


def serie_numerica(df, *columnas):
    columna = buscar_columna(df, *columnas)
    if not columna:
        return pd.Series(0.0, index=df.index, dtype=float)
    return pd.to_numeric(df[columna], errors="coerce").fillna(0)


def buscar_columna(df, *candidatos):
    normalizadas = {normalizar(col): col for col in df.columns}
    for candidato in candidatos:
        columna = normalizadas.get(normalizar(candidato))
        if columna:
            return columna
    return None


def normalizar(valor):
    from unicodedata import normalize

    return normalize("NFKD", str(valor)).encode("ascii", "ignore").decode("ascii").lower().strip()


def limitar_0_100(valor):
    return max(0.0, min(float(valor or 0), 100.0))
