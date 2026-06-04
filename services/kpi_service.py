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


def _serie_numerica_estable(df, *columnas):
    if df is None:
        return pd.Series(dtype=float)
    columna = buscar_columna(df, *columnas)
    if not columna:
        return pd.Series([0.0] * len(df), index=df.index, dtype=float)
    return pd.to_numeric(df[columna], errors="coerce").fillna(0.0)


def _normalizar_group_cols(group_cols):
    if group_cols is None:
        return []
    if isinstance(group_cols, str):
        return [group_cols]
    return list(group_cols)


def _resolver_group_cols(df, group_cols):
    columnas = []
    for columna in _normalizar_group_cols(group_cols):
        real = buscar_columna(df, columna)
        if not real:
            return []
        columnas.append(real)
    return columnas


def _columnas_resultado_rendimiento(group_cols=None):
    return _normalizar_group_cols(group_cols) + [
        "Metros perforados",
        "Horas efectivas perforando",
        "Rendimiento m/h",
        "Registros productivos",
    ]


def obtener_series_productivas(df):
    if df is None:
        df = pd.DataFrame()
    metros = _serie_numerica_estable(df, *columnas_equivalentes("metros_perforados"))
    horas = _serie_numerica_estable(df, *columnas_equivalentes("horas_efectivas"))
    productivos = (metros > 0) & (horas > 0)
    return {
        "metros": metros,
        "horas_efectivas": horas,
        "productivos": productivos,
    }


def obtener_registros_productivos(df):
    if df is None:
        return pd.DataFrame()
    series = obtener_series_productivas(df)
    return df.loc[series["productivos"]].copy()


def calcular_totales_productivos(df):
    series = obtener_series_productivas(df)
    metros = series["metros"]
    horas = series["horas_efectivas"]
    productivos = series["productivos"]
    total_metros = float(metros[productivos].sum())
    total_horas = float(horas[productivos].sum())
    return {
        "metros_productivos": round(total_metros, 2),
        "horas_efectivas_productivas": round(total_horas, 2),
        "registros_productivos": int(productivos.sum()),
        "rendimiento_m_h": round(total_metros / total_horas, 2) if total_horas > 0 else 0.0,
    }


def calcular_rendimiento_productivo(df, group_cols=None):
    if df is None:
        df = pd.DataFrame()
    columnas_grupo = _resolver_group_cols(df, group_cols)
    columnas_salida = _columnas_resultado_rendimiento(group_cols)
    if group_cols and not columnas_grupo:
        return pd.DataFrame(columns=columnas_salida)

    base = obtener_registros_productivos(df)
    if base.empty:
        if group_cols:
            return pd.DataFrame(columns=columnas_salida)
        return 0.0

    series = obtener_series_productivas(base)
    base = base.copy()
    base["_kpi_metros_productivos"] = series["metros"]
    base["_kpi_horas_productivas"] = series["horas_efectivas"]

    if not group_cols:
        total_horas = float(base["_kpi_horas_productivas"].sum())
        if total_horas <= 0:
            return 0.0
        return float(base["_kpi_metros_productivos"].sum() / total_horas)

    resultado = base.groupby(columnas_grupo, as_index=False, dropna=False).agg(
        _kpi_metros_productivos=("_kpi_metros_productivos", "sum"),
        _kpi_horas_productivas=("_kpi_horas_productivas", "sum"),
        _kpi_registros_productivos=("_kpi_metros_productivos", "size"),
    )
    rename_grupos = {
        real: solicitado
        for real, solicitado in zip(columnas_grupo, _normalizar_group_cols(group_cols))
    }
    resultado = resultado.rename(columns=rename_grupos)
    resultado["Rendimiento m/h"] = resultado.apply(
        lambda fila: fila["_kpi_metros_productivos"] / fila["_kpi_horas_productivas"]
        if fila["_kpi_horas_productivas"] > 0 else 0.0,
        axis=1,
    )
    resultado = resultado.rename(columns={
        "_kpi_metros_productivos": "Metros perforados",
        "_kpi_horas_productivas": "Horas efectivas perforando",
        "_kpi_registros_productivos": "Registros productivos",
    })
    for columna in ["Metros perforados", "Horas efectivas perforando", "Rendimiento m/h"]:
        resultado[columna] = resultado[columna].round(2)
    return resultado[columnas_salida]


def calcular_resumen_productivo_por_equipo(df):
    columnas_salida = [
        "Modelo equipo",
        "N\u00famero equipo",
        "Equipo",
        "Metros perforados",
        "Horas efectivas perforando",
        "Rendimiento m/h",
        "Registros productivos",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=columnas_salida)

    base = obtener_registros_productivos(df)
    if base.empty:
        return pd.DataFrame(columns=columnas_salida)

    modelo_col = buscar_columna(base, *columnas_equivalentes("modelo_equipo"), "Modelo equipo")
    numero_col = buscar_columna(base, *columnas_equivalentes("numero_equipo"), "N\u00famero equipo", "N\u00c3\u00bamero equipo", "Número equipo")
    equipo_col = buscar_columna(base, "Equipo")
    trabajo = base.copy()
    if modelo_col:
        trabajo["_kpi_modelo_equipo"] = trabajo[modelo_col].fillna("").astype(str).str.strip()
    else:
        trabajo["_kpi_modelo_equipo"] = ""
    if numero_col:
        trabajo["_kpi_numero_equipo"] = trabajo[numero_col].fillna("").astype(str).apply(limpiar_entero)
    else:
        trabajo["_kpi_numero_equipo"] = ""
    if equipo_col:
        trabajo["_kpi_equipo"] = trabajo[equipo_col].fillna("").astype(str).str.strip()
    else:
        trabajo["_kpi_equipo"] = (
            trabajo["_kpi_modelo_equipo"] + " " + trabajo["_kpi_numero_equipo"]
        ).str.strip()

    resumen = calcular_rendimiento_productivo(
        trabajo,
        ["_kpi_modelo_equipo", "_kpi_numero_equipo", "_kpi_equipo"],
    )
    if resumen.empty:
        return pd.DataFrame(columns=columnas_salida)
    resumen = resumen.rename(columns={
        "_kpi_modelo_equipo": "Modelo equipo",
        "_kpi_numero_equipo": "N\u00famero equipo",
        "_kpi_equipo": "Equipo",
    })
    return resumen[columnas_salida]


def calcular_resumen_productivo_por_operador(df):
    columnas_salida = [
        "Operador",
        "Metros perforados",
        "Horas efectivas perforando",
        "Rendimiento m/h",
        "Registros productivos",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=columnas_salida)

    operador_col = buscar_columna(df, *columnas_equivalentes("operador"), "Operador")
    if not operador_col:
        return pd.DataFrame(columns=columnas_salida)

    resumen = calcular_rendimiento_productivo(df, [operador_col])
    if resumen.empty:
        return pd.DataFrame(columns=columnas_salida)
    resumen = resumen.rename(columns={operador_col: "Operador"})
    return resumen[columnas_salida]


def _serie_numerica_trazabilidad(df, *columnas):
    columna = buscar_columna(df, *columnas)
    if not columna:
        return pd.Series([0.0] * len(df), index=df.index, dtype=float), pd.Series([False] * len(df), index=df.index)

    serie_texto = df[columna]
    serie_numerica = pd.to_numeric(serie_texto, errors="coerce")
    invalidos = serie_numerica.isna() & serie_texto.notna() & serie_texto.astype(str).str.strip().ne("")
    return serie_numerica.fillna(0.0), invalidos


def _valor_detalle_trazabilidad(df, indice, *columnas):
    columna = buscar_columna(df, *columnas)
    if not columna:
        return ""
    valor = df.at[indice, columna]
    if pd.isna(valor):
        return ""
    return valor


def _motivo_exclusion_trazabilidad(metros, horas, metros_invalido=False, horas_invalida=False):
    if metros_invalido or horas_invalida:
        return "Datos inválidos"
    if metros < 0 or horas < 0:
        return "Datos negativos"
    if metros > 0 and horas <= 0:
        return "Metros > 0 sin horas"
    if horas > 0 and metros <= 0:
        return "Horas > 0 sin metros"
    if metros <= 0 and horas <= 0:
        return "Sin metros y sin horas"
    return ""


def _redondear_trazabilidad(valor):
    redondeado = round(float(valor), 2)
    return 0.0 if abs(redondeado) == 0 else redondeado


def _valor_texto_trazabilidad(df, indice, *columnas):
    valor = _valor_detalle_trazabilidad(df, indice, *columnas)
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def _equipo_trazabilidad(df, indice):
    equipo = _valor_texto_trazabilidad(df, indice, "Equipo")
    if equipo:
        return equipo
    modelo = _valor_texto_trazabilidad(df, indice, *columnas_equivalentes("modelo_equipo"))
    numero = _valor_texto_trazabilidad(df, indice, *columnas_equivalentes("numero_equipo"))
    return f"{modelo} {numero}".strip()


def _detalle_operacional_trazabilidad(df, indice):
    return {
        "Fecha turno": _valor_detalle_trazabilidad(df, indice, *columnas_equivalentes("fecha_turno")),
        "Turno": _valor_detalle_trazabilidad(df, indice, *columnas_equivalentes("turno")),
        "Equipo": _equipo_trazabilidad(df, indice),
        "Operador": _valor_detalle_trazabilidad(df, indice, *columnas_equivalentes("operador")),
        "Tipo de perforación": _valor_detalle_trazabilidad(df, indice, "Tipo de perforacion", "Tipo de perforación", "Tipo de perforaci\u00f3n"),
        "Tipo detención": _valor_detalle_trazabilidad(df, indice, "Tipo detencion", "Tipo detención", "Tipo detenci\u00f3n"),
    }


def _serie_llave_trazabilidad(df):
    if df is None or df.empty:
        return pd.Series(dtype=str)

    partes = []
    for indice in df.index:
        detalle = _detalle_operacional_trazabilidad(df, indice)
        partes.append(
            "|".join(
                normalizar_nombre_columna(detalle.get(columna, ""))
                for columna in ["Fecha turno", "Turno", "Equipo", "Operador"]
            )
        )
    llave_base = pd.Series(partes, index=df.index, dtype=str)
    ocurrencia = llave_base.groupby(llave_base).cumcount().astype(str)
    return llave_base + "|" + ocurrencia


def _normalizar_lista_texto(valor):
    if valor is None:
        return []
    if isinstance(valor, (list, tuple, set, pd.Index, pd.Series)):
        valores = valor
    else:
        valores = [valor]
    return [str(item).strip() for item in valores if str(item).strip()]


def _valor_en_filtro(valor, seleccion):
    seleccion_normalizada = {normalizar_nombre_columna(item) for item in _normalizar_lista_texto(seleccion)}
    if not seleccion_normalizada:
        return True
    return normalizar_nombre_columna(valor) in seleccion_normalizada


def _tipo_en_filtro(tipo, seleccion):
    seleccion_normalizada = {normalizar_nombre_columna(item) for item in _normalizar_lista_texto(seleccion)}
    if not seleccion_normalizada:
        return True
    partes = {
        normalizar_nombre_columna(parte)
        for parte in str(tipo).split(",")
        if str(parte).strip()
    }
    return bool(partes.intersection(seleccion_normalizada)) or normalizar_nombre_columna(tipo) in seleccion_normalizada


def _causa_registro_ausente(detalle, filtros=None):
    filtros = filtros or {}
    causas = []
    if not _valor_en_filtro(detalle.get("Turno", ""), filtros.get("turnos") or filtros.get("turno")):
        causas.append("Filtro turno")
    if not _valor_en_filtro(detalle.get("Equipo", ""), filtros.get("equipos") or filtros.get("equipo")):
        causas.append("Filtro equipo")
    if not _valor_en_filtro(detalle.get("Operador", ""), filtros.get("operadores") or filtros.get("operador")):
        causas.append("Filtro operador")
    if not _tipo_en_filtro(detalle.get("Tipo de perforación", ""), filtros.get("tipo_perforacion")):
        causas.append("Filtro tipo perforación")

    fecha = pd.to_datetime(detalle.get("Fecha turno"), errors="coerce")
    fecha_inicio = filtros.get("fecha_inicio") or filtros.get("fecha_desde")
    fecha_fin = filtros.get("fecha_fin") or filtros.get("fecha_hasta")
    if pd.notna(fecha) and fecha_inicio is not None:
        if fecha.date() < pd.to_datetime(fecha_inicio, errors="coerce").date():
            causas.append("Filtro fecha inicio")
    if pd.notna(fecha) and fecha_fin is not None:
        if fecha.date() > pd.to_datetime(fecha_fin, errors="coerce").date():
            causas.append("Filtro fecha fin")

    return ", ".join(causas) if causas else "Ausente en df_analisis"


def trazabilidad_kpis_productivos(df):
    columnas_detalle = [
        "Fecha turno",
        "Turno",
        "Equipo",
        "Operador",
        "Tipo de perforación",
        "Tipo detención",
        "Metros perforados",
        "Horas efectivas perforando",
        "Motivo exclusión",
    ]
    if df is None or df.empty:
        return {
            "metros_totales": 0.0,
            "metros_productivos": 0.0,
            "metros_excluidos": 0.0,
            "horas_efectivas_totales": 0.0,
            "horas_efectivas_productivas": 0.0,
            "horas_excluidas": 0.0,
            "registros_totales": 0,
            "registros_productivos": 0,
            "registros_excluidos": 0,
            "detalle_registros_excluidos": pd.DataFrame(columns=columnas_detalle),
        }

    base = df.copy()
    metros, metros_invalidos = _serie_numerica_trazabilidad(base, *columnas_equivalentes("metros_perforados"))
    horas, horas_invalidas = _serie_numerica_trazabilidad(base, *columnas_equivalentes("horas_efectivas"))
    productivos = (metros > 0) & (horas > 0)
    excluidos = ~productivos

    detalle = []
    for indice in base.index[excluidos]:
        detalle_operacional = _detalle_operacional_trazabilidad(base, indice)
        detalle.append({
            **detalle_operacional,
            "Metros perforados": float(metros.loc[indice]),
            "Horas efectivas perforando": float(horas.loc[indice]),
            "Motivo exclusión": _motivo_exclusion_trazabilidad(
                float(metros.loc[indice]),
                float(horas.loc[indice]),
                bool(metros_invalidos.loc[indice]),
                bool(horas_invalidas.loc[indice]),
            ),
        })

    metros_totales = float(metros.sum())
    metros_productivos = float(metros[productivos].sum())
    horas_totales = float(horas.sum())
    horas_productivas = float(horas[productivos].sum())

    return {
        "metros_totales": _redondear_trazabilidad(metros_totales),
        "metros_productivos": _redondear_trazabilidad(metros_productivos),
        "metros_excluidos": _redondear_trazabilidad(metros_totales - metros_productivos),
        "horas_efectivas_totales": _redondear_trazabilidad(horas_totales),
        "horas_efectivas_productivas": _redondear_trazabilidad(horas_productivas),
        "horas_excluidas": _redondear_trazabilidad(horas_totales - horas_productivas),
        "registros_totales": int(len(base)),
        "registros_productivos": int(productivos.sum()),
        "registros_excluidos": int(excluidos.sum()),
        "detalle_registros_excluidos": pd.DataFrame(detalle, columns=columnas_detalle),
    }


def comparar_base_vs_analisis_kpis(df_base, df_analisis, filtros=None):
    columnas_detalle = [
        "id",
        "Fecha turno",
        "Turno",
        "Equipo",
        "Operador",
        "Tipo de perforación",
        "Tipo detención",
        "Metros perforados",
        "Horas efectivas perforando",
        "Posible causa",
    ]
    if df_base is None or df_base.empty:
        return {
            "registros_base": 0,
            "registros_analisis": 0 if df_analisis is None else int(len(df_analisis)),
            "registros_ausentes": 0,
            "metros_ausentes": 0.0,
            "horas_ausentes": 0.0,
            "detalle_registros_ausentes": pd.DataFrame(columns=columnas_detalle),
        }

    base = df_base.copy()
    analisis = df_analisis.copy() if df_analisis is not None else pd.DataFrame()
    llave_base = _serie_llave_trazabilidad(base)
    llaves_analisis = set(_serie_llave_trazabilidad(analisis).tolist())
    mascara_ausentes = ~llave_base.isin(llaves_analisis)

    metros, _ = _serie_numerica_trazabilidad(base, *columnas_equivalentes("metros_perforados"))
    horas, _ = _serie_numerica_trazabilidad(base, *columnas_equivalentes("horas_efectivas"))

    detalle = []
    for indice in base.index[mascara_ausentes]:
        detalle_operacional = _detalle_operacional_trazabilidad(base, indice)
        detalle.append({
            "id": _valor_detalle_trazabilidad(base, indice, "id"),
            **detalle_operacional,
            "Metros perforados": float(metros.loc[indice]),
            "Horas efectivas perforando": float(horas.loc[indice]),
            "Posible causa": _causa_registro_ausente(detalle_operacional, filtros=filtros),
        })

    return {
        "registros_base": int(len(base)),
        "registros_analisis": int(len(analisis)),
        "registros_ausentes": int(mascara_ausentes.sum()),
        "metros_ausentes": _redondear_trazabilidad(metros[mascara_ausentes].sum()),
        "horas_ausentes": _redondear_trazabilidad(horas[mascara_ausentes].sum()),
        "detalle_registros_ausentes": pd.DataFrame(detalle, columns=columnas_detalle),
    }


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
        "Utilización",
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
        utilizacion = calcular_utilizacion(
            horas_efectivas,
            horas_turno=horas_programadas,
            horas_averia=horas_averia,
            horas_mantencion=horas_mantencion,
        )
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
            "Utilización": round(utilizacion, 2),
            "Horas efectivas perforando": round(horas_efectivas, 2),
            "Horas no efectivas": round(horas_no_efectivas, 2),
            "Horas avería equipo": round(horas_averia, 2),
            "Mantención Programada": round(horas_mantencion, 2),
            "Estado operacional": estado,
            "Marcación": marcacion,
        })

    return pd.DataFrame(filas, columns=columnas)
