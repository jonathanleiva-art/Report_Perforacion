from pathlib import Path
from calendar import monthrange
from contextlib import closing
import csv
import json
import sqlite3
from unicodedata import normalize

import pandas as pd

from config import DATABASE_PATH, PROJECT_ROOT
from operators import cargar_mapa_operadores, normalizar_codigo_operador


TABLA_CICLOS = "ciclos_perforacion"
TABLA_FUENTES = "fuentes_datos"
EXCEL_CICLOS_NOMBRE = "Ciclos de Perforación.xls"
OPERADORES_PENDIENTES_CSV = PROJECT_ROOT / "operadores_pendientes_ciclos.csv"
FUENTE_TODOS_EXCEL = "Todos los Excel importados"

COLUMNA_IDENT = "Ident de Registro de Ciclo de Perforación"
COLUMNA_FECHA = "Fecha de Turno de Perforación"
COLUMNA_TURNO = "Turno de Perforación"
COLUMNA_EQUIPO = "Unidad de Perforación"
COLUMNA_OPERADOR = "Operador de Unidad de Perforación"
COLUMNA_PROFUNDIDAD = "Profundidad de Pozo (MTR)"
COLUMNA_REPERFORACION = "Es Reperforación"
COLUMNA_POZO = "Pozo Perforación"


def ruta_excel_ciclos():
    directa = PROJECT_ROOT / EXCEL_CICLOS_NOMBRE
    if directa.exists():
        return directa
    candidatos = sorted(PROJECT_ROOT.glob("Ciclos*.xls*"))
    return candidatos[0] if candidatos else directa


def quote_identifier(identifier):
    return '"' + str(identifier).replace('"', '""') + '"'


def _columnas_tabla(connection, tabla):
    try:
        filas = connection.execute(f"PRAGMA table_info({quote_identifier(tabla)})").fetchall()
    except sqlite3.OperationalError:
        return []
    columnas = []
    for fila in filas:
        try:
            columnas.append(fila["name"])
        except (TypeError, IndexError):
            columnas.append(fila[1])
    return columnas


def _tablas(connection):
    return {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }


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
    if isinstance(valor, pd.Timestamp):
        return valor.isoformat()
    return str(valor).strip()


def _normalizar_nombre_columna(valor):
    texto = normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.strip().split())


def _display_codigo_pendiente(codigo_original):
    texto = _texto(codigo_original)
    if not texto:
        return ""
    if texto.upper().startswith("M-"):
        return texto
    normalizado = normalizar_codigo_operador(texto)
    if not normalizado:
        return texto
    sin_ceros = normalizado.lstrip("0") or normalizado
    return f"M-{sin_ceros}"


def leer_excel_ciclos(excel_path=None):
    path = Path(excel_path or ruta_excel_ciclos())
    if not path.exists():
        return pd.DataFrame()

    bruto = pd.read_excel(path, sheet_name=0, header=None)
    header_idx = None
    for idx, fila in bruto.iterrows():
        valores = [_normalizar_nombre_columna(valor) for valor in fila.tolist()]
        if "Ident de Registro de Ciclo de Perforacion" in valores:
            header_idx = idx
            break
    if header_idx is None:
        raise ValueError("No se encontró la fila de encabezados del Excel de ciclos.")

    df = pd.read_excel(path, sheet_name=0, header=header_idx)
    df = df.dropna(how="all").copy()
    df.columns = [str(col).strip() for col in df.columns]
    if COLUMNA_IDENT not in df.columns:
        raise ValueError(f"No existe la columna obligatoria {COLUMNA_IDENT!r}.")
    df = df[df[COLUMNA_IDENT].map(_texto).ne("")]
    return df.reset_index(drop=True)


def _equipos_asociados(df):
    if COLUMNA_EQUIPO not in df.columns:
        return []
    return sorted(df[COLUMNA_EQUIPO].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].unique())


def _fechas_disponibles(df):
    fechas = []
    for columna in [COLUMNA_FECHA, "Fecha de Turno Inicial", "Fecha de Fin de Turno"]:
        if columna not in df.columns:
            continue
        serie = pd.to_datetime(df[columna], errors="coerce").dt.date.dropna()
        fechas.extend(serie.astype(str).tolist())
    return sorted(set(fechas))


def _turnos_disponibles(df):
    turnos = []
    for columna in [COLUMNA_TURNO, "Turno de Inicio", "Finalizar Turno"]:
        if columna not in df.columns:
            continue
        turnos.extend(df[columna].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].tolist())
    return sorted(set(turnos))


def _profundidades(df):
    if COLUMNA_PROFUNDIDAD not in df.columns:
        return {"cantidad": 0, "min": 0.0, "max": 0.0, "total": 0.0}
    serie = pd.to_numeric(df[COLUMNA_PROFUNDIDAD], errors="coerce").dropna()
    if serie.empty:
        return {"cantidad": 0, "min": 0.0, "max": 0.0, "total": 0.0}
    return {
        "cantidad": int(serie.count()),
        "min": round(float(serie.min()), 2),
        "max": round(float(serie.max()), 2),
        "total": round(float(serie.sum()), 2),
    }


def _reperforaciones(df):
    if COLUMNA_REPERFORACION not in df.columns:
        return {}
    return {
        str(clave): int(valor)
        for clave, valor in df[COLUMNA_REPERFORACION].fillna("").astype(str).str.strip().value_counts().to_dict().items()
    }


def diagnosticar_excel_ciclos(excel_path=None):
    df = leer_excel_ciclos(excel_path)
    codigos = []
    if COLUMNA_OPERADOR in df.columns:
        codigos = sorted(df[COLUMNA_OPERADOR].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].unique())
    return {
        "filas": int(len(df)),
        "columnas": list(df.columns),
        "codigos_unicos_operador": codigos,
        "equipos": _equipos_asociados(df),
        "fechas": _fechas_disponibles(df),
        "turnos": _turnos_disponibles(df),
        "profundidades": _profundidades(df),
        "reperforaciones": _reperforaciones(df),
    }


def _crear_tabla_fuentes(connection):
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
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS {quote_identifier('idx_fuentes_datos_tipo_activo')} "
        f"ON {quote_identifier(TABLA_FUENTES)} (tipo_fuente, activo)"
    )
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS {quote_identifier('idx_fuentes_datos_archivo')} "
        f"ON {quote_identifier(TABLA_FUENTES)} (archivo_origen)"
    )
    connection.commit()


def _rango_fechas_excel(df):
    if COLUMNA_FECHA not in df.columns:
        return "", ""
    fechas = pd.to_datetime(df[COLUMNA_FECHA], errors="coerce").dropna()
    if fechas.empty:
        return "", ""
    return fechas.min().strftime("%Y-%m-%d"), fechas.max().strftime("%Y-%m-%d")


def _nombre_fuente_desde_excel(path, df):
    fecha_min, fecha_max = _rango_fechas_excel(df)
    nombre_archivo = Path(path).stem if path else EXCEL_CICLOS_NOMBRE
    if fecha_min and fecha_min == fecha_max:
        return f"Ciclos de Perforacion Excel - {fecha_min.replace('-', '/')}"
    if fecha_min and fecha_max:
        inicio = pd.to_datetime(fecha_min)
        fin = pd.to_datetime(fecha_max)
        if inicio.year == fin.year and inicio.month == fin.month:
            meses = {
                1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
                5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
                9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
            }
            return f"Ciclos de Perforacion Excel - {meses[int(inicio.month)]} {int(inicio.year)}"
    return f"Ciclos de Perforacion Excel - {nombre_archivo}"


def _fuente_legacy(connection):
    _crear_tabla_fuentes(connection)
    fila = connection.execute(
        f"""
        SELECT id_fuente
        FROM {quote_identifier(TABLA_FUENTES)}
        WHERE tipo_fuente = 'excel_ciclos' AND archivo_origen = '__legacy_ciclos__'
        LIMIT 1
        """
    ).fetchone()
    if fila:
        return int(fila["id_fuente"] if isinstance(fila, sqlite3.Row) else fila[0])
    cursor = connection.execute(
        f"""
        INSERT INTO {quote_identifier(TABLA_FUENTES)}
        (nombre_fuente, tipo_fuente, archivo_origen, fecha_importacion, activo, observacion)
        VALUES ('Ciclos de Perforacion Excel - Legacy', 'excel_ciclos', '__legacy_ciclos__', CURRENT_TIMESTAMP, 1, 'Fuente creada al migrar ciclos existentes')
        """
    )
    connection.commit()
    return int(cursor.lastrowid)


def _obtener_o_crear_fuente(connection, *, excel_path, df_excel, nombre_fuente=None, observacion=""):
    _crear_tabla_fuentes(connection)
    path = Path(excel_path or ruta_excel_ciclos()).resolve()
    archivo_origen = str(path)
    existente = connection.execute(
        f"""
        SELECT id_fuente
        FROM {quote_identifier(TABLA_FUENTES)}
        WHERE tipo_fuente = 'excel_ciclos' AND archivo_origen = ?
        ORDER BY id_fuente DESC
        LIMIT 1
        """,
        (archivo_origen,),
    ).fetchone()
    fecha_min, fecha_max = _rango_fechas_excel(df_excel)
    nombre = nombre_fuente or _nombre_fuente_desde_excel(path, df_excel)
    if existente:
        id_fuente = int(existente["id_fuente"] if isinstance(existente, sqlite3.Row) else existente[0])
        connection.execute(
            f"""
            UPDATE {quote_identifier(TABLA_FUENTES)}
            SET nombre_fuente = ?,
                total_registros = ?,
                fecha_min = ?,
                fecha_max = ?,
                observacion = COALESCE(NULLIF(?, ''), observacion)
            WHERE id_fuente = ?
            """,
            (nombre, int(len(df_excel)), fecha_min, fecha_max, observacion, id_fuente),
        )
        return id_fuente

    cursor = connection.execute(
        f"""
        INSERT INTO {quote_identifier(TABLA_FUENTES)}
        (nombre_fuente, tipo_fuente, archivo_origen, fecha_importacion, total_registros, fecha_min, fecha_max, activo, observacion)
        VALUES (?, 'excel_ciclos', ?, CURRENT_TIMESTAMP, ?, ?, ?, 1, ?)
        """,
        (nombre, archivo_origen, int(len(df_excel)), fecha_min, fecha_max, observacion),
    )
    return int(cursor.lastrowid)


def _crear_tabla_ciclos(connection, columnas_excel):
    _crear_tabla_fuentes(connection)
    if TABLA_CICLOS in _tablas(connection):
        info = connection.execute(f"PRAGMA table_info({quote_identifier(TABLA_CICLOS)})").fetchall()
        ident_pk = False
        for fila in info:
            nombre = fila["name"] if isinstance(fila, sqlite3.Row) else fila[1]
            pk = fila["pk"] if isinstance(fila, sqlite3.Row) else fila[5]
            if nombre == "ident_registro" and int(pk or 0) > 0:
                ident_pk = True
                break
        if ident_pk:
            id_legacy = _fuente_legacy(connection)
            columnas_existentes = _columnas_tabla(connection, TABLA_CICLOS)
            tabla_tmp = f"{TABLA_CICLOS}_migracion_fuentes"
            connection.execute(f"DROP TABLE IF EXISTS {quote_identifier(tabla_tmp)}")
            columnas_tmp = [
                "id INTEGER PRIMARY KEY AUTOINCREMENT",
                "id_fuente INTEGER NOT NULL",
                "ident_registro TEXT NOT NULL",
                "raw_json TEXT",
                "operador_codigo_original TEXT",
                "operador_codigo_normalizado TEXT",
                "operador_nombre TEXT",
                "operador_display TEXT",
                "operador_pendiente INTEGER DEFAULT 0",
                "fecha_turno TEXT",
                "equipo TEXT",
                "turno TEXT",
                "imported_at TEXT DEFAULT CURRENT_TIMESTAMP",
                "updated_at TEXT",
            ]
            for columna in columnas_existentes:
                if columna not in {item.split()[0] for item in columnas_tmp}:
                    columnas_tmp.append(f"{quote_identifier(columna)} TEXT")
            for columna in columnas_excel:
                if columna not in columnas_existentes:
                    columnas_tmp.append(f"{quote_identifier(columna)} TEXT")
            connection.execute(
                f"CREATE TABLE {quote_identifier(tabla_tmp)} ({', '.join(columnas_tmp)})"
            )
            columnas_copiables = [col for col in columnas_existentes if col != "id_fuente"]
            destino = ["id_fuente", *columnas_copiables]
            origen = ["?", *[quote_identifier(col) for col in columnas_copiables]]
            connection.execute(
                f"""
                INSERT INTO {quote_identifier(tabla_tmp)}
                ({", ".join(quote_identifier(col) for col in destino)})
                SELECT {", ".join(origen)}
                FROM {quote_identifier(TABLA_CICLOS)}
                """,
                (id_legacy,),
            )
            connection.execute(f"DROP TABLE {quote_identifier(TABLA_CICLOS)}")
            connection.execute(f"ALTER TABLE {quote_identifier(tabla_tmp)} RENAME TO {quote_identifier(TABLA_CICLOS)}")

    columnas_sql = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "id_fuente INTEGER NOT NULL",
        "ident_registro TEXT NOT NULL",
        "raw_json TEXT",
        "operador_codigo_original TEXT",
        "operador_codigo_normalizado TEXT",
        "operador_nombre TEXT",
        "operador_display TEXT",
        "operador_pendiente INTEGER DEFAULT 0",
        "fecha_turno TEXT",
        "equipo TEXT",
        "turno TEXT",
        "imported_at TEXT DEFAULT CURRENT_TIMESTAMP",
        "updated_at TEXT",
    ]
    for columna in columnas_excel:
        columnas_sql.append(f"{quote_identifier(columna)} TEXT")
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quote_identifier(TABLA_CICLOS)} (
            {", ".join(columnas_sql)}
        )
        """
    )
    existentes = set(_columnas_tabla(connection, TABLA_CICLOS))
    for columna in columnas_excel:
        if columna not in existentes:
            connection.execute(
                f"ALTER TABLE {quote_identifier(TABLA_CICLOS)} ADD COLUMN {quote_identifier(columna)} TEXT"
            )
    for columna, definicion in [
        ("id_fuente", "INTEGER"),
        ("operador_codigo_original", "TEXT"),
        ("operador_codigo_normalizado", "TEXT"),
        ("operador_nombre", "TEXT"),
        ("operador_display", "TEXT"),
        ("operador_pendiente", "INTEGER DEFAULT 0"),
        ("fecha_turno", "TEXT"),
        ("equipo", "TEXT"),
        ("turno", "TEXT"),
        ("updated_at", "TEXT"),
    ]:
        if columna not in existentes:
            connection.execute(
                f"ALTER TABLE {quote_identifier(TABLA_CICLOS)} ADD COLUMN {quote_identifier(columna)} {definicion}"
            )
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS {quote_identifier('idx_ciclos_id_fuente')} "
        f"ON {quote_identifier(TABLA_CICLOS)} ({quote_identifier('id_fuente')})"
    )
    connection.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {quote_identifier('uq_ciclos_ident_fuente')} "
        f"ON {quote_identifier(TABLA_CICLOS)} ({quote_identifier('ident_registro')}, {quote_identifier('id_fuente')})"
    )
    connection.commit()


def _agregar_columnas_operador(df, mapa_operadores):
    resultado = df.copy()
    original = resultado.get(COLUMNA_OPERADOR, pd.Series([""] * len(resultado), index=resultado.index)).map(_texto)
    normalizado = original.map(normalizar_codigo_operador)
    nombres = normalizado.map(lambda codigo: mapa_operadores.get(codigo, "") if codigo else "")
    fechas = pd.to_datetime(resultado.get(COLUMNA_FECHA, pd.Series([""] * len(resultado), index=resultado.index)), errors="coerce")
    resultado["operador_codigo_original"] = original
    resultado["operador_codigo_normalizado"] = normalizado
    resultado["operador_nombre"] = nombres
    resultado["operador_display"] = [
        nombre if nombre else _display_codigo_pendiente(codigo_original)
        for nombre, codigo_original in zip(nombres, original)
    ]
    resultado["operador_pendiente"] = [
        1 if codigo_original and not nombre else 0
        for nombre, codigo_original in zip(nombres, original)
    ]
    resultado["fecha_turno"] = fechas.dt.strftime("%Y-%m-%d").fillna("")
    resultado["equipo"] = resultado.get(COLUMNA_EQUIPO, pd.Series([""] * len(resultado), index=resultado.index)).map(_texto)
    resultado["turno"] = resultado.get(COLUMNA_TURNO, pd.Series([""] * len(resultado), index=resultado.index)).map(_texto)
    return resultado


def generar_operadores_pendientes(df, csv_path=OPERADORES_PENDIENTES_CSV):
    pendientes = df[
        df["operador_pendiente"].astype(int).eq(1)
        & df["operador_codigo_normalizado"].astype(str).str.strip().ne("")
    ].copy()
    filas = []
    if not pendientes.empty:
        agrupado = pendientes.groupby(["operador_codigo_original", "operador_codigo_normalizado"], dropna=False)
        for (original, normalizado), grupo in agrupado:
            filas.append(
                {
                    "codigo_original": original,
                    "codigo_normalizado": normalizado,
                    "registros": int(len(grupo)),
                    "observacion": "operador pendiente de identificar",
                }
            )
    with Path(csv_path).open("w", newline="", encoding="utf-8-sig") as archivo:
        writer = csv.DictWriter(
            archivo,
            fieldnames=["codigo_original", "codigo_normalizado", "registros", "observacion"],
        )
        writer.writeheader()
        writer.writerows(filas)
    return filas


def importar_excel_ciclos(db_path=DATABASE_PATH, excel_path=None, nombre_fuente=None, observacion=""):
    df_excel = leer_excel_ciclos(excel_path)
    with closing(sqlite3.connect(Path(db_path))) as connection:
        connection.row_factory = sqlite3.Row
        mapa = cargar_mapa_operadores(connection=connection)
        df = _agregar_columnas_operador(df_excel, mapa)
        _crear_tabla_ciclos(connection, list(df_excel.columns))
        id_fuente = _obtener_o_crear_fuente(
            connection,
            excel_path=excel_path,
            df_excel=df_excel,
            nombre_fuente=nombre_fuente,
            observacion=observacion,
        )

        columnas_insert = [
            "id_fuente",
            "ident_registro",
            "raw_json",
            "operador_codigo_original",
            "operador_codigo_normalizado",
            "operador_nombre",
            "operador_display",
            "operador_pendiente",
            "fecha_turno",
            "equipo",
            "turno",
            *list(df_excel.columns),
        ]
        placeholders = ", ".join("?" for _ in columnas_insert)
        columnas_sql = ", ".join(quote_identifier(col) for col in columnas_insert)
        insert_sql = (
            f"INSERT OR IGNORE INTO {quote_identifier(TABLA_CICLOS)} "
            f"({columnas_sql}) VALUES ({placeholders})"
        )
        importadas = 0
        for _, fila in df.iterrows():
            ident = _texto(fila[COLUMNA_IDENT])
            raw = {columna: _texto(fila.get(columna, "")) for columna in df_excel.columns}
            valores = [
                id_fuente,
                ident,
                json.dumps(raw, ensure_ascii=False),
                _texto(fila["operador_codigo_original"]),
                _texto(fila["operador_codigo_normalizado"]),
                _texto(fila["operador_nombre"]),
                _texto(fila["operador_display"]),
                int(fila["operador_pendiente"]),
                _texto(fila["fecha_turno"]),
                _texto(fila["equipo"]),
                _texto(fila["turno"]),
                *[_texto(fila.get(columna, "")) for columna in df_excel.columns],
            ]
            cursor = connection.execute(insert_sql, valores)
            importadas += int(cursor.rowcount or 0)
        connection.commit()

    pendientes = generar_operadores_pendientes(df)
    return {
        "id_fuente": int(id_fuente) if "id_fuente" in locals() else None,
        "filas_excel": int(len(df_excel)),
        "filas_importadas": int(importadas),
        "duplicados_omitidos": int(len(df_excel) - importadas),
        "codigos_unicos_detectados": int(df["operador_codigo_normalizado"].replace("", pd.NA).dropna().nunique()),
        "operadores_con_nombre": int(df.loc[df["operador_nombre"].astype(str).str.strip().ne(""), "operador_codigo_normalizado"].nunique()),
        "operadores_pendientes": int(len(pendientes)),
        "pendientes_csv": str(OPERADORES_PENDIENTES_CSV),
    }


def recalcular_operadores_ciclos(db_path=DATABASE_PATH):
    df_ciclos = leer_ciclos(db_path=db_path)
    if df_ciclos.empty:
        return {
            "registros_actualizados": 0,
            "codigos_unicos_detectados": 0,
            "operadores_con_nombre": 0,
            "operadores_pendientes": 0,
        }

    with closing(sqlite3.connect(Path(db_path))) as connection:
        connection.row_factory = sqlite3.Row
        _crear_tabla_ciclos(connection, [columna for columna in df_ciclos.columns if columna not in {
            "id",
            "id_fuente",
            "ident_registro",
            "raw_json",
            "operador_codigo_original",
            "operador_codigo_normalizado",
            "operador_nombre",
            "operador_display",
            "operador_pendiente",
            "fecha_turno",
            "equipo",
            "turno",
            "imported_at",
            "updated_at",
            "nombre_fuente",
            "fuente_activa",
        }])
        df_ciclos = leer_ciclos(db_path=db_path)
        mapa = cargar_mapa_operadores(connection=connection)
        df = _agregar_columnas_operador(df_ciclos, mapa)
        for _, fila in df.iterrows():
            connection.execute(
                f"""
                UPDATE {quote_identifier(TABLA_CICLOS)}
                SET operador_codigo_original = ?,
                    operador_codigo_normalizado = ?,
                    operador_nombre = ?,
                    operador_display = ?,
                    operador_pendiente = ?,
                    fecha_turno = ?,
                    equipo = ?,
                    turno = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    _texto(fila["operador_codigo_original"]),
                    _texto(fila["operador_codigo_normalizado"]),
                    _texto(fila["operador_nombre"]),
                    _texto(fila["operador_display"]),
                    int(fila["operador_pendiente"]),
                    _texto(fila["fecha_turno"]),
                    _texto(fila["equipo"]),
                    _texto(fila["turno"]),
                    int(fila["id"]) if "id" in df.columns else None,
                ),
            )
        connection.commit()

    pendientes = generar_operadores_pendientes(df)
    return {
        "registros_actualizados": int(len(df)),
        "codigos_unicos_detectados": int(df["operador_codigo_normalizado"].replace("", pd.NA).dropna().nunique()),
        "operadores_con_nombre": int(df.loc[df["operador_nombre"].astype(str).str.strip().ne(""), "operador_codigo_normalizado"].nunique()),
        "operadores_pendientes": int(len(pendientes)),
    }


def sincronizar_operadores_ciclos(db_path=DATABASE_PATH):
    return recalcular_operadores_ciclos(db_path=db_path)


def listar_fuentes_datos(db_path=DATABASE_PATH, solo_activas=False):
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame(columns=[
            "id_fuente",
            "nombre_fuente",
            "tipo_fuente",
            "archivo_origen",
            "fecha_importacion",
            "total_registros",
            "fecha_min",
            "fecha_max",
            "activo",
            "observacion",
        ])
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        _crear_tabla_fuentes(connection)
        sql = f"SELECT * FROM {quote_identifier(TABLA_FUENTES)} WHERE tipo_fuente = 'excel_ciclos'"
        if solo_activas:
            sql += " AND activo = 1"
        sql += " ORDER BY fecha_importacion DESC, id_fuente DESC"
        return pd.read_sql_query(sql, connection)


def actualizar_estado_fuente(id_fuente, activo, db_path=DATABASE_PATH):
    with closing(sqlite3.connect(Path(db_path))) as connection:
        _crear_tabla_fuentes(connection)
        cursor = connection.execute(
            f"UPDATE {quote_identifier(TABLA_FUENTES)} SET activo = ? WHERE id_fuente = ?",
            (1 if activo else 0, int(id_fuente)),
        )
        connection.commit()
        return int(cursor.rowcount or 0)


def eliminar_fuente(id_fuente, db_path=DATABASE_PATH):
    with closing(sqlite3.connect(Path(db_path))) as connection:
        connection.row_factory = sqlite3.Row
        _crear_tabla_fuentes(connection)
        if TABLA_CICLOS in _tablas(connection):
            ciclos = connection.execute(
                f"DELETE FROM {quote_identifier(TABLA_CICLOS)} WHERE id_fuente = ?",
                (int(id_fuente),),
            ).rowcount
        else:
            ciclos = 0
        fuentes = connection.execute(
            f"DELETE FROM {quote_identifier(TABLA_FUENTES)} WHERE id_fuente = ?",
            (int(id_fuente),),
        ).rowcount
        connection.commit()
    recalcular_operadores_ciclos(db_path=db_path)
    return {"fuentes_eliminadas": int(fuentes or 0), "ciclos_eliminados": int(ciclos or 0)}


def resumen_fuentes_excel(db_path=DATABASE_PATH):
    fuentes = listar_fuentes_datos(db_path=db_path)
    if fuentes.empty:
        return fuentes
    df = fuentes.copy()
    df["estado"] = df["activo"].astype(int).map({1: "Activa", 0: "Inactiva"}).fillna("Inactiva")
    return df[[
        "id_fuente",
        "nombre_fuente",
        "archivo_origen",
        "fecha_importacion",
        "fecha_min",
        "fecha_max",
        "total_registros",
        "estado",
        "observacion",
    ]]


def resumen_operacional_por_fuente(id_fuente, db_path=DATABASE_PATH):
    df = leer_ciclos_operacional(db_path=db_path, id_fuente=id_fuente)
    if df.empty:
        return {
            "id_fuente": id_fuente,
            "registros": 0,
            "metros": 0.0,
            "reperforaciones": 0,
            "fecha_min": "",
            "fecha_max": "",
            "equipos": 0,
            "operadores": 0,
        }
    fechas = pd.to_datetime(df["Fecha turno"], errors="coerce").dropna()
    metros = pd.to_numeric(df["Metros perforados"], errors="coerce").fillna(0)
    return {
        "id_fuente": id_fuente,
        "registros": int(len(df)),
        "metros": round(float(metros.sum()), 2),
        "reperforaciones": int(pd.to_numeric(df.get("Reperforaciones", 0), errors="coerce").fillna(0).sum()),
        "fecha_min": fechas.min().strftime("%Y-%m-%d") if not fechas.empty else "",
        "fecha_max": fechas.max().strftime("%Y-%m-%d") if not fechas.empty else "",
        "equipos": int(df["Equipo"].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].nunique()),
        "operadores": int(df["operador_display"].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].nunique()),
    }


def comparar_fuentes(id_fuente_actual, id_fuente_anterior, db_path=DATABASE_PATH):
    actual = leer_ciclos_operacional(db_path=db_path, id_fuente=id_fuente_actual)
    anterior = leer_ciclos_operacional(db_path=db_path, id_fuente=id_fuente_anterior)

    def agrupar(df, columna):
        if df.empty:
            return pd.DataFrame(columns=[columna, "metros", "registros", "reperforaciones"])
        base = df.copy()
        base["Metros perforados"] = pd.to_numeric(base["Metros perforados"], errors="coerce").fillna(0)
        base["Reperforaciones"] = pd.to_numeric(base["Reperforaciones"], errors="coerce").fillna(0)
        return base.groupby(columna, as_index=False).agg(
            metros=("Metros perforados", "sum"),
            registros=("Fuente de datos", "count"),
            reperforaciones=("Reperforaciones", "sum"),
        )

    def comparar_tabla(columna):
        act = agrupar(actual, columna).rename(columns={
            "metros": "metros_actual",
            "registros": "registros_actual",
            "reperforaciones": "reperforaciones_actual",
        })
        ant = agrupar(anterior, columna).rename(columns={
            "metros": "metros_anterior",
            "registros": "registros_anterior",
            "reperforaciones": "reperforaciones_anterior",
        })
        combinado = act.merge(ant, on=columna, how="outer").fillna(0)
        combinado["delta_metros"] = combinado["metros_actual"] - combinado["metros_anterior"]
        return combinado.sort_values("delta_metros", ascending=False).reset_index(drop=True)

    return {
        "resumen_actual": resumen_operacional_por_fuente(id_fuente_actual, db_path=db_path),
        "resumen_anterior": resumen_operacional_por_fuente(id_fuente_anterior, db_path=db_path),
        "metros_por_equipo": comparar_tabla("Equipo"),
        "metros_por_operador": comparar_tabla("operador_display"),
    }


def leer_ciclos(db_path=DATABASE_PATH, id_fuente=None, solo_activas=False):
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame()
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        if TABLA_CICLOS not in _tablas(connection):
            return pd.DataFrame()
        _crear_tabla_ciclos(connection, [])
        sql = f"""
            SELECT c.*, f.nombre_fuente, f.activo AS fuente_activa
            FROM {quote_identifier(TABLA_CICLOS)} c
            LEFT JOIN {quote_identifier(TABLA_FUENTES)} f ON f.id_fuente = c.id_fuente
        """
        condiciones = []
        params = []
        if id_fuente is not None:
            condiciones.append("c.id_fuente = ?")
            params.append(int(id_fuente))
        if solo_activas:
            condiciones.append("COALESCE(f.activo, 1) = 1")
        if condiciones:
            sql += " WHERE " + " AND ".join(condiciones)
        df = pd.read_sql_query(sql, connection, params=params)
        return df.loc[:, ~df.columns.duplicated(keep="last")]


def ciclos_a_dataframe_operacional(df_ciclos):
    if df_ciclos is None or df_ciclos.empty:
        return pd.DataFrame()
    df = df_ciclos.copy()
    fecha = pd.to_datetime(df.get(COLUMNA_FECHA), errors="coerce").dt.date
    profundidad = pd.to_numeric(df.get(COLUMNA_PROFUNDIDAD), errors="coerce").fillna(0)
    reperforacion = df.get(COLUMNA_REPERFORACION, pd.Series([""] * len(df), index=df.index)).fillna("").astype(str).str.strip().str.upper()
    equipo = df.get(COLUMNA_EQUIPO, pd.Series([""] * len(df), index=df.index)).fillna("").astype(str).str.strip()
    turno = df.get(COLUMNA_TURNO, pd.Series([""] * len(df), index=df.index)).fillna("").astype(str).str.strip()
    operador = df.get("operador_display", pd.Series([""] * len(df), index=df.index)).fillna("").astype(str).str.strip()
    codigo_original = df.get("operador_codigo_original", pd.Series([""] * len(df), index=df.index)).fillna("").astype(str).str.strip()
    fuente = df.get(
        "nombre_fuente",
        pd.Series(["Ciclos de Perforacion Excel"] * len(df), index=df.index),
    ).fillna("Ciclos de Perforacion Excel")

    resultado = pd.DataFrame(
        {
            "Fuente de datos": "Ciclos de Perforación Excel",
            "id_fuente": df.get("id_fuente", ""),
            "Fuente de datos": fuente,
            "Fecha turno": fecha,
            "Modelo equipo": "Ciclos Excel",
            "Número equipo": equipo.str.replace("PE", "", regex=False),
            "Equipo": equipo,
            "Operador": operador,
            "Código operador": codigo_original,
            "Turno": turno,
            "Banco": df.get("Ubicación de Perforación", ""),
            "Malla": "",
            "Fase": "",
            "Pozo Perforación": df.get(COLUMNA_POZO, ""),
            "Metros perforados": profundidad,
            "Pozos perforados turno": 1,
            "Horas efectivas perforando": 0.0,
            "Horas detención mecánica": 0.0,
            "Horas detención No efectivas": 0.0,
            "Disponibilidad %": 0.0,
            "Utilización": 0.0,
            "Rendimiento m/h": 0.0,
            "Es Reperforación": reperforacion,
            "Reperforaciones": reperforacion.eq("Y").astype(int),
            "operador_codigo_original": df.get("operador_codigo_original", ""),
            "operador_codigo_normalizado": df.get("operador_codigo_normalizado", ""),
            "operador_nombre": df.get("operador_nombre", ""),
            "operador_display": df.get("operador_display", ""),
        }
    )
    return resultado.reset_index(drop=True)


def leer_ciclos_operacional(db_path=DATABASE_PATH, id_fuente=None, solo_activas=False):
    return ciclos_a_dataframe_operacional(
        leer_ciclos(db_path=db_path, id_fuente=id_fuente, solo_activas=solo_activas)
    )


def obtener_opciones_filtros_ciclos(db_path=DATABASE_PATH):
    path = Path(db_path)
    if not path.exists():
        return {"operadores": [], "equipos": [], "turnos": [], "fechas": []}

    def consultar(connection, columna):
        try:
            filas = connection.execute(
                f"""
                SELECT DISTINCT {quote_identifier(columna)}
                FROM {quote_identifier(TABLA_CICLOS)}
                WHERE TRIM(COALESCE({quote_identifier(columna)}, '')) <> ''
                ORDER BY {quote_identifier(columna)}
                """
            ).fetchall()
        except sqlite3.Error:
            return []
        return [str(fila[0]).strip() for fila in filas if str(fila[0] or "").strip()]

    with closing(sqlite3.connect(path)) as connection:
        tablas = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if TABLA_CICLOS not in tablas:
            return {"operadores": [], "equipos": [], "turnos": [], "fechas": []}
        return {
            "operadores": consultar(connection, "operador_display"),
            "equipos": consultar(connection, "equipo"),
            "turnos": consultar(connection, "turno"),
            "fechas": consultar(connection, "fecha_turno"),
        }


def _filtrar_mes_ciclos(anio, mes, db_path=DATABASE_PATH, id_fuente=None, solo_activas=False):
    df = leer_ciclos_operacional(db_path=db_path, id_fuente=id_fuente, solo_activas=solo_activas)
    if df.empty or "Fecha turno" not in df.columns:
        return pd.DataFrame()
    fechas = pd.to_datetime(df["Fecha turno"], errors="coerce")
    return df[(fechas.dt.year == int(anio)) & (fechas.dt.month == int(mes))].copy()


def obtener_resumen_mensual_ciclos(anio, mes, db_path=DATABASE_PATH, id_fuente=None, solo_activas=False):
    ultimo = monthrange(int(anio), int(mes))[1]
    df = _filtrar_mes_ciclos(anio, mes, db_path=db_path, id_fuente=id_fuente, solo_activas=solo_activas)
    if df.empty:
        return {
            "anio": int(anio),
            "mes": int(mes),
            "fecha_inicio": f"{int(anio):04d}-{int(mes):02d}-01",
            "fecha_fin": f"{int(anio):04d}-{int(mes):02d}-{ultimo:02d}",
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
    metros = pd.to_numeric(df["Metros perforados"], errors="coerce").fillna(0)
    return {
        "anio": int(anio),
        "mes": int(mes),
        "fecha_inicio": f"{int(anio):04d}-{int(mes):02d}-01",
        "fecha_fin": f"{int(anio):04d}-{int(mes):02d}-{ultimo:02d}",
        "cantidad_registros": int(len(df)),
        "metros_totales": round(float(metros.sum()), 2),
        "horas_efectivas_totales": 0.0,
        "horas_no_efectivas_totales": 0.0,
        "horas_averias_totales": 0.0,
        "disponibilidad_promedio": 0.0,
        "utilizacion_promedio": 0.0,
        "rendimiento_promedio": 0.0,
        "equipos_distintos": int(df["Equipo"].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].nunique()),
        "operadores_distintos": int(df["operador_display"].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].nunique()),
    }


def obtener_ranking_equipos_mensual_ciclos(anio, mes, db_path=DATABASE_PATH, id_fuente=None, solo_activas=False):
    df = _filtrar_mes_ciclos(anio, mes, db_path=db_path, id_fuente=id_fuente, solo_activas=solo_activas)
    columnas = [
        "numero_equipo",
        "metros_totales",
        "horas_efectivas_totales",
        "horas_no_efectivas_totales",
        "horas_averias_totales",
        "disponibilidad_promedio",
        "utilizacion_promedio",
        "rendimiento_promedio",
        "cantidad_registros",
    ]
    if df.empty:
        return pd.DataFrame(columns=columnas)
    base = df.copy()
    base["Metros perforados"] = pd.to_numeric(base["Metros perforados"], errors="coerce").fillna(0)
    ranking = base.groupby("Equipo", as_index=False).agg({"Metros perforados": "sum", "Fuente de datos": "count"})
    ranking = ranking.rename(columns={"Equipo": "numero_equipo", "Metros perforados": "metros_totales", "Fuente de datos": "cantidad_registros"})
    ranking["horas_efectivas_totales"] = 0.0
    ranking["horas_no_efectivas_totales"] = 0.0
    ranking["horas_averias_totales"] = 0.0
    ranking["disponibilidad_promedio"] = 0.0
    ranking["utilizacion_promedio"] = 0.0
    ranking["rendimiento_promedio"] = 0.0
    return ranking[columnas].round(2).sort_values("metros_totales", ascending=False).reset_index(drop=True)


def obtener_ranking_operadores_mensual_ciclos(anio, mes, db_path=DATABASE_PATH, id_fuente=None, solo_activas=False):
    df = _filtrar_mes_ciclos(anio, mes, db_path=db_path, id_fuente=id_fuente, solo_activas=solo_activas)
    columnas = [
        "operador",
        "metros_totales",
        "horas_efectivas_totales",
        "horas_no_efectivas_totales",
        "horas_averias_totales",
        "disponibilidad_promedio",
        "utilizacion_promedio",
        "rendimiento_promedio",
        "cantidad_registros",
    ]
    if df.empty:
        return pd.DataFrame(columns=columnas)
    base = df.copy()
    base["Metros perforados"] = pd.to_numeric(base["Metros perforados"], errors="coerce").fillna(0)
    ranking = base.groupby("operador_display", as_index=False).agg({"Metros perforados": "sum", "Fuente de datos": "count"})
    ranking = ranking.rename(columns={"operador_display": "operador", "Metros perforados": "metros_totales", "Fuente de datos": "cantidad_registros"})
    ranking["horas_efectivas_totales"] = 0.0
    ranking["horas_no_efectivas_totales"] = 0.0
    ranking["horas_averias_totales"] = 0.0
    ranking["disponibilidad_promedio"] = 0.0
    ranking["utilizacion_promedio"] = 0.0
    ranking["rendimiento_promedio"] = 0.0
    return ranking[columnas].round(2).sort_values("metros_totales", ascending=False).reset_index(drop=True)
