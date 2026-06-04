from pathlib import Path
import re
from unicodedata import normalize

import pandas as pd


TIPO_CICLOS = "ciclos_perforacion"
TIPO_REGISTRO_OPERACIONAL = "registro_operacional_excel"
TIPO_DESCONOCIDO = "desconocido"


COLUMNAS_CICLOS = {
    "ident_registro": {"ident_registro_ciclo_perforacion", "ident_de_registro_de_ciclo_de_perforacion"},
    "pozo": {"pozo", "pozo_perforacion"},
    "banco": {"banco"},
    "profundidad": {"profundidad", "profundidad_pozo_mtr", "profundidad_de_pozo_mtr", "metros", "mtr"},
    "norte": {"norte", "coordenada_norte", "norte_m"},
    "este": {"este", "coordenada_este", "este_m"},
    "operador": {"operador", "operador_unidad_perforacion", "operador_de_unidad_de_perforacion"},
    "equipo": {"equipo", "unidad_perforacion", "unidad_de_perforacion", "numero_equipo"},
    "fecha": {"fecha_turno_perforacion", "fecha_de_turno_de_perforacion", "fecha_turno"},
}


COLUMNAS_REGISTRO_OPERACIONAL = {
    "fecha": {"fecha", "fecha_turno", "dia", "ano", "anio", "mes"},
    "turno": {"turno"},
    "equipo": {"equipo", "numero_equipo", "n_equipo", "no_equipo"},
    "operador": {"operador"},
    "metros": {"total_metros", "metros", "produccion"},
    "horas_efectivas": {"horas_efectivas", "horas_efectivas_perforando"},
    "horas_averia": {"horas_averia", "averia", "horas_detencion_mecanica"},
    "horas_mp": {"horas_mp", "mantencion_programada", "mantencion"},
    "disponibilidad": {"disponibilidad", "disponibilidad_porcentaje"},
    "utilizacion": {"utilizacion", "utilizacion_porcentaje"},
    "rendimiento": {"rendimiento_m_h", "m_h", "rendimiento"},
}


SINONIMOS_NORMALIZACION = {
    "n_equipo": "numero_equipo",
    "no_equipo": "numero_equipo",
    "num_equipo": "numero_equipo",
    "numero_de_equipo": "numero_equipo",
    "equipo": "equipo",
    "n_pozos": "numero_pozos",
    "no_pozos": "numero_pozos",
    "n_bit_tricono": "numero_bit_tricono",
    "no_bit_tricono": "numero_bit_tricono",
    "ano": "anio",
    "m_h": "rendimiento_m_h",
    "total_metros": "total_metros",
}


def normalizar_nombre_columna(nombre):
    texto = normalize("NFKD", str(nombre or "")).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().replace("\n", " ")
    texto = re.sub(r"[^a-z0-9]+", "_", texto).strip("_")
    texto = re.sub(r"_+", "_", texto)
    return SINONIMOS_NORMALIZACION.get(texto, texto)


def _normalizar_columnas(columnas):
    return [normalizar_nombre_columna(columna) for columna in columnas if str(columna).strip()]


def _campos_reconocidos(columnas_normalizadas, definicion):
    columnas_set = set(columnas_normalizadas)
    reconocidos = {}
    for campo, candidatos in definicion.items():
        encontrados = sorted(columnas_set.intersection(candidatos))
        if encontrados:
            reconocidos[campo] = encontrados
    return reconocidos


def detectar_tipo_fuente(columnas):
    columnas_normalizadas = _normalizar_columnas(columnas)
    ciclos = _campos_reconocidos(columnas_normalizadas, COLUMNAS_CICLOS)
    registro = _campos_reconocidos(columnas_normalizadas, COLUMNAS_REGISTRO_OPERACIONAL)

    puntaje_ciclos = len(ciclos)
    puntaje_registro = len(registro)
    if {"pozo", "profundidad", "operador", "equipo"}.issubset(ciclos) or puntaje_ciclos >= 6:
        return TIPO_CICLOS
    if {"turno", "equipo", "operador", "metros"}.issubset(registro) and puntaje_registro >= 5:
        return TIPO_REGISTRO_OPERACIONAL
    if puntaje_registro >= 6:
        return TIPO_REGISTRO_OPERACIONAL
    return TIPO_DESCONOCIDO


def _detectar_fila_encabezado(excel_path, hoja):
    bruto = pd.read_excel(excel_path, sheet_name=hoja, header=None, nrows=80)
    mejor_idx = 0
    mejor_puntaje = -1
    for idx, fila in bruto.iterrows():
        columnas = _normalizar_columnas(fila.tolist())
        tipo = detectar_tipo_fuente(columnas)
        reconocidos = _columnas_reconocidas_por_tipo(columnas, tipo)
        puntaje = len(reconocidos)
        if puntaje > mejor_puntaje:
            mejor_idx = int(idx)
            mejor_puntaje = puntaje
    return mejor_idx


def _leer_hoja_principal(excel_path, hojas):
    mejor = {
        "hoja": hojas[0] if hojas else None,
        "header": 0,
        "puntaje": -1,
        "tipo": TIPO_DESCONOCIDO,
        "columnas": [],
    }
    for hoja in hojas:
        header_idx = _detectar_fila_encabezado(excel_path, hoja)
        columnas = list(pd.read_excel(excel_path, sheet_name=hoja, header=header_idx, nrows=0).columns)
        columnas = [col for col in columnas if not str(col).startswith("Unnamed")]
        tipo = detectar_tipo_fuente(columnas)
        reconocidas = _columnas_reconocidas_por_tipo(_normalizar_columnas(columnas), tipo)
        puntaje = len(reconocidas)
        if puntaje > mejor["puntaje"]:
            mejor = {
                "hoja": hoja,
                "header": header_idx,
                "puntaje": puntaje,
                "tipo": tipo,
                "columnas": columnas,
            }
    df = pd.read_excel(excel_path, sheet_name=mejor["hoja"], header=mejor["header"])
    df = df.dropna(how="all")
    df = df[[col for col in df.columns if not str(col).startswith("Unnamed")]].copy()
    return mejor["hoja"], df


def _columnas_reconocidas_por_tipo(columnas_normalizadas, tipo):
    if tipo == TIPO_CICLOS:
        definicion = COLUMNAS_CICLOS
    elif tipo == TIPO_REGISTRO_OPERACIONAL:
        definicion = COLUMNAS_REGISTRO_OPERACIONAL
    else:
        definicion = {**COLUMNAS_CICLOS, **COLUMNAS_REGISTRO_OPERACIONAL}
    reconocidos = _campos_reconocidos(columnas_normalizadas, definicion)
    return sorted({columna for valores in reconocidos.values() for columna in valores})


def _columnas_faltantes_por_tipo(columnas_normalizadas, tipo):
    if tipo == TIPO_CICLOS:
        requeridas = {"pozo", "profundidad", "operador", "equipo"}
        reconocidos = _campos_reconocidos(columnas_normalizadas, COLUMNAS_CICLOS)
    elif tipo == TIPO_REGISTRO_OPERACIONAL:
        requeridas = {"turno", "equipo", "operador", "metros", "horas_efectivas"}
        reconocidos = _campos_reconocidos(columnas_normalizadas, COLUMNAS_REGISTRO_OPERACIONAL)
    else:
        return []
    return sorted(requeridas.difference(reconocidos))


def _buscar_columna(df, candidatos):
    normalizadas = {normalizar_nombre_columna(columna): columna for columna in df.columns}
    for candidato in candidatos:
        if candidato in normalizadas:
            return normalizadas[candidato]
    return None


def _texto_valor(valor):
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _serie_fechas(df, tipo):
    if tipo == TIPO_CICLOS:
        columna = _buscar_columna(df, COLUMNAS_CICLOS["fecha"])
        return pd.to_datetime(df[columna], errors="coerce") if columna else pd.Series(dtype="datetime64[ns]")

    columna_fecha = _buscar_columna(df, {"fecha", "fecha_turno"})
    if columna_fecha:
        return pd.to_datetime(df[columna_fecha], errors="coerce")

    col_anio = _buscar_columna(df, {"anio"})
    col_mes = _buscar_columna(df, {"mes"})
    col_dia = _buscar_columna(df, {"dia"})
    if not all([col_anio, col_mes, col_dia]):
        return pd.Series(dtype="datetime64[ns]")
    fechas = []
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
        "noviembre": 11, "diciembre": 12,
    }
    for _, fila in df[[col_anio, col_mes, col_dia]].iterrows():
        dia_fecha = pd.to_datetime(fila[col_dia], errors="coerce")
        if pd.notna(dia_fecha) and int(dia_fecha.year) > 2000:
            fechas.append(dia_fecha)
            continue
        anio = pd.to_numeric(fila[col_anio], errors="coerce")
        dia = pd.to_numeric(fila[col_dia], errors="coerce")
        mes_valor = fila[col_mes]
        mes_num = pd.to_numeric(mes_valor, errors="coerce")
        if pd.isna(mes_num):
            mes_num = meses.get(normalize("NFKD", str(mes_valor)).encode("ascii", "ignore").decode("ascii").lower())
        if pd.isna(anio) or pd.isna(dia) or not mes_num:
            fechas.append(pd.NaT)
            continue
        fechas.append(pd.to_datetime(f"{int(anio):04d}-{int(mes_num):02d}-{int(dia):02d}", errors="coerce"))
    return pd.Series(fechas)


def _valores_unicos(df, candidatos):
    columna = _buscar_columna(df, candidatos)
    if not columna:
        return []
    serie = df[columna].dropna().map(_texto_valor).astype(str).str.strip()
    return sorted(serie[serie.ne("")].unique().tolist())


def _metros_estimados(df, tipo):
    if tipo == TIPO_CICLOS:
        columna = _buscar_columna(df, ["profundidad_de_pozo_mtr", "profundidad_pozo_mtr", "profundidad", "metros"])
    else:
        columna = _buscar_columna(df, ["total_metros", "metros", "produccion"])
    if not columna:
        return 0.0
    return round(float(pd.to_numeric(df[columna], errors="coerce").fillna(0).sum()), 2)


def diagnosticar_excel(ruta_excel):
    path = Path(ruta_excel)
    resultado_base = {
        "archivo": str(path),
        "hojas_detectadas": [],
        "hoja_principal_detectada": None,
        "columnas_detectadas": [],
        "total_filas_leidas": 0,
        "total_columnas": 0,
        "tipo_fuente_detectado": TIPO_DESCONOCIDO,
        "columnas_reconocidas": [],
        "columnas_no_reconocidas": [],
        "columnas_faltantes": [],
        "fecha_min": None,
        "fecha_max": None,
        "equipos_detectados": [],
        "operadores_detectados": [],
        "metros_totales_estimados": 0.0,
        "estado_diagnostico": "error",
        "observaciones": [],
    }
    if not path.exists():
        return {**resultado_base, "observaciones": ["El archivo no existe."]}

    try:
        xls = pd.ExcelFile(path)
        hojas = list(xls.sheet_names)
        hoja_principal, df = _leer_hoja_principal(path, hojas)
    except Exception as exc:
        return {**resultado_base, "observaciones": [f"No se pudo leer el Excel: {exc}"]}

    columnas = list(df.columns)
    columnas_normalizadas = _normalizar_columnas(columnas)
    tipo = detectar_tipo_fuente(columnas)
    reconocidas = _columnas_reconocidas_por_tipo(columnas_normalizadas, tipo)
    no_reconocidas = sorted(set(columnas_normalizadas).difference(reconocidas))
    faltantes = _columnas_faltantes_por_tipo(columnas_normalizadas, tipo)
    fechas = _serie_fechas(df, tipo).dropna()

    estado = "ok" if tipo != TIPO_DESCONOCIDO and not faltantes else "advertencia"
    observaciones = []
    if tipo == TIPO_DESCONOCIDO:
        observaciones.append("No se pudo clasificar el tipo de fuente con las columnas detectadas.")
    if faltantes:
        observaciones.append("Faltan columnas mínimas para una importación automática confiable.")
    if fechas.empty:
        observaciones.append("No se detectó rango de fechas.")

    return {
        "archivo": str(path),
        "hojas_detectadas": hojas,
        "hoja_principal_detectada": hoja_principal,
        "columnas_detectadas": [str(columna) for columna in columnas],
        "total_filas_leidas": int(len(df)),
        "total_columnas": int(len(columnas)),
        "tipo_fuente_detectado": tipo,
        "columnas_reconocidas": reconocidas,
        "columnas_no_reconocidas": no_reconocidas,
        "columnas_faltantes": faltantes,
        "fecha_min": fechas.min().strftime("%Y-%m-%d") if not fechas.empty else None,
        "fecha_max": fechas.max().strftime("%Y-%m-%d") if not fechas.empty else None,
        "equipos_detectados": _valores_unicos(df, COLUMNAS_CICLOS["equipo"] | COLUMNAS_REGISTRO_OPERACIONAL["equipo"]),
        "operadores_detectados": _valores_unicos(df, COLUMNAS_CICLOS["operador"] | COLUMNAS_REGISTRO_OPERACIONAL["operador"]),
        "metros_totales_estimados": _metros_estimados(df, tipo),
        "estado_diagnostico": estado,
        "observaciones": observaciones,
    }
