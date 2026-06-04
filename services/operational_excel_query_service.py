from pathlib import Path

import pandas as pd

from config import DATABASE_PATH
from metrics import calcular_kpis_consolidados_dataframe
from services import operational_excel_service, source_service


TIPOS_OPERACIONALES = operational_excel_service.TIPOS_FUENTE_OPERACIONAL
ESTADO_IMPORTADA = "importada"


def _serie_texto_no_vacia(df, columna):
    if df is None or df.empty or columna not in df.columns:
        return pd.Series(dtype=str)
    serie = df[columna].dropna().astype(str).str.strip()
    return serie[serie.ne("")]


def _normalizar_estado(serie):
    return serie.fillna("").astype(str).str.strip().str.lower()


def listar_fuentes_operacionales_importadas(db_path=DATABASE_PATH):
    fuentes = source_service.listar_fuentes_datos(
        db_path=db_path,
        solo_activas=True,
        incluir_eliminadas=False,
    )
    if fuentes.empty:
        return pd.DataFrame(columns=list(source_service.COLUMNAS_FUENTES))

    tipos = fuentes.get("tipo_fuente", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    estados = _normalizar_estado(fuentes.get("estado", pd.Series(dtype=str)))
    resultado = fuentes[tipos.isin(TIPOS_OPERACIONALES) & estados.eq(ESTADO_IMPORTADA)].copy()
    if resultado.empty:
        return pd.DataFrame(columns=fuentes.columns)
    return resultado.sort_values(["fecha_importacion", "id_fuente"], ascending=[False, False]).reset_index(drop=True)


def cargar_registros_operacionales_por_fuente(id_fuente, db_path=DATABASE_PATH):
    if id_fuente is None:
        return pd.DataFrame()
    registros = operational_excel_service.leer_registros_operacional(
        db_path=Path(db_path),
        id_fuente=int(id_fuente),
    )
    if registros.empty:
        return operational_excel_service.leer_fuente_operacional_normalizada_df(registros)
    return operational_excel_service.leer_fuente_operacional_normalizada_df(registros)


def calcular_resumen_operacional_excel(id_fuente, db_path=DATABASE_PATH):
    df = cargar_registros_operacionales_por_fuente(id_fuente, db_path=db_path)
    if df.empty:
        return {
            "id_fuente": int(id_fuente) if id_fuente is not None else None,
            "registros": 0,
            "metros_totales": 0.0,
            "fecha_min": None,
            "fecha_max": None,
            "equipos": 0,
            "operadores": 0,
            "horas_efectivas": 0.0,
            "horas_averia": 0.0,
            "horas_mp": 0.0,
            "disponibilidad_promedio": 0.0,
            "utilizacion_promedio": 0.0,
            "rendimiento_promedio_mh": 0.0,
        }

    fechas = pd.to_datetime(df["fecha_turno"], errors="coerce").dropna()
    kpis = calcular_kpis_consolidados_dataframe(pd.DataFrame({
        "Horas Totales": pd.to_numeric(df["horas_totales"], errors="coerce").fillna(0),
        "Horas detencion mecanica": pd.to_numeric(df["horas_averia"], errors="coerce").fillna(0),
        "Mantencion Programada": pd.to_numeric(df["horas_mp"], errors="coerce").fillna(0),
        "Horas efectivas perforando": pd.to_numeric(df["horas_efectivas"], errors="coerce").fillna(0),
        "Metros perforados": pd.to_numeric(df["metros"], errors="coerce").fillna(0),
    }))
    return {
        "id_fuente": int(id_fuente),
        "registros": int(len(df)),
        "metros_totales": round(float(pd.to_numeric(df["metros"], errors="coerce").fillna(0).sum()), 2),
        "fecha_min": fechas.min().date() if not fechas.empty else None,
        "fecha_max": fechas.max().date() if not fechas.empty else None,
        "equipos": int(_serie_texto_no_vacia(df, "equipo").nunique()),
        "operadores": int(_serie_texto_no_vacia(df, "operador").nunique()),
        "horas_efectivas": round(float(pd.to_numeric(df["horas_efectivas"], errors="coerce").fillna(0).sum()), 2),
        "horas_averia": round(float(pd.to_numeric(df["horas_averia"], errors="coerce").fillna(0).sum()), 2),
        "horas_mp": round(float(pd.to_numeric(df["horas_mp"], errors="coerce").fillna(0).sum()), 2),
        "disponibilidad_promedio": round(float(kpis["disponibilidad"]), 2),
        "utilizacion_promedio": round(float(kpis["utilizacion"]), 2),
        "rendimiento_promedio_mh": round(float(kpis["rendimiento"]), 2),
    }


def _ranking_por_columna(id_fuente, columna, nombre_salida, db_path=DATABASE_PATH):
    df = cargar_registros_operacionales_por_fuente(id_fuente, db_path=db_path)
    columnas = [
        nombre_salida,
        "registros",
        "metros_totales",
        "horas_efectivas",
        "horas_averia",
        "horas_mp",
        "disponibilidad_promedio",
        "utilizacion_promedio",
        "rendimiento_promedio_mh",
    ]
    if df.empty or columna not in df.columns:
        return pd.DataFrame(columns=columnas)

    trabajo = df.copy()
    trabajo["_grupo"] = trabajo[columna].fillna("").astype(str).str.strip()
    trabajo = trabajo[trabajo["_grupo"].ne("")]
    if trabajo.empty:
        return pd.DataFrame(columns=columnas)

    filas = []
    for grupo, datos in trabajo.groupby("_grupo", dropna=False):
        kpis = calcular_kpis_consolidados_dataframe(pd.DataFrame({
            "Horas Totales": pd.to_numeric(datos["horas_totales"], errors="coerce").fillna(0),
            "Horas detencion mecanica": pd.to_numeric(datos["horas_averia"], errors="coerce").fillna(0),
            "Mantencion Programada": pd.to_numeric(datos["horas_mp"], errors="coerce").fillna(0),
            "Horas efectivas perforando": pd.to_numeric(datos["horas_efectivas"], errors="coerce").fillna(0),
            "Metros perforados": pd.to_numeric(datos["metros"], errors="coerce").fillna(0),
        }))
        filas.append({
            nombre_salida: grupo,
            "registros": int(len(datos)),
            "metros_totales": round(float(kpis["metros"]), 2),
            "horas_efectivas": round(float(kpis["horas_efectivas"]), 2),
            "horas_averia": round(float(kpis["horas_averia"]), 2),
            "horas_mp": round(float(kpis["horas_mantencion"]), 2),
            "disponibilidad_promedio": round(float(kpis["disponibilidad"]), 2),
            "utilizacion_promedio": round(float(kpis["utilizacion"]), 2),
            "rendimiento_promedio_mh": round(float(kpis["rendimiento"]), 2),
        })
    return pd.DataFrame(filas, columns=columnas).sort_values(
        ["metros_totales", "registros"],
        ascending=[False, False],
    ).reset_index(drop=True)


def obtener_ranking_equipos_excel(id_fuente, db_path=DATABASE_PATH):
    return _ranking_por_columna(id_fuente, "equipo", "equipo", db_path=db_path)


def obtener_ranking_operadores_excel(id_fuente, db_path=DATABASE_PATH):
    return _ranking_por_columna(id_fuente, "operador", "operador", db_path=db_path)
