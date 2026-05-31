from calendar import monthrange
from datetime import date
from pathlib import Path
import re
from unicodedata import normalize

import pandas as pd
import streamlit as st

import db
from services import kpi_service


RESULTADO_BASE = {
    "anio": 0,
    "mes": 0,
    "fecha_inicio": "",
    "fecha_fin": "",
    "cantidad_registros": 0,
    "metros_totales": 0.0,
    "horas_efectivas_totales": 0.0,
    "horas_no_efectivas_totales": 0.0,
    "horas_averias_totales": 0.0,
    "disponibilidad_promedio": 0.0,
    "utilizacion_promedio": 0.0,
    "rendimiento_promedio": 0.0,
    "equipos_distintos": 0,
    "operadores_distintos": 0,
}

COLUMNAS = {
    "fecha": ["Fecha turno", "Fecha"],
    "metros": ["Metros perforados"],
    "horas_efectivas": ["Horas efectivas perforando"],
    "horas_no_efectivas": [
        "Horas detencion No efectivas",
        "Horas detención No efectivas",
        "Horas no efectivas",
        "Horas no efectivas operacionales",
    ],
    "horas_averias": [
        "Horas averia equipo",
        "Horas avería equipo",
        "Horas detencion mecanica",
        "Horas detención mecánica",
    ],
    "disponibilidad": ["Disponibilidad %", "Disponibilidad"],
    "utilizacion": ["Utilización", "Utilización", "Utilización", "Utilización"],
    "rendimiento": ["Rendimiento m/h", "Rendimiento consolidado m/h", "Rendimiento"],
    "equipo": ["Número equipo", "Número equipo", "Equipo"],
    "operador": ["Operador"],
}

MOJIBAKE_REEMPLAZOS = {
    "Ã¡": "a",
    "Ã©": "e",
    "Ã­": "i",
    "Ã³": "o",
    "Ãº": "u",
    "Ã±": "n",
    "Ã": "A",
    "Ã‰": "E",
    "Ã": "I",
    "Ã“": "O",
    "Ãš": "U",
    "Ã‘": "N",
}


def _db_mtime(db_path):
    path = Path(db_path)
    return path.stat().st_mtime if path.exists() else 0


def obtener_resumen_mensual(anio: int, mes: int, db_path=db.DB_PATH):
    return _obtener_resumen_mensual_cached(anio, mes, str(Path(db_path).resolve()), _db_mtime(db_path))


@st.cache_data(show_spinner=False)
def _obtener_resumen_mensual_cached(anio: int, mes: int, db_path_text: str, mtime: float):
    db_path = Path(db_path_text)
    fecha_inicio, fecha_fin = _rango_mes(anio, mes)
    resultado = _resultado_vacio(anio, mes, fecha_inicio, fecha_fin)

    mensual, columnas = _obtener_dataframe_mensual(anio, mes, db_path=db_path)
    if mensual.empty:
        return resultado

    horas_efectivas = _serie_numerica(mensual, columnas.get("horas_efectivas"))
    metros = _serie_numerica(mensual, columnas.get("metros"))

    resultado.update(
        {
            "cantidad_registros": int(len(mensual)),
            "metros_totales": _redondear(metros.sum()),
            "horas_efectivas_totales": _redondear(horas_efectivas.sum()),
            "horas_no_efectivas_totales": _redondear(_serie_numerica(mensual, columnas.get("horas_no_efectivas")).sum()),
            "horas_averias_totales": _redondear(_serie_numerica(mensual, columnas.get("horas_averias")).sum()),
            "disponibilidad_promedio": _redondear(_serie_numerica(mensual, columnas.get("disponibilidad")).mean()),
            "utilizacion_promedio": _redondear(_serie_numerica(mensual, columnas.get("utilizacion")).mean()),
            "rendimiento_promedio": _redondear(_calcular_rendimiento(mensual, columnas, metros, horas_efectivas)),
            "equipos_distintos": _contar_distintos(mensual, columnas.get("equipo")),
            "operadores_distintos": _contar_distintos(mensual, columnas.get("operador")),
        }
    )
    return resultado


def obtener_ranking_equipos_mensual(anio: int, mes: int, db_path=db.DB_PATH):
    return _obtener_ranking_mensual_cached(
        anio,
        mes,
        "equipo",
        "numero_equipo",
        str(Path(db_path).resolve()),
        _db_mtime(db_path),
    )


def obtener_ranking_operadores_mensual(anio: int, mes: int, db_path=db.DB_PATH):
    return _obtener_ranking_mensual_cached(
        anio,
        mes,
        "operador",
        "operador",
        str(Path(db_path).resolve()),
        _db_mtime(db_path),
    )


@st.cache_data(show_spinner=False)
def _obtener_ranking_mensual_cached(anio, mes, clave_columna, nombre_salida, db_path_text, mtime):
    db_path = Path(db_path_text)
    return _obtener_ranking_mensual(anio, mes, clave_columna, nombre_salida, db_path=db_path)


def _obtener_dataframe_mensual(anio, mes, db_path=db.DB_PATH):
    fecha_inicio, fecha_fin = _rango_mes(anio, mes)
    df = db.leer_registros(db_path=db_path)
    if df.empty:
        return pd.DataFrame(), {}

    columnas = _mapear_columnas(df.columns)
    columna_fecha = columnas.get("fecha")
    if not columna_fecha:
        return pd.DataFrame(), columnas

    fechas = pd.to_datetime(df[columna_fecha], errors="coerce").dt.date
    mascara = fechas.between(fecha_inicio, fecha_fin)
    return df[mascara].copy(), columnas


def _obtener_ranking_mensual(anio, mes, clave_columna, nombre_salida, db_path=db.DB_PATH):
    mensual, columnas = _obtener_dataframe_mensual(anio, mes, db_path=db_path)
    columnas_salida = [
        nombre_salida,
        "metros_totales",
        "horas_efectivas_totales",
        "horas_no_efectivas_totales",
        "horas_averias_totales",
        "disponibilidad_promedio",
        "utilizacion_promedio",
        "rendimiento_promedio",
        "cantidad_registros",
    ]
    columna_grupo = columnas.get(clave_columna)
    if mensual.empty or not columna_grupo:
        return pd.DataFrame(columns=columnas_salida)

    trabajo = mensual.copy()
    trabajo["_grupo_ranking"] = trabajo[columna_grupo].fillna("").astype(str).str.strip()
    trabajo = trabajo[trabajo["_grupo_ranking"].ne("") & trabajo["_grupo_ranking"].str.lower().ne("nan")]
    if trabajo.empty:
        return pd.DataFrame(columns=columnas_salida)

    filas = []
    for grupo, df_grupo in trabajo.groupby("_grupo_ranking", dropna=False):
        metros = _serie_numerica(df_grupo, columnas.get("metros"))
        horas_efectivas = _serie_numerica(df_grupo, columnas.get("horas_efectivas"))
        filas.append(
            {
                nombre_salida: grupo,
                "metros_totales": _redondear(metros.sum()),
                "horas_efectivas_totales": _redondear(horas_efectivas.sum()),
                "horas_no_efectivas_totales": _redondear(_serie_numerica(df_grupo, columnas.get("horas_no_efectivas")).sum()),
                "horas_averias_totales": _redondear(_serie_numerica(df_grupo, columnas.get("horas_averias")).sum()),
                "disponibilidad_promedio": _redondear(_serie_numerica(df_grupo, columnas.get("disponibilidad")).mean()),
                "utilizacion_promedio": _redondear(_serie_numerica(df_grupo, columnas.get("utilizacion")).mean()),
                "rendimiento_promedio": _redondear(_calcular_rendimiento(df_grupo, columnas, metros, horas_efectivas)),
                "cantidad_registros": int(len(df_grupo)),
            }
        )

    ranking = pd.DataFrame(filas, columns=columnas_salida)
    return ranking.sort_values("metros_totales", ascending=False, kind="mergesort").reset_index(drop=True)


def _rango_mes(anio, mes):
    anio = int(anio)
    mes = int(mes)
    ultimo_dia = monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, ultimo_dia)


def _resultado_vacio(anio, mes, fecha_inicio, fecha_fin):
    resultado = RESULTADO_BASE.copy()
    resultado.update(
        {
            "anio": int(anio),
            "mes": int(mes),
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
        }
    )
    return resultado


def _mapear_columnas(columnas):
    normalizadas = {_normalizar_columna(columna): columna for columna in columnas}
    mapeo = {}
    for clave, candidatos in COLUMNAS.items():
        for candidato in candidatos:
            columna = normalizadas.get(_normalizar_columna(candidato))
            if columna:
                mapeo[clave] = columna
                break
    return mapeo


def _normalizar_columna(valor):
    texto = str(valor or "").strip()
    for origen, destino in MOJIBAKE_REEMPLAZOS.items():
        texto = texto.replace(origen, destino)
    texto = normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", texto.lower())


def _serie_numerica(df, columna):
    if not columna or columna not in df.columns:
        return pd.Series([0.0] * len(df), index=df.index, dtype=float)
    return pd.to_numeric(df[columna], errors="coerce").fillna(0.0)


def _calcular_rendimiento(df, columnas, metros, horas_efectivas):
    return kpi_service.calcular_rendimiento_productivo(df)


def _contar_distintos(df, columna):
    if not columna or columna not in df.columns:
        return 0
    valores = df[columna].dropna().astype(str).str.strip()
    valores = valores[valores.ne("") & valores.str.lower().ne("nan")]
    return int(valores.nunique())


def _redondear(valor):
    if pd.isna(valor):
        return 0.0
    return round(float(valor), 2)
