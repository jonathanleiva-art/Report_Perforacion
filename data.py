from datetime import datetime
from contextlib import closing
import logging
from pathlib import Path
import sqlite3
from unicodedata import normalize

import pandas as pd

from runtime_cache import cache_data

from audit import audit_log
from schema import NUMERIC_COLUMNS, TEXT_TAG_COLUMNS, columna_canonica
from config import BACKUP_DIR
from operators import agregar_columnas_operador_visual
from text_utils import reparar_mojibake
from utils import EXCEL_PATH, HORAS_TURNO, limpiar_entero
import db
from services.export_service import exportar_reportes_excel, respaldar_excel_actual


LOGGER = logging.getLogger(__name__)

def reparar_texto(valor):
    if valor is None:
        return ""

    texto = reparar_mojibake(valor).strip()
    if texto.lower() in ("", "nan", "none", "nat"):
        return ""
    return texto


def es_lista_valores(valor):
    return isinstance(valor, (list, tuple, set, dict))


def valor_a_texto(valor):
    if valor is None:
        return ""
    try:
        if not es_lista_valores(valor) and pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(valor, dict):
        valores = valor.values()
    elif isinstance(valor, (list, tuple, set)):
        valores = valor
    else:
        return reparar_texto(valor)

    partes = []
    for item in valores:
        texto = valor_a_texto(item)
        if texto and texto.lower() not in ("nan", "none", "nat"):
            partes.append(texto)
    return ",".join(partes)


def valor_a_numero(valor):
    if isinstance(valor, dict):
        valores = valor.values()
    elif isinstance(valor, (list, tuple, set)):
        valores = valor
    else:
        valores = [valor]

    numeros = pd.to_numeric(
        pd.Series([valor_a_texto(item) for item in valores]),
        errors="coerce",
    ).fillna(0)
    return numeros.sum()


def fusionar_columnas_duplicadas(df):
    duplicadas = df.columns[df.columns.duplicated()].unique()
    if len(duplicadas) == 0:
        return df

    resultado = df.loc[:, ~df.columns.duplicated()].copy()
    for columna in duplicadas:
        bloque = df.loc[:, df.columns == columna]
        if columna in NUMERIC_COLUMNS:
            resultado[columna] = bloque.apply(
                lambda fila: pd.to_numeric(
                    fila.map(valor_a_texto),
                    errors="coerce",
                ).fillna(0).sum(),
                axis=1,
            )
        else:
            resultado[columna] = bloque.apply(
                lambda fila: ", ".join(
                    dict.fromkeys(
                        texto.strip()
                        for valor in fila
                        for texto in valor_a_texto(valor).split(",")
                        if texto.strip()
                    )
                ),
                axis=1,
            )

    return resultado


def normalizar_columnas(df):
    df = df.rename(columns={
        str(col).strip(): columna_canonica(reparar_texto(str(col).strip()))
        for col in df.columns
    })
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed:")]
    return fusionar_columnas_duplicadas(df)


def normalizar_columna_texto(df, columna, enteros=False):
    if columna not in df.columns:
        return

    df[columna] = df[columna].apply(valor_a_texto)
    if enteros:
        df[columna] = df[columna].apply(normalizar_lista_enteros)
    else:
        df[columna] = df[columna].fillna("").astype(str).str.strip()


def normalizar_columna_numerica(df, columna):
    if columna not in df.columns:
        return

    serie = df[columna]
    if isinstance(serie, pd.DataFrame):
        serie = serie.apply(
            lambda fila: pd.to_numeric(fila.map(valor_a_texto), errors="coerce").fillna(0).sum(),
            axis=1,
        )
    else:
        serie = serie.apply(valor_a_numero)

    df[columna] = (
        pd.to_numeric(serie, errors="coerce")
        .replace([float("inf"), -float("inf")], 0)
        .fillna(0)
    )


def normalizar_fecha_turno(df):
    if "Fecha turno" not in df.columns:
        return df

    serie = df["Fecha turno"]
    fechas_iso = pd.to_datetime(serie, errors="coerce", format="%Y-%m-%d")
    fechas = fechas_iso.copy()
    pendientes = fechas.isna()
    if pendientes.any():
        fechas_dia = pd.to_datetime(serie[pendientes], errors="coerce", dayfirst=True)
        fechas.loc[pendientes] = fechas_dia
    df["Fecha turno"] = fechas.dt.date
    return df


def normalizar_tipo_detencion(valor):
    if valor is None:
        return ""

    partes = []
    for item in valor_a_texto(valor).split(","):
        texto = item.strip()
        clave = normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()
        if clave in ("mecania", "mecanica", "averia mecanica"):
            texto = "Avería mecánica"
        if clave in ("sin marcacion", "standby por falta de tajo/patio"):
            texto = "Standby por falta de tajo/Patio"
        if clave in ("agua", "abastecimiento agua", "relleno de agua"):
            texto = "Relleno de agua"
        if clave in ("mantencion", "mantencion programada"):
            texto = "Mantención Programada"
        if clave == "cambio de aceros":
            texto = "Cambio de aceros"
        if clave == "geologia":
            texto = "Geología"
        if texto:
            partes.append(texto)

    return ", ".join(dict.fromkeys(partes))


def integrar_causa_detencion_en_observaciones(df):
    if "Causa detención" not in df.columns:
        return df

    if "Observaciones" not in df.columns:
        df["Observaciones"] = ""

    causa = df["Causa detención"].apply(valor_a_texto)
    observaciones = df["Observaciones"].apply(valor_a_texto)
    prefijo = "Causa detención histórica: "

    def combinar(obs, causa_texto):
        obs = obs.strip()
        causa_texto = causa_texto.strip()
        if not causa_texto:
            return obs
        texto_historico = f"{prefijo}{causa_texto}"
        if causa_texto.lower() in obs.lower() or texto_historico.lower() in obs.lower():
            return obs
        return f"{obs}\n{texto_historico}" if obs else texto_historico

    df["Observaciones"] = [
        combinar(obs, causa_texto)
        for obs, causa_texto in zip(observaciones, causa)
    ]
    return df


def normalizar_lista_enteros(valor):
    if valor is None:
        return ""

    partes = []
    for item in valor_a_texto(valor).split(","):
        limpio = limpiar_entero(item)
        if limpio:
            partes.append(limpio)

    return ", ".join(partes)


def preparar_dataframe(df):
    if df.empty:
        return df

    df = normalizar_columnas(df.copy()).dropna(how="all")

    if "Número equipo" in df.columns:
        df["Número equipo"] = df["Número equipo"].apply(limpiar_entero)

    for col in ["Operador", "Modelo equipo", "Turno"]:
        normalizar_columna_texto(df, col)

    for col in TEXT_TAG_COLUMNS:
        normalizar_columna_texto(df, col, enteros=col in ("Banco", "Fase"))

    normalizar_columna_texto(df, "Estatus del Equipo")

    for col in NUMERIC_COLUMNS:
        normalizar_columna_numerica(df, col)

    if "Tipo detención" in df.columns:
        df["Tipo detención"] = df["Tipo detención"].apply(normalizar_tipo_detencion)

    df = normalizar_fecha_turno(df)
    df = integrar_causa_detencion_en_observaciones(df)

    if {"Modelo equipo", "Número equipo"}.issubset(df.columns):
        es_pv271_9291 = (
            df["Modelo equipo"].astype(str).str.strip().str.upper().eq("PV271")
            & df["Número equipo"].astype(str).apply(limpiar_entero).eq("9291")
        )
        df = df[~es_pv271_9291].copy()
        df["Equipo"] = (df["Modelo equipo"].astype(str) + " " + df["Número equipo"].astype(str)).str.strip()

    df = agregar_columnas_operador_visual(df, db_path=db.DB_PATH)
    return df.reset_index(drop=True)


def excel_mtime():
    path = Path(EXCEL_PATH)
    return path.stat().st_mtime if path.exists() else 0


def sqlite_mtime(db_path=db.DB_PATH):
    path = Path(db_path)
    return path.stat().st_mtime if path.exists() else 0


def registrar_diagnostico_sqlite(db_path, df):
    path = Path(db_path).resolve()
    timestamp = datetime.now().isoformat(timespec="seconds")
    total_df = len(df) if df is not None else 0
    total_sqlite = None
    ultimos = []
    tabla_legacy_count = None

    if path.exists():
        try:
            with closing(sqlite3.connect(path)) as connection:
                connection.row_factory = sqlite3.Row
                total_sqlite = connection.execute(
                    f"SELECT COUNT(*) FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
                ).fetchone()[0]
                tablas = {
                    fila["name"]
                    for fila in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                if "reportes" in tablas:
                    tabla_legacy_count = connection.execute(
                        f"SELECT COUNT(*) FROM {db.quote_identifier('reportes')}"
                    ).fetchone()[0]
                columnas = set(db.columnas_tabla(connection))
                columnas_ultimos = [
                    columna
                    for columna in [
                        "id",
                        "created_at",
                        "updated_at",
                        "source",
                        "Fecha turno",
                        "Turno",
                        "Modelo equipo",
                        "Número equipo",
                        "Operador",
                        "Hora registro",
                    ]
                    if columna in columnas
                ]
                if columnas_ultimos:
                    columnas_sql = ", ".join(db.quote_identifier(columna) for columna in columnas_ultimos)
                    filas = connection.execute(
                        f"SELECT {columnas_sql} FROM {db.quote_identifier(db.TABLA_REGISTROS)} ORDER BY id DESC LIMIT 6"
                    ).fetchall()
                    ultimos = [dict(fila) for fila in filas]
        except Exception:
            LOGGER.exception("No se pudo generar diagnostico temporal SQLite.")

    LOGGER.warning(
        "DIAGNOSTICO_SQLITE_TEMP timestamp=%s db_path=%s exists=%s mtime=%s count_sqlite=%s count_dataframe=%s count_tabla_reportes_legacy=%s ultimos=%s",
        timestamp,
        path,
        path.exists(),
        sqlite_mtime(path),
        total_sqlite,
        total_df,
        tabla_legacy_count,
        ultimos,
    )


@cache_data
def leer_excel_cached(path_text, mtime):
    path = Path(path_text)
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_excel(path, engine="openpyxl")
    return preparar_dataframe(df)


@cache_data
def leer_sqlite_cached(path_text, mtime):
    path = Path(path_text)
    if not path.exists():
        return pd.DataFrame()
    return db.leer_registros(db_path=path)


def leer_reportes():
    return leer_reportes_sqlite()


def leer_reportes_sqlite(db_path=db.DB_PATH):
    try:
        df_sqlite = leer_sqlite_cached(str(db_path), sqlite_mtime(db_path))
        resultado = df_sqlite if not df_sqlite.empty else pd.DataFrame()
        registrar_diagnostico_sqlite(db_path, resultado)
        return resultado
    except Exception as exc:
        LOGGER.exception("No se pudo leer SQLite.")
        audit_log.registrar_evento(
            "lectura_sqlite",
            resultado="error",
            detalle=str(exc),
        )
        return pd.DataFrame()


def leer_reportes_excel_legacy():
    path = Path(EXCEL_PATH)
    if not path.exists():
        return pd.DataFrame()

    try:
        return leer_excel_cached(str(path), excel_mtime())
    except Exception as exc:
        LOGGER.exception("No se pudo leer Excel legado.")
        audit_log.registrar_evento(
            "lectura_excel_legacy",
            resultado="error",
            detalle=str(exc),
        )
        return pd.DataFrame()


def crear_registro(datos):
    registro = {
        "Fecha": datetime.now().strftime("%d-%m-%Y"),
        "Hora registro": datetime.now().strftime("%H:%M:%S"),
        "Horas turno": HORAS_TURNO,
        **datos,
    }
    return preparar_dataframe(pd.DataFrame([registro]))


def guardar_reportes(df):
    path = Path(EXCEL_PATH)
    respaldo = respaldar_excel_actual(path)
    df = preparar_dataframe(df)
    if "Fecha turno" in df.columns:
        df = df.sort_values("Fecha turno", na_position="last")

    registros_sqlite = guardar_sqlite(df, db_path=db.DB_PATH)
    if registros_sqlite <= 0:
        raise RuntimeError("No se pudo guardar el reporte en SQLite.")

    try:
        exportar_reportes_excel(df, path=path)
    except Exception as exc:
        audit_log.registrar_evento(
            "guardado_excel",
            resultado="error",
            detalle=str(exc),
        )
        LOGGER.exception("No se pudo exportar Excel; SQLite ya quedo guardado.")
    return path, respaldo


def guardar_sqlite(df, db_path=db.DB_PATH, source="streamlit_save"):
    try:
        return db.reemplazar_dataframe_reportes(df, db_path=db_path, source=source)
    except Exception as exc:
        audit_log.registrar_evento(
            "guardado_sqlite",
            resultado="error",
            detalle=str(exc),
        )
        LOGGER.exception("No se pudo guardar en SQLite; se conserva exportacion Excel.")
        return 0


def respaldar_reportes_sqlite(df):
    try:
        registros = db.reemplazar_dataframe_reportes(df, source="excel_export")
        audit_log.registrar_respaldo_sqlite(
            resultado="ok",
            detalle={"registros": registros},
        )
    except Exception as exc:
        audit_log.registrar_respaldo_sqlite(
            resultado="error",
            detalle=str(exc),
        )
        LOGGER.exception("No se pudo respaldar reportes en SQLite.")


def anexar_sqlite(registro, db_path=db.DB_PATH, source="streamlit_save"):
    try:
        return db.insertar_registro(registro, db_path=db_path, source=source)
    except Exception as exc:
        audit_log.registrar_evento(
            "guardado_sqlite",
            resultado="error",
            detalle=str(exc),
        )
        LOGGER.exception("No se pudo guardar en SQLite; se conserva exportacion Excel.")
        return 0


def anexar_registro(registro):
    registros_sqlite = anexar_sqlite(registro, db_path=db.DB_PATH)
    if registros_sqlite <= 0:
        raise RuntimeError("No se pudo guardar el reporte en SQLite.")

    final = db.leer_registros(db_path=db.DB_PATH)
    path = Path(EXCEL_PATH)
    respaldo = respaldar_excel_actual(path)
    try:
        exportar_reportes_excel(final, path=path)
    except Exception as exc:
        audit_log.registrar_evento(
            "guardado_excel",
            resultado="error",
            detalle=str(exc),
        )
        LOGGER.exception("No se pudo exportar Excel; SQLite ya quedo guardado.")
    leer_excel_cached.clear()
    leer_sqlite_cached.clear()
    return final, path, respaldo


def limpiar_cache_reportes():
    leer_excel_cached.clear()
    leer_sqlite_cached.clear()
    try:
        db.limpiar_cache_consultas()
    except Exception:
        pass
