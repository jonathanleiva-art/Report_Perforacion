from unicodedata import normalize

import pandas as pd

from metrics import (
    calcular_disponibilidad,
    calcular_rendimiento_consolidado,
    calcular_utilizacion,
)
from schema import columnas_equivalentes
from utils import EQUIPOS, HORAS_TURNO, limpiar_entero


def normalizar_nombre_columna(nombre):
    texto = normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode("ascii")
    return texto.lower().strip()


def buscar_columna(df, *candidatos):
    columnas_normalizadas = {normalizar_nombre_columna(col): col for col in df.columns}
    for candidato in candidatos:
        columna = columnas_normalizadas.get(normalizar_nombre_columna(candidato))
        if columna:
            return columna

    return None


def serie_numerica(df, *columnas):
    columna = buscar_columna(df, *columnas)
    if not columna:
        return pd.Series(dtype=float)

    return pd.to_numeric(df[columna], errors="coerce").fillna(0)


def totales_productivos(df):
    metros = serie_numerica(df, *columnas_equivalentes("metros_perforados"))
    horas = serie_numerica(df, *columnas_equivalentes("horas_efectivas"))
    productivos = (metros > 0) & (horas > 0)
    total_metros = metros[productivos].sum()
    total_horas = horas[productivos].sum()
    rendimiento = total_metros / total_horas if total_horas > 0 else 0

    return total_metros, total_horas, rendimiento


def equipos_esperados():
    return [(modelo, numero) for modelo, numeros in EQUIPOS.items() for numero in numeros]


def estado_operacional_equipo(
    metros,
    pozos,
    horas_efectivas,
    horas_no_efectivas,
    horas_averia,
    horas_mantencion,
    horas_standby=0,
):
    tiene_produccion = (metros > 0) or (pozos > 0) or (horas_efectivas > 0)
    if horas_mantencion >= HORAS_TURNO and horas_efectivas == 0:
        return "Mantención Programada", "Fuera de servicio programado"
    if horas_averia >= HORAS_TURNO and horas_efectivas == 0:
        return "Avería", "Fuera de servicio por avería"
    if horas_efectivas > 0 and (horas_averia > 0 or horas_no_efectivas > 0):
        return "Operativo parcial", "Con marcación"
    if horas_efectivas > 0:
        return "Operativo", "Con marcación"
    if horas_standby > 0:
        return "Operativo", "Standby por falta de tajo/Patio"
    if not tiene_produccion:
        return "Sin marcación", "Sin marcación"
    return "Sin marcación", "Sin marcación"


def resumen_operacional_equipos(df):
    columnas = [
        "Modelo equipo",
        "Número equipo",
        "Equipo",
        "Operador",
        "Metros perforados",
        "Pozos perforados",
        "Rendimiento consolidado m/h",
        "Disponibilidad %",
        "Utilización %",
        "Horas efectivas perforando",
        "Horas no efectivas",
        "Horas avería equipo",
        "Mantención Programada",
        "Estado operacional",
        "Marcación",
    ]
    filas = []
    base = df.copy() if not df.empty else pd.DataFrame()
    numero_equipo_col = buscar_columna(base, *columnas_equivalentes("numero_equipo"))
    modelo_equipo_col = buscar_columna(base, *columnas_equivalentes("modelo_equipo"))
    if not base.empty and numero_equipo_col:
        base[numero_equipo_col] = base[numero_equipo_col].astype(str).apply(limpiar_entero)

    for modelo, numero in equipos_esperados():
        if not base.empty and modelo_equipo_col and numero_equipo_col:
            grupo = base[
                base[modelo_equipo_col].astype(str).str.strip().eq(str(modelo).strip())
                & base[numero_equipo_col].astype(str).apply(limpiar_entero).eq(limpiar_entero(numero))
            ].copy()
        else:
            grupo = pd.DataFrame()

        operador = ", ".join(dict.fromkeys(grupo.get("Operador", pd.Series(dtype=str)).dropna().astype(str)))
        metros = serie_numerica(grupo, *columnas_equivalentes("metros_perforados")).sum()
        pozos = serie_numerica(grupo, *columnas_equivalentes("pozos_perforados")).sum()
        horas_efectivas = serie_numerica(grupo, *columnas_equivalentes("horas_efectivas")).sum()
        horas_no_efectivas = serie_numerica(grupo, *columnas_equivalentes("horas_no_efectivas")).sum()
        horas_averia = serie_numerica(grupo, *columnas_equivalentes("horas_averia")).sum()
        horas_mantencion = serie_numerica(grupo, *columnas_equivalentes("horas_mantencion")).sum()
        horas_standby = serie_numerica(grupo, *columnas_equivalentes("horas_standby")).sum()
        horas_sin_marcacion = serie_numerica(grupo, *columnas_equivalentes("sin_marcacion")).sum()
        horas_programadas = HORAS_TURNO * max(len(grupo), 1)
        disponibilidad = calcular_disponibilidad(
            horas_averia,
            horas_turno=horas_programadas,
            horas_mantencion=horas_mantencion,
            horas_standby=horas_standby,
            horas_sin_marcacion=horas_sin_marcacion,
        )
        utilizacion = calcular_utilizacion(horas_efectivas, horas_turno=horas_programadas)
        rendimiento = metros / horas_efectivas if horas_efectivas > 0 else 0
        estado, marcacion = estado_operacional_equipo(
            metros,
            pozos,
            horas_efectivas,
            horas_no_efectivas,
            horas_averia,
            horas_mantencion,
            horas_standby,
        )
        filas.append({
            "Modelo equipo": modelo,
            "Número equipo": limpiar_entero(numero),
            "Equipo": f"{modelo} {limpiar_entero(numero)}",
            "Operador": operador,
            "Metros perforados": round(metros, 2),
            "Pozos perforados": round(pozos, 0),
            "Rendimiento consolidado m/h": round(rendimiento, 2),
            "Disponibilidad %": round(disponibilidad, 2),
            "Utilización %": round(utilizacion, 2),
            "Horas efectivas perforando": round(horas_efectivas, 2),
            "Horas no efectivas": round(horas_no_efectivas, 2),
            "Horas avería equipo": round(horas_averia, 2),
            "Mantención Programada": round(horas_mantencion, 2),
            "Estado operacional": estado,
            "Marcación": marcacion,
        })

    return pd.DataFrame(filas, columns=columnas)
