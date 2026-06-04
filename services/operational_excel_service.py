from contextlib import closing
from datetime import date
from pathlib import Path
import re
import sqlite3
from unicodedata import normalize

import pandas as pd

from config import DATABASE_PATH, PROJECT_ROOT
from metrics import calcular_horas_disponibles
from services.ciclos_service import quote_identifier


TABLA_FUENTES = "fuentes_datos"
TABLA_REGISTROS_EXCEL = "registros_excel_operacional"
TIPO_FUENTE = "excel_registro_operacional"
TIPOS_FUENTE_OPERACIONAL = {TIPO_FUENTE, "registro_operacional_excel"}
EXCEL_REGISTRO_MAYO = PROJECT_ROOT / "4001-Registro de Perforación_MAYO.xlsx"
NOMBRE_FUENTE_MAYO = "4001 - Registro de Perforación MAYO"

MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

COLUMNAS_SQL = {
    "id_registro": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "id_fuente": "INTEGER NOT NULL",
    "fecha_turno": "TEXT",
    "anio": "INTEGER",
    "mes": "TEXT",
    "dia": "INTEGER",
    "turno": "TEXT",
    "numero_equipo": "TEXT",
    "modelo": "TEXT",
    "operador": "TEXT",
    "produccion": "REAL",
    "mineral": "REAL",
    "precorte": "REAL",
    "buffer": "REAL",
    "repaso": "REAL",
    "total_metros": "REAL",
    "fase": "TEXT",
    "banco": "TEXT",
    "malla": "TEXT",
    "numero_pozos": "REAL",
    "rendimiento_mh": "REAL",
    "horas_trabajo": "REAL",
    "horas_efectivas": "REAL",
    "ajuste_taller": "REAL",
    "sin_operador": "REAL",
    "horas_averia": "REAL",
    "tronadura": "REAL",
    "cambio_turno": "REAL",
    "horas_mp": "REAL",
    "colacion": "REAL",
    "horas_sin_marca": "REAL",
    "horas_disponible": "REAL",
    "horas_totales": "REAL",
    "numero_bit_tricono": "TEXT",
    "martillo": "TEXT",
    "observaciones": "TEXT",
    "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
}

MAPEO_COLUMNAS = {
    "ano": "anio",
    "mes": "mes",
    "dia": "dia",
    "turno": "turno",
    "no_equipo": "numero_equipo",
    "modelo": "modelo",
    "operador": "operador",
    "produccion": "produccion",
    "mineral": "mineral",
    "precorte": "precorte",
    "buffer": "buffer",
    "repaso": "repaso",
    "total_metros": "total_metros",
    "fase": "fase",
    "banco": "banco",
    "malla": "malla",
    "n_pozos": "numero_pozos",
    "m_h": "rendimiento_mh",
    "horas_trabajo": "horas_trabajo",
    "horas_efectivas": "horas_efectivas",
    "ajuste_taller": "ajuste_taller",
    "sin_operador": "sin_operador",
    "horas_averia": "horas_averia",
    "tronadura": "tronadura",
    "cambio_turno": "cambio_turno",
    "horas_mp": "horas_mp",
    "colacion": "colacion",
    "horas_sin_marca": "horas_sin_marca",
    "horas_disponible": "horas_disponible",
    "horas_totales": "horas_totales",
    "no_bit_tricono": "numero_bit_tricono",
    "martillo": "martillo",
    "observaciones": "observaciones",
}


def _clave(valor):
    texto = normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().replace("\n", " ")
    return re.sub(r"[^a-z0-9]+", "_", texto).strip("_")


def _texto(valor):
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


def _numero(valor):
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return None
    return float(numero)


def _entero(valor):
    numero = _numero(valor)
    if numero is not None:
        return int(numero)
    fecha = pd.to_datetime(valor, errors="coerce")
    if pd.notna(fecha):
        return int(fecha.year)
    return None


def _mes_numero(valor):
    numero = _numero(valor)
    if numero is not None and 1 <= int(numero) <= 12:
        return int(numero)
    fecha = pd.to_datetime(valor, errors="coerce")
    if pd.notna(fecha) and int(fecha.year) > 1900:
        return int(fecha.month)
    texto = normalize("NFKD", _texto(valor)).encode("ascii", "ignore").decode("ascii").lower()
    return MESES.get(texto)


def _dia_numero(valor):
    numero = _numero(valor)
    if numero is not None and 1 <= int(numero) <= 31:
        return int(numero)
    fecha = pd.to_datetime(valor, errors="coerce")
    if pd.notna(fecha):
        return int(fecha.day)
    return None


def _fecha_turno(anio_valor, mes_valor, dia_valor):
    dia_fecha = pd.to_datetime(dia_valor, errors="coerce")
    if pd.notna(dia_fecha) and int(dia_fecha.year) > 2000:
        return dia_fecha.date()

    anio = _entero(anio_valor)
    if not anio:
        anio_fecha = pd.to_datetime(anio_valor, errors="coerce")
        anio = int(anio_fecha.year) if pd.notna(anio_fecha) else None
    mes = _mes_numero(mes_valor)
    dia = _dia_numero(dia_valor)
    if not anio or not mes or not dia:
        return None
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def _normalizar_turno(valor):
    texto = _texto(valor)
    upper = normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").upper()
    if upper in {"1", "DIA"}:
        return "Día"
    if upper in {"2", "NOCHE"}:
        return "Noche"
    return texto.capitalize() if upper in {"DIA", "NOCHE"} else texto


def _crear_tablas(connection):
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quote_identifier(TABLA_FUENTES)} (
            id_fuente INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_fuente TEXT NOT NULL,
            tipo_fuente TEXT NOT NULL,
            archivo_origen TEXT,
            fecha_importacion TEXT,
            total_registros INTEGER,
            fecha_min TEXT,
            fecha_max TEXT,
            activo INTEGER DEFAULT 1,
            observacion TEXT
        )
        """
    )
    columnas = ", ".join(f"{quote_identifier(col)} {tipo}" for col, tipo in COLUMNAS_SQL.items())
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quote_identifier(TABLA_REGISTROS_EXCEL)} (
            {columnas}
        )
        """
    )
    _asegurar_columnas_registros(connection)
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS {quote_identifier('idx_reg_excel_operacional_fuente')} "
        f"ON {quote_identifier(TABLA_REGISTROS_EXCEL)} ({quote_identifier('id_fuente')})"
    )
    connection.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {quote_identifier('uq_reg_excel_operacional_fuente_registro')} "
        f"ON {quote_identifier(TABLA_REGISTROS_EXCEL)} ("
        f"{quote_identifier('id_fuente')}, {quote_identifier('fecha_turno')}, "
        f"{quote_identifier('turno')}, {quote_identifier('numero_equipo')}, {quote_identifier('operador')})"
    )
    connection.commit()


def _columnas_tabla(connection, tabla):
    filas = connection.execute(f"PRAGMA table_info({quote_identifier(tabla)})").fetchall()
    columnas = []
    for fila in filas:
        try:
            columnas.append(fila["name"])
        except (TypeError, IndexError):
            columnas.append(fila[1])
    return columnas


def _asegurar_columnas_registros(connection):
    existentes = set(_columnas_tabla(connection, TABLA_REGISTROS_EXCEL))
    for columna, tipo in COLUMNAS_SQL.items():
        if columna in existentes or columna == "id_registro":
            continue
        if columna == "id_fuente":
            tipo_columna = "INTEGER"
        elif "DEFAULT" in tipo.upper():
            tipo_columna = tipo.split("DEFAULT", 1)[0].strip()
        else:
            tipo_columna = tipo
        connection.execute(
            f"ALTER TABLE {quote_identifier(TABLA_REGISTROS_EXCEL)} "
            f"ADD COLUMN {quote_identifier(columna)} {tipo_columna}"
        )


def detectar_fila_encabezado(excel_path=EXCEL_REGISTRO_MAYO, sheet_name="Registro"):
    bruto = pd.read_excel(excel_path, sheet_name=sheet_name, header=None, nrows=120)
    requeridas = {"ano", "mes", "dia", "turno", "no_equipo", "modelo", "operador"}
    for idx, fila in bruto.iterrows():
        claves = {_clave(valor) for valor in fila.tolist() if _texto(valor)}
        if len(requeridas.intersection(claves)) >= 5 and "total_metros" in claves:
            return int(idx)
    raise ValueError("No se encontró la fila de encabezados de la hoja Registro.")


def leer_excel_operacional(excel_path=EXCEL_REGISTRO_MAYO):
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    xls = pd.ExcelFile(path)
    if "Registro" not in xls.sheet_names:
        raise ValueError("El Excel no contiene la hoja Registro.")
    header_idx = detectar_fila_encabezado(path, sheet_name="Registro")
    df = pd.read_excel(path, sheet_name="Registro", header=header_idx)
    df = df.dropna(how="all").copy()
    df = df[[col for col in df.columns if not str(col).startswith("Unnamed")]].copy()
    renombres = {}
    for columna in df.columns:
        destino = MAPEO_COLUMNAS.get(_clave(columna))
        if destino:
            renombres[columna] = destino
    df = df.rename(columns=renombres)
    df = df[[col for col in df.columns if col in set(MAPEO_COLUMNAS.values())]].copy()

    for columna in COLUMNAS_SQL:
        if columna in {"id_registro", "id_fuente", "fecha_turno", "created_at"}:
            continue
        if columna not in df.columns:
            df[columna] = None

    fechas = [
        _fecha_turno(fila.get("anio"), fila.get("mes"), fila.get("dia"))
        for _, fila in df.iterrows()
    ]
    df["fecha_turno"] = fechas
    df["anio"] = pd.Series(fechas).map(lambda valor: valor.year if valor else None)
    df["mes"] = pd.Series(fechas).map(lambda valor: valor.month if valor else None)
    df["dia"] = pd.Series(fechas).map(lambda valor: valor.day if valor else None)
    df["turno"] = df["turno"].map(_normalizar_turno)
    df["numero_equipo"] = df["numero_equipo"].map(_texto)
    df["numero_equipo"] = df["numero_equipo"].str.replace(r"\.0$", "", regex=True)
    df["operador"] = df["operador"].map(_texto)

    numericas = [
        "produccion", "mineral", "precorte", "buffer", "repaso", "total_metros",
        "numero_pozos", "rendimiento_mh", "horas_trabajo", "horas_efectivas",
        "ajuste_taller", "sin_operador", "horas_averia", "tronadura",
        "cambio_turno", "horas_mp", "colacion", "horas_sin_marca",
        "horas_disponible", "horas_totales",
    ]
    for columna in numericas:
        df[columna] = pd.to_numeric(df[columna], errors="coerce")

    tiene_equipo = df["numero_equipo"].fillna("").astype(str).str.strip().ne("")
    tiene_fecha = pd.notna(df["fecha_turno"])
    tiene_metrica = df["horas_totales"].fillna(0).ne(0) | df["total_metros"].fillna(0).ne(0)
    df = df[tiene_equipo & tiene_fecha & tiene_metrica].copy()
    df["fecha_turno"] = df["fecha_turno"].map(lambda valor: valor.isoformat() if valor else "")
    return df.reset_index(drop=True)


def _obtener_o_crear_fuente(connection, excel_path, df):
    _crear_tablas(connection)
    path = Path(excel_path)
    archivo_origen = path.name
    fila = connection.execute(
        f"""
        SELECT id_fuente
        FROM {quote_identifier(TABLA_FUENTES)}
        WHERE tipo_fuente = ? AND archivo_origen = ?
        ORDER BY id_fuente DESC
        LIMIT 1
        """,
        (TIPO_FUENTE, archivo_origen),
    ).fetchone()
    fechas = pd.to_datetime(df["fecha_turno"], errors="coerce").dropna()
    fecha_min = fechas.min().strftime("%Y-%m-%d") if not fechas.empty else ""
    fecha_max = fechas.max().strftime("%Y-%m-%d") if not fechas.empty else ""
    if fila:
        id_fuente = int(fila["id_fuente"] if isinstance(fila, sqlite3.Row) else fila[0])
        connection.execute(
            f"""
            UPDATE {quote_identifier(TABLA_FUENTES)}
            SET nombre_fuente = ?,
                total_registros = ?,
                fecha_min = ?,
                fecha_max = ?,
                activo = 1
            WHERE id_fuente = ?
            """,
            (NOMBRE_FUENTE_MAYO, int(len(df)), fecha_min, fecha_max, id_fuente),
        )
        return id_fuente, fecha_min, fecha_max

    cursor = connection.execute(
        f"""
        INSERT INTO {quote_identifier(TABLA_FUENTES)}
        (nombre_fuente, tipo_fuente, archivo_origen, fecha_importacion, total_registros, fecha_min, fecha_max, activo, observacion)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, 1, 'Importado desde hoja Registro')
        """,
        (NOMBRE_FUENTE_MAYO, TIPO_FUENTE, archivo_origen, int(len(df)), fecha_min, fecha_max),
    )
    return int(cursor.lastrowid), fecha_min, fecha_max


def importar_excel_operacional(db_path=DATABASE_PATH, excel_path=EXCEL_REGISTRO_MAYO):
    df = leer_excel_operacional(excel_path)
    columnas_insert = [col for col in COLUMNAS_SQL if col not in {"id_registro", "created_at"}]
    with closing(sqlite3.connect(Path(db_path))) as connection:
        connection.row_factory = sqlite3.Row
        _crear_tablas(connection)
        id_fuente, fecha_min, fecha_max = _obtener_o_crear_fuente(connection, excel_path, df)
        connection.execute(
            f"DELETE FROM {quote_identifier(TABLA_REGISTROS_EXCEL)} WHERE id_fuente = ?",
            (id_fuente,),
        )
        placeholders = ", ".join("?" for _ in columnas_insert)
        columnas_sql = ", ".join(quote_identifier(col) for col in columnas_insert)
        insert_sql = (
            f"INSERT OR IGNORE INTO {quote_identifier(TABLA_REGISTROS_EXCEL)} "
            f"({columnas_sql}) VALUES ({placeholders})"
        )
        importadas = 0
        for _, fila in df.iterrows():
            valores = []
            for columna in columnas_insert:
                if columna == "id_fuente":
                    valores.append(id_fuente)
                else:
                    valor = fila.get(columna)
                    if isinstance(valor, float) and pd.isna(valor):
                        valor = None
                    valores.append(valor)
            cursor = connection.execute(insert_sql, valores)
            importadas += int(cursor.rowcount or 0)
        connection.execute(
            f"""
            UPDATE {quote_identifier(TABLA_FUENTES)}
            SET total_registros = (
                SELECT COUNT(*) FROM {quote_identifier(TABLA_REGISTROS_EXCEL)}
                WHERE id_fuente = ?
            )
            WHERE id_fuente = ?
            """,
            (id_fuente, id_fuente),
        )
        connection.commit()

    return {
        "id_fuente": id_fuente,
        "filas_leidas": int(len(df)),
        "filas_importadas": int(importadas),
        "duplicados_omitidos": int(len(df) - importadas),
        "fecha_min": fecha_min,
        "fecha_max": fecha_max,
        "total_metros": round(float(pd.to_numeric(df["total_metros"], errors="coerce").fillna(0).sum()), 2),
        "equipos": sorted(df["numero_equipo"].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].unique().tolist()),
        "operadores": sorted(df["operador"].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].unique().tolist()),
    }


def importar_registro_operacional_excel_desde_fuente(id_fuente, ruta_excel, db_path=DATABASE_PATH):
    if id_fuente is None or int(id_fuente) <= 0:
        raise ValueError("id_fuente debe ser un entero positivo.")

    df = leer_excel_operacional(ruta_excel)
    columnas_insert = [col for col in COLUMNAS_SQL if col not in {"id_registro", "created_at"}]
    fechas = pd.to_datetime(df["fecha_turno"], errors="coerce").dropna() if not df.empty else pd.Series(dtype="datetime64[ns]")
    fecha_min = fechas.min().strftime("%Y-%m-%d") if not fechas.empty else None
    fecha_max = fechas.max().strftime("%Y-%m-%d") if not fechas.empty else None
    metros_totales = round(float(pd.to_numeric(df.get("total_metros", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()), 2)
    errores = []

    if df.empty:
        errores.append("No se encontraron filas validas para importar.")
        return {
            "id_fuente": int(id_fuente),
            "filas_leidas": 0,
            "filas_validas": 0,
            "filas_insertadas": 0,
            "filas_rechazadas": 0,
            "duplicados": 0,
            "fecha_min": fecha_min,
            "fecha_max": fecha_max,
            "metros_totales": metros_totales,
            "errores": errores,
        }

    with closing(sqlite3.connect(Path(db_path))) as connection:
        connection.row_factory = sqlite3.Row
        _crear_tablas(connection)
        placeholders = ", ".join("?" for _ in columnas_insert)
        columnas_sql = ", ".join(quote_identifier(col) for col in columnas_insert)
        insert_sql = (
            f"INSERT OR IGNORE INTO {quote_identifier(TABLA_REGISTROS_EXCEL)} "
            f"({columnas_sql}) VALUES ({placeholders})"
        )
        insertadas = 0
        for _, fila in df.iterrows():
            valores = []
            for columna in columnas_insert:
                if columna == "id_fuente":
                    valores.append(int(id_fuente))
                    continue
                valor = fila.get(columna)
                try:
                    if pd.isna(valor):
                        valor = None
                except (TypeError, ValueError):
                    pass
                valores.append(valor)
            cursor = connection.execute(insert_sql, valores)
            insertadas += int(cursor.rowcount or 0)
        connection.commit()

    duplicados = int(len(df) - insertadas)
    return {
        "id_fuente": int(id_fuente),
        "filas_leidas": int(len(df)),
        "filas_validas": int(len(df)),
        "filas_insertadas": int(insertadas),
        "filas_rechazadas": 0,
        "duplicados": duplicados,
        "fecha_min": fecha_min,
        "fecha_max": fecha_max,
        "metros_totales": metros_totales,
        "errores": errores,
    }


def listar_fuentes_operacionales(db_path=DATABASE_PATH, solo_activas=True):
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame()
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        _crear_tablas(connection)
        tipos = sorted(TIPOS_FUENTE_OPERACIONAL)
        placeholders = ", ".join("?" for _ in tipos)
        sql = f"SELECT * FROM {quote_identifier(TABLA_FUENTES)} WHERE tipo_fuente IN ({placeholders})"
        params = tipos
        if solo_activas:
            sql += " AND activo = 1"
        sql += " ORDER BY fecha_importacion DESC, id_fuente DESC"
        return pd.read_sql_query(sql, connection, params=params)


def resumen_fuentes_operacionales(db_path=DATABASE_PATH, solo_activas=True):
    fuentes = listar_fuentes_operacionales(db_path=db_path, solo_activas=solo_activas)
    if fuentes.empty:
        return fuentes

    registros = leer_registros_operacional(db_path=db_path)
    if registros.empty:
        df = fuentes.copy()
        df["registros_importados"] = 0
        df["metros_importados"] = 0.0
        df["equipos"] = 0
        df["operadores"] = 0
    else:
        base = registros.copy()
        base["id_fuente"] = pd.to_numeric(base["id_fuente"], errors="coerce").astype("Int64")
        base["total_metros"] = pd.to_numeric(base.get("total_metros", 0), errors="coerce").fillna(0)
        resumen = base.groupby("id_fuente", dropna=True).agg(
            registros_importados=("id_registro", "count"),
            metros_importados=("total_metros", "sum"),
            equipos=("numero_equipo", lambda serie: serie.dropna().astype(str).str.strip().loc[lambda s: s.ne("")].nunique()),
            operadores=("operador", lambda serie: serie.dropna().astype(str).str.strip().loc[lambda s: s.ne("")].nunique()),
        ).reset_index()
        resumen["metros_importados"] = resumen["metros_importados"].round(2)
        df = fuentes.merge(resumen, on="id_fuente", how="left")
        for columna in ["registros_importados", "equipos", "operadores"]:
            df[columna] = pd.to_numeric(df[columna], errors="coerce").fillna(0).astype(int)
        df["metros_importados"] = pd.to_numeric(df["metros_importados"], errors="coerce").fillna(0.0).round(2)

    if "estado" not in df.columns:
        df["estado"] = "activa"
    else:
        df["estado"] = df["estado"].fillna("").astype(str).replace("", "activa")
    if "activo" not in df.columns:
        df["activo"] = 1
    else:
        df["activo"] = pd.to_numeric(df["activo"], errors="coerce").fillna(1).astype(int)
    return df[[
        "id_fuente",
        "nombre_fuente",
        "archivo_origen",
        "fecha_importacion",
        "fecha_min",
        "fecha_max",
        "total_registros",
        "registros_importados",
        "metros_importados",
        "equipos",
        "operadores",
        "estado",
        "activo",
        "observacion",
    ]]


def leer_registros_operacional(db_path=DATABASE_PATH, id_fuente=None):
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame()
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        _crear_tablas(connection)
        sql = f"SELECT r.*, f.nombre_fuente FROM {quote_identifier(TABLA_REGISTROS_EXCEL)} r LEFT JOIN {quote_identifier(TABLA_FUENTES)} f ON f.id_fuente = r.id_fuente"
        params = []
        if id_fuente is not None:
            sql += " WHERE r.id_fuente = ?"
            params.append(int(id_fuente))
        return pd.read_sql_query(sql, connection, params=params)


def _fechas_desde_componentes(df):
    if df is None or df.empty or not {"anio", "mes", "dia"}.issubset(df.columns):
        return pd.Series(pd.NaT, index=getattr(df, "index", None), dtype="datetime64[ns]")
    fechas = [
        _fecha_turno(fila.get("anio"), fila.get("mes"), fila.get("dia"))
        for _, fila in df.iterrows()
    ]
    return pd.to_datetime(pd.Series(fechas, index=df.index), errors="coerce")


def leer_fuente_operacional_normalizada_df(df_registros):
    columnas = [
        "fecha_turno",
        "turno",
        "equipo",
        "operador",
        "metros",
        "horas_efectivas",
        "horas_averia",
        "horas_mp",
        "disponibilidad",
        "utilizacion",
        "rendimiento",
    ]
    if df_registros is None or df_registros.empty:
        return pd.DataFrame(columns=columnas)

    df = df_registros.copy()
    fecha_componentes = _fechas_desde_componentes(df)
    fecha_guardada = pd.to_datetime(df.get("fecha_turno"), errors="coerce")
    fecha_turno = fecha_componentes.fillna(fecha_guardada)
    horas_totales = pd.to_numeric(df.get("horas_totales", 0), errors="coerce").fillna(0)
    horas_efectivas = pd.to_numeric(df.get("horas_efectivas", 0), errors="coerce").fillna(0)
    horas_averia = pd.to_numeric(df.get("horas_averia", 0), errors="coerce").fillna(0)
    horas_mp = pd.to_numeric(df.get("horas_mp", 0), errors="coerce").fillna(0)
    total_metros = pd.to_numeric(df.get("total_metros", df.get("metros", 0)), errors="coerce").fillna(0)
    horas_disponible = calcular_horas_disponibles(
        horas_totales,
        horas_averia=horas_averia,
        horas_mantencion=horas_mp,
    )
    rendimiento = pd.to_numeric(df.get("rendimiento_mh", pd.Series(dtype=float)), errors="coerce")
    rendimiento = rendimiento.fillna(total_metros.div(horas_efectivas.where(horas_efectivas.ne(0), pd.NA)).fillna(0))
    disponibilidad = horas_disponible.div(horas_totales.where(horas_totales.ne(0), pd.NA)).fillna(0) * 100
    utilizacion = horas_efectivas.div(horas_disponible.where(horas_disponible.ne(0), pd.NA)).fillna(0) * 100
    texto_vacio = pd.Series([""] * len(df), index=df.index)
    return pd.DataFrame({
        "id_fuente": df.get("id_fuente", pd.Series([None] * len(df), index=df.index)),
        "nombre_fuente": df.get("nombre_fuente", pd.Series([NOMBRE_FUENTE_MAYO] * len(df), index=df.index)),
        "fecha_turno": fecha_turno.dt.date,
        "turno": df.get("turno", texto_vacio).fillna("").astype(str),
        "equipo": df.get("numero_equipo", texto_vacio).fillna("").astype(str),
        "numero_equipo": df.get("numero_equipo", texto_vacio).fillna("").astype(str),
        "modelo": df.get("modelo", texto_vacio).fillna("").astype(str),
        "operador": df.get("operador", texto_vacio).fillna("").astype(str),
        "metros": total_metros,
        "total_metros": total_metros,
        "horas_efectivas": horas_efectivas,
        "horas_averia": horas_averia,
        "horas_mp": horas_mp,
        "horas_totales": horas_totales,
        "horas_disponibles": horas_disponible,
        "disponibilidad": disponibilidad,
        "utilizacion": utilizacion,
        "rendimiento": rendimiento,
        "rendimiento_mh": rendimiento,
        "banco": df.get("banco", texto_vacio).fillna("").astype(str),
        "malla": df.get("malla", texto_vacio).fillna("").astype(str),
        "fase": df.get("fase", texto_vacio).fillna("").astype(str),
        "numero_pozos": pd.to_numeric(df.get("numero_pozos", 0), errors="coerce").fillna(0),
        "observaciones": df.get("observaciones", texto_vacio).fillna("").astype(str),
    }).reset_index(drop=True)


def leer_fuente_operacional_normalizada(id_fuente, db_path=DATABASE_PATH):
    return leer_fuente_operacional_normalizada_df(
        leer_registros_operacional(db_path=db_path, id_fuente=id_fuente)
    )


def registros_a_dataframe_dashboard(df_registros):
    if df_registros is None or df_registros.empty:
        return pd.DataFrame()
    df = leer_fuente_operacional_normalizada_df(df_registros)
    horas_totales = pd.to_numeric(df["horas_totales"], errors="coerce").fillna(0)
    horas_efectivas = pd.to_numeric(df["horas_efectivas"], errors="coerce").fillna(0)
    horas_averia = pd.to_numeric(df["horas_averia"], errors="coerce").fillna(0)
    horas_mp = pd.to_numeric(df["horas_mp"], errors="coerce").fillna(0)
    total_metros = pd.to_numeric(df["metros"], errors="coerce").fillna(0)
    horas_disponible = pd.to_numeric(df["horas_disponibles"], errors="coerce").fillna(0)
    rendimiento = pd.to_numeric(df["rendimiento"], errors="coerce").fillna(0)
    disponibilidad = pd.to_numeric(df["disponibilidad"], errors="coerce").fillna(0)
    utilizacion = pd.to_numeric(df["utilizacion"], errors="coerce").fillna(0)
    resultado = pd.DataFrame({
        "id_fuente": df["id_fuente"],
        "Fuente de datos": df.get("nombre_fuente", NOMBRE_FUENTE_MAYO),
        "fecha_turno": df["fecha_turno"],
        "Fecha turno": df["fecha_turno"],
        "Modelo equipo": df["modelo"].fillna("").astype(str),
        "Número equipo": df["numero_equipo"].fillna("").astype(str),
        "equipo": df["equipo"].fillna("").astype(str),
        "Equipo": df["numero_equipo"].fillna("").astype(str),
        "operador": df["operador"].fillna("").astype(str),
        "Operador": df["operador"].fillna("").astype(str),
        "operador_display": df["operador"].fillna("").astype(str),
        "turno": df["turno"].fillna("").astype(str),
        "Turno": df["turno"].fillna("").astype(str),
        "Banco": df["banco"].fillna("").astype(str),
        "Malla": df["malla"].fillna("").astype(str),
        "Fase": df["fase"].fillna("").astype(str),
        "metros": total_metros,
        "Metros perforados": total_metros,
        "Pozos perforados turno": pd.to_numeric(df["numero_pozos"], errors="coerce").fillna(0),
        "horas_efectivas": horas_efectivas,
        "Horas efectivas perforando": horas_efectivas,
        "horas_averia": horas_averia,
        "Horas detención mecánica": horas_averia,
        "Horas avería equipo": horas_averia,
        "Mantención Programada": horas_mp,
        "horas_mp": horas_mp,
        "Horas MP": horas_mp,
        "Horas Totales": horas_totales,
        "Horas Disponible": horas_disponible,
        "Horas detención No efectivas": (horas_totales - horas_efectivas).clip(lower=0),
        "disponibilidad": disponibilidad,
        "Disponibilidad %": disponibilidad,
        "utilizacion": utilizacion,
        "Utilización": utilizacion,
        "rendimiento": rendimiento,
        "Rendimiento m/h": rendimiento,
        "Tipo de perforación": "",
        "Observaciones": df["observaciones"].fillna("").astype(str),
    })
    return resultado.reset_index(drop=True)


def leer_operacional_dashboard(db_path=DATABASE_PATH, id_fuente=None):
    return registros_a_dataframe_dashboard(leer_registros_operacional(db_path=db_path, id_fuente=id_fuente))


def obtener_opciones_filtros_operacional(db_path=DATABASE_PATH, id_fuente=None):
    df = leer_operacional_dashboard(db_path=db_path, id_fuente=id_fuente)
    if df.empty:
        return {"operadores": [], "equipos": [], "turnos": [], "fechas": []}
    return {
        "operadores": sorted(df["Operador"].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].unique().tolist()),
        "equipos": sorted(df["Equipo"].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].unique().tolist()),
        "turnos": sorted(df["Turno"].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].unique().tolist()),
        "fechas": sorted(pd.to_datetime(df["Fecha turno"], errors="coerce").dt.strftime("%Y-%m-%d").dropna().unique().tolist()),
    }
