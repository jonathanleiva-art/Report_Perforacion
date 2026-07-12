from datetime import date, timedelta
from pathlib import Path
import sqlite3
from unicodedata import normalize

import pandas as pd

from schema import columnas_equivalentes
from services.catalog_service import FLOTA_EQUIPOS


EQUIPOS_REPORTES_REQUERIDOS = FLOTA_EQUIPOS
TURNOS_REPORTES_REQUERIDOS = ["Día", "Noche"]


def _normalizar_equipo(valor):
    texto = str(valor or "").strip()
    if texto.lower() in ("", "nan", "none", "nat"):
        return ""
    texto = texto.replace("\u00a0", "").strip()
    try:
        numero = float(texto)
    except (TypeError, ValueError):
        return texto
    return str(int(numero)) if numero.is_integer() else texto


def _normalizar_turno(valor):
    texto = str(valor or "").replace("\u00a0", " ").strip()
    texto_lower = texto.lower()
    normalizado = normalize("NFKD", texto_lower).encode("ascii", "ignore").decode("ascii")
    normalizado = normalizado.strip()
    if "noche" in normalizado:
        return "Noche"
    if normalizado in {"dia", "da", "d a"} or texto_lower.startswith("d"):
        return "Día"
    return texto.strip().title()


def _fecha_or_none(valor):
    if valor is None or valor == "":
        return None
    serie = pd.Series([valor])
    fecha = pd.to_datetime(serie, errors="coerce", format="%Y-%m-%d").dt.date.iloc[0]
    if pd.isna(fecha):
        fecha = pd.to_datetime(serie, errors="coerce", dayfirst=True).dt.date.iloc[0]
    if pd.isna(fecha):
        return None
    return fecha


def _rango_fechas(fecha_inicio, fecha_fin):
    if fecha_inicio is None or fecha_fin is None or fecha_inicio > fecha_fin:
        return []
    dias = (fecha_fin - fecha_inicio).days
    return [fecha_inicio + timedelta(days=offset) for offset in range(dias + 1)]


def _leer_registros_reportes(db_path):
    import db

    path = Path(db_path or db.DB_PATH)
    if not path.exists():
        return pd.DataFrame(columns=["Fecha turno", "Turno", "Número equipo"])

    try:
        with sqlite3.connect(path) as connection:
            connection.row_factory = sqlite3.Row
            columnas = db.columnas_tabla(connection)
            columna_fecha = db._resolver_columna_existente(columnas, "Fecha turno", "Fecha")
            columna_turno = db._resolver_columna_existente(columnas, "Turno")
            columna_equipo = db._resolver_columna_existente(columnas, "Número equipo", "Numero equipo", "Nro equipo")
            if not columna_fecha or not columna_turno or not columna_equipo:
                return pd.DataFrame(columns=["Fecha turno", "Turno", "Número equipo"])

            query = f"""
                SELECT
                    {db.quote_identifier(columna_fecha)} AS fecha_turno,
                    {db.quote_identifier(columna_turno)} AS turno,
                    {db.quote_identifier(columna_equipo)} AS numero_equipo
                FROM {db.quote_identifier(db.TABLA_REGISTROS)}
                WHERE TRIM(COALESCE({db.quote_identifier(columna_fecha)}, '')) <> ''
            """
            return pd.read_sql_query(query, connection)
    except sqlite3.DatabaseError:
        return pd.DataFrame(columns=["Fecha turno", "Turno", "Número equipo"])


def get_reportes_faltantes(
    fecha_desde=None,
    fecha_hasta=None,
    db_path=None,
    equipos=None,
    turnos=None,
    reference_date=None,
):
    """Devuelve la matriz fecha x equipo x turno faltante en reportes operacionales."""
    registros = _leer_registros_reportes(db_path)
    columnas_salida = ["Fecha", "Turno", "Equipo", "Días de atraso"]
    if registros.empty:
        return pd.DataFrame(columns=columnas_salida)

    fechas_registradas = registros["fecha_turno"].map(_fecha_or_none)
    registros = registros.assign(_fecha=fechas_registradas).dropna(subset=["_fecha"])
    if registros.empty:
        return pd.DataFrame(columns=columnas_salida)

    hoy = _fecha_or_none(reference_date) or date.today()
    inicio = _fecha_or_none(fecha_desde) or min(registros["_fecha"])
    fin = _fecha_or_none(fecha_hasta) or hoy
    if fin > hoy:
        fin = hoy

    equipos_requeridos = [_normalizar_equipo(equipo) for equipo in (equipos or EQUIPOS_REPORTES_REQUERIDOS)]
    equipos_requeridos = [equipo for equipo in equipos_requeridos if equipo]
    turnos_requeridos = [_normalizar_turno(turno) for turno in (turnos or TURNOS_REPORTES_REQUERIDOS)]
    turnos_requeridos = [turno for turno in turnos_requeridos if turno]

    registrados = set()
    for _, fila in registros.iterrows():
        registrados.add(
            (
                fila["_fecha"].isoformat(),
                _normalizar_turno(fila.get("turno")),
                _normalizar_equipo(fila.get("numero_equipo")),
            )
        )

    faltantes = []
    for fecha in _rango_fechas(inicio, fin):
        fecha_iso = fecha.isoformat()
        for turno in turnos_requeridos:
            for equipo in equipos_requeridos:
                if (fecha_iso, turno, equipo) in registrados:
                    continue
                faltantes.append(
                    {
                        "Fecha": fecha,
                        "Turno": turno,
                        "Equipo": equipo,
                        "Días de atraso": max((hoy - fecha).days, 0),
                    }
                )

    resultado = pd.DataFrame(faltantes, columns=columnas_salida)
    if resultado.empty:
        return resultado
    return resultado.sort_values(["Fecha", "Turno", "Equipo"], ascending=[False, True, True]).reset_index(drop=True)


def evaluar_alertas_operacionales(df, horas_turno=12):
    if df.empty:
        return {"mensajes": [], "detalle": pd.DataFrame(), "sin_alertas": False}

    mensajes = []
    tipos_alerta = pd.Series("", index=df.index, dtype=str)

    evaluar_inconsistencia_disponibilidad_mantencion(df, mensajes, tipos_alerta)
    evaluar_baja_utilizacion(df, mensajes, tipos_alerta)
    evaluar_bajo_rendimiento(df, mensajes, tipos_alerta)
    evaluar_inconsistencia_horas_turno(df, mensajes, tipos_alerta, horas_turno)

    return {
        "mensajes": mensajes,
        "detalle": construir_detalle_alertas(df, tipos_alerta),
        "sin_alertas": not mensajes,
    }


def evaluar_inconsistencia_disponibilidad_mantencion(df, mensajes, tipos_alerta):
    disponibilidad = serie_numerica(df, *columnas_equivalentes("disponibilidad"))
    mantencion = serie_numerica(df, *columnas_equivalentes("horas_mantencion"))
    if disponibilidad.empty or mantencion.empty:
        return

    conflicto_mantencion = disponibilidad.ge(99.99) & mantencion.gt(0)
    if not conflicto_mantencion.any():
        return

    mensajes.append((
        "error",
        f"{int(conflicto_mantencion.sum())} registro(s) con disponibilidad 100% "
        "y horas de mantención programada.",
    ))
    tipos_alerta.loc[conflicto_mantencion] = tipos_alerta.loc[conflicto_mantencion].apply(
        lambda valor: agregar_tipo_alerta(valor, "Disponibilidad 100% con mantención")
    )


def evaluar_baja_utilizacion(df, mensajes, tipos_alerta):
    utilizacion = serie_numerica(df, *columnas_equivalentes("utilizacion"))
    if utilizacion.empty:
        return

    utilizacion_baja = utilizacion.lt(50)
    if not utilizacion_baja.any():
        return

    mensajes.append((
        "warning",
        f"{int(utilizacion_baja.sum())} registro(s) con utilización muy baja "
        f"(< 50%). Promedio: {formato_numero(utilizacion.mean(), 2, '%')}.",
    ))
    tipos_alerta.loc[utilizacion_baja] = tipos_alerta.loc[utilizacion_baja].apply(
        lambda valor: agregar_tipo_alerta(valor, "Utilización muy baja")
    )


def evaluar_bajo_rendimiento(df, mensajes, tipos_alerta):
    metros, _, rendimiento = totales_productivos(df)
    if metros > 0 and rendimiento < 10:
        mensajes.append((
            "warning",
            f"Rendimiento bajo: {formato_numero(rendimiento, 2)} m/h "
            f"con {formato_numero(metros, 2)} metros productivos.",
        ))
        rendimiento_fila = serie_numerica(df, *columnas_equivalentes("rendimiento"))
        if not rendimiento_fila.empty:
            rendimiento_bajo = rendimiento_fila.gt(0) & rendimiento_fila.lt(10)
            tipos_alerta.loc[rendimiento_bajo] = tipos_alerta.loc[rendimiento_bajo].apply(
                lambda valor: agregar_tipo_alerta(valor, "Rendimiento bajo")
            )
    elif metros == 0:
        mensajes.append(("warning", "No hay metros productivos para calcular rendimiento operacional."))


def evaluar_inconsistencia_horas_turno(df, mensajes, tipos_alerta, horas_turno):
    horas = serie_numerica(df, "Horas turno")
    if horas.empty:
        return

    turnos_invalidos = (horas - horas_turno).abs().gt(0.01)
    if not turnos_invalidos.any():
        return

    mensajes.append((
        "warning",
        f"{int(turnos_invalidos.sum())} registro(s) con horas de turno distintas "
        f"de {formato_numero(horas_turno, 0)} h.",
    ))
    tipos_alerta.loc[turnos_invalidos] = tipos_alerta.loc[turnos_invalidos].apply(
        lambda valor: agregar_tipo_alerta(valor, "Horas turno distintas de 12")
    )


def evaluar_baja_disponibilidad(df, umbral=60):
    disponibilidad = serie_numerica(df, *columnas_equivalentes("disponibilidad"))
    return disponibilidad.lt(umbral) if not disponibilidad.empty else pd.Series(False, index=df.index)


def evaluar_equipos_sin_marcacion(df):
    horas = serie_numerica(df, *columnas_equivalentes("sin_marcacion"))
    sin_marcacion_horas = horas.gt(0) if not horas.empty else pd.Series(False, index=df.index)
    if "Tipo detención" not in df.columns:
        return sin_marcacion_horas
    sin_marcacion_tipo = df["Tipo detención"].astype(str).str.contains("Sin marcación", case=False, na=False)
    return sin_marcacion_horas | sin_marcacion_tipo


def evaluar_detenciones_altas(df, horas_turno=12, proporcion=0.35):
    horas_no_efectivas = serie_numerica(df, *columnas_equivalentes("horas_no_efectivas"))
    horas_averia = serie_numerica(df, *columnas_equivalentes("horas_averia"))
    if horas_no_efectivas.empty:
        horas_no_efectivas = pd.Series(0, index=df.index)
    if horas_averia.empty:
        horas_averia = pd.Series(0, index=df.index)
    umbral = max(float(horas_turno) * float(proporcion), 0)
    return (horas_no_efectivas + horas_averia).ge(umbral)


def normalizar_nombre_columna(nombre):
    texto = normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode("ascii")
    return texto.lower().strip()


def buscar_columna(df, *candidatos):
    if df is None:
        return None

    columnas_normalizadas = {
        normalizar_nombre_columna(columna): columna
        for columna in df.columns
    }
    for candidato in candidatos:
        columna = columnas_normalizadas.get(normalizar_nombre_columna(candidato))
        if columna is not None:
            return columna
    return None


def serie_numerica(df, *columnas):
    if df is None:
        return pd.Series(dtype=float)

    candidatos = columnas[0] if len(columnas) == 1 and isinstance(columnas[0], (list, tuple, set)) else columnas
    columna = buscar_columna(df, *candidatos)
    if columna is not None:
        return pd.to_numeric(df[columna], errors="coerce").fillna(0)
    return pd.Series([0.0] * len(df), index=df.index, dtype=float)


def totales_productivos(df):
    metros = serie_numerica(df, *columnas_equivalentes("metros_perforados"))
    horas = serie_numerica(df, *columnas_equivalentes("horas_efectivas"))
    productivos = metros.gt(0) & horas.gt(0)
    total_metros = float(metros[productivos].sum())
    total_horas = float(horas[productivos].sum())
    rendimiento = total_metros / total_horas if total_horas > 0 else 0.0
    return total_metros, total_horas, rendimiento


def formato_numero(valor, decimales=2, sufijo=""):
    numero = pd.to_numeric(pd.Series([valor]), errors="coerce").fillna(0).iloc[0]
    return f"{numero:,.{decimales}f}{sufijo}"


def agregar_tipo_alerta(valor, alerta):
    return f"{valor}, {alerta}" if valor else alerta


def construir_detalle_alertas(df, tipos_alerta):
    indices_alerta = tipos_alerta[tipos_alerta.astype(str).str.strip().ne("")].index
    if len(indices_alerta) == 0:
        return pd.DataFrame()

    base = df.loc[indices_alerta].copy()
    columnas_detalle = [
        ("Fecha", [*columnas_equivalentes("fecha_turno"), "Fecha"]),
        ("Turno", columnas_equivalentes("turno")),
        ("Equipo", ["Equipo", "Modelo equipo"]),
        ("Número de equipo", columnas_equivalentes("numero_equipo")),
        ("Operador", columnas_equivalentes("operador")),
        ("Disponibilidad %", columnas_equivalentes("disponibilidad")),
        ("Utilización", columnas_equivalentes("utilizacion")),
        ("Rendimiento m/h", columnas_equivalentes("rendimiento")),
        ("Mantención programada", columnas_equivalentes("horas_mantencion")),
        ("Total horas turno", ["Horas turno"]),
    ]

    detalle = pd.DataFrame(index=base.index)
    for salida, candidatos in columnas_detalle:
        columna = buscar_columna(base, *candidatos)
        if columna:
            detalle[salida] = base[columna]

    detalle["Tipo de alerta"] = tipos_alerta.loc[indices_alerta].values
    detalle["Recomendación operacional"] = detalle["Tipo de alerta"].apply(recomendacion_alerta)
    if "Fecha" in detalle.columns:
        detalle["Fecha"] = pd.to_datetime(detalle["Fecha"], errors="coerce").dt.strftime("%d-%m-%Y")

    return detalle.reset_index(drop=True)


def recomendacion_alerta(tipo_alerta):
    recomendaciones = {
        "Utilización muy baja": "Revisar detenciones, tiempos no efectivos y continuidad operacional.",
        "Rendimiento bajo": "Revisar tipo de terreno, parámetros de perforación y condición de aceros.",
        "Disponibilidad 100% con mantención": "Revisar cálculo de disponibilidad; la mantención debe afectar la disponibilidad del equipo.",
        "Horas turno distintas de 12": "Revisar suma de horas efectivas, no efectivas y averías.",
    }
    return " ".join(
        recomendaciones[alerta]
        for alerta in [parte.strip() for parte in str(tipo_alerta).split(",") if parte.strip()]
        if alerta in recomendaciones
    )
