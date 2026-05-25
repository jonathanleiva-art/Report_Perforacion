"""Validation helpers for the drilling report project."""

import pandas as pd

from utils import HORAS_TURNO, limpiar_entero


def validar_total_horas_turno(total_horas, horas_turno=HORAS_TURNO):
    return total_horas == horas_turno


def validar_operador_obligatorio(operador):
    return bool(operador)


def existe_reporte_duplicado(df, fecha_turno, turno, modelo_equipo, numero_equipo, operador):
    columnas = {"Fecha turno", "Turno", "Modelo equipo", "Número equipo", "Operador"}
    if df.empty or not columnas.issubset(df.columns):
        return False

    fechas = pd.to_datetime(df["Fecha turno"], errors="coerce").dt.date
    return bool(
        (
            fechas.eq(fecha_turno)
            & df["Turno"].astype(str).str.strip().eq(str(turno).strip())
            & df["Modelo equipo"].astype(str).str.strip().eq(str(modelo_equipo).strip())
            & df["Número equipo"].astype(str).apply(limpiar_entero).eq(limpiar_entero(numero_equipo))
            & df["Operador"].astype(str).str.strip().eq(str(operador).strip())
        ).any()
    )
