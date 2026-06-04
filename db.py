from datetime import datetime
from pathlib import Path
import shutil
import sqlite3

import pandas as pd

from runtime_cache import cache_data, cache_resource

from config import BACKUP_DIR, BACKUPS_SQLITE_DIR, BASE_DIR, DATABASE_PATH
from schema import alias_columna
from services.alert_service import evaluar_alertas_operacionales
from metrics import calcular_disponibilidad, calcular_kpis_consolidados_dataframe, calcular_utilizacion
from services.kpi_service import estado_operacional_equipo
from operators import asegurar_tabla_operadores, upsert_operadores_conocidos
from utils import EQUIPOS, EXCEL_PATH, HORAS_TURNO, OPERADORES, limpiar_entero


DB_PATH = DATABASE_PATH
TABLA_REGISTROS = "registros_perforacion"
TABLA_AUDITORIA_EDICIONES = "auditoria_ediciones"
TECHNICAL_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "created_at": "TEXT",
    "updated_at": "TEXT",
    "source": "TEXT",
    "source_row": "INTEGER",
}

AUDITORIA_EDICIONES_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "registro_id": "INTEGER NOT NULL",
    "changed_at": "TEXT NOT NULL",
    "campo": "TEXT NOT NULL",
    "valor_anterior": "TEXT",
    "valor_nuevo": "TEXT",
    "motivo": "TEXT NOT NULL",
    "usuario": "TEXT",
}

INDEXES_REGISTROS = [
    ("idx_registros_fecha_turno", ["Fecha turno"]),
    ("idx_registros_turno", ["Turno"]),
    ("idx_registros_numero_equipo", ["Número equipo"]),
    ("idx_registros_operador", ["Operador"]),
    ("idx_registros_banco", ["Banco"]),
    ("idx_registros_malla", ["Malla"]),
    ("idx_registros_fecha_turno_turno_equipo_operador", ["Fecha turno", "Turno", "Número equipo", "Operador"]),
]


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        resultado = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return resultado


def quote_identifier(identifier):
    return '"' + str(identifier).replace('"', '""') + '"'


def conectar_db(db_path=DB_PATH):
    connection = sqlite3.connect(Path(db_path), timeout=30, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    return connection


def get_connection(db_path=DB_PATH):
    return conectar_db(db_path)


def _archivo_mtime(ruta):
    path = Path(ruta)
    return path.stat().st_mtime if path.exists() else 0


def limpiar_cache_consultas():
    leer_registros.clear()
    consultar_historial_filtrado.clear()
    consultar_registros_edicion.clear()
    obtener_rango_fechas.clear()
    contar_historial_filtrado.clear()
    obtener_valores_distintos_columna.clear()
    consultar_alertas_operacionales_filtradas.clear()
    consultar_resumen_operadores_filtrado.clear()
    consultar_resumen_operacional_equipos_filtrado.clear()
    consultar_resumen_aceros_filtrado.clear()
    contar_registros.clear()
    contar_duplicados_operacionales.clear()
    existe_registro_duplicado.clear()


def crear_tablas(db_path=DB_PATH, columnas=None):
    columnas = [alias_columna(columna) for columna in list(columnas or [])]
    if not columnas:
        return _asegurar_tablas_base_cached(str(Path(db_path).resolve()), _archivo_mtime(db_path))
    with conectar_db(db_path) as connection:
        columnas_sql = [
            f"{quote_identifier(columna)} {tipo}"
            for columna, tipo in TECHNICAL_COLUMNS.items()
        ]
        columnas_sql.extend(
            f"{quote_identifier(columna)} TEXT"
            for columna in columnas
            if columna not in TECHNICAL_COLUMNS
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {quote_identifier(TABLA_REGISTROS)} (
                {", ".join(columnas_sql)}
            )
            """
        )
        connection.commit()
        normalizar_esquema_columnas(connection)
        asegurar_columnas(connection, columnas)
        asegurar_indices(connection)
        crear_tabla_auditoria_ediciones(connection)
        upsert_operadores_conocidos(connection)


@cache_resource
def _asegurar_tablas_base_cached(db_path_text, mtime):
    with conectar_db(db_path_text) as connection:
        columnas_sql = [
            f"{quote_identifier(columna)} {tipo}"
            for columna, tipo in TECHNICAL_COLUMNS.items()
        ]
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {quote_identifier(TABLA_REGISTROS)} (
                {", ".join(columnas_sql)}
            )
            """
        )
        connection.commit()
        normalizar_esquema_columnas(connection)
        asegurar_indices(connection)
        crear_tabla_auditoria_ediciones(connection)
        upsert_operadores_conocidos(connection)


def crear_tablas_si_no_existen(db_path=DB_PATH):
    crear_tablas(db_path=db_path)


def crear_tabla_operadores(connection):
    asegurar_tabla_operadores(connection)


def crear_tabla_auditoria_ediciones(connection):
    columnas_sql = [
        f"{quote_identifier(columna)} {tipo}"
        for columna, tipo in AUDITORIA_EDICIONES_COLUMNS.items()
    ]
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quote_identifier(TABLA_AUDITORIA_EDICIONES)} (
            {", ".join(columnas_sql)}
        )
        """
    )
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS {quote_identifier('idx_auditoria_ediciones_registro_id')} "
        f"ON {quote_identifier(TABLA_AUDITORIA_EDICIONES)} ({quote_identifier('registro_id')})"
    )
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS {quote_identifier('idx_auditoria_ediciones_changed_at')} "
        f"ON {quote_identifier(TABLA_AUDITORIA_EDICIONES)} ({quote_identifier('changed_at')})"
    )
    connection.commit()


def columnas_tabla(connection, tabla=TABLA_REGISTROS):
    try:
        filas = connection.execute(f"PRAGMA table_info({quote_identifier(tabla)})").fetchall()
    except sqlite3.OperationalError:
        return []
    return [fila["name"] for fila in filas]


def _ruta_sqlite_connection(connection):
    try:
        filas = connection.execute("PRAGMA database_list").fetchall()
    except sqlite3.DatabaseError:
        return None
    for fila in filas:
        if fila["name"] == "main" and fila["file"]:
            return Path(fila["file"])
    return None


def ruta_respaldo_migracion_sqlite(db_path, backup_dir=None):
    db_path = Path(db_path)
    backup_dir = Path(backup_dir or BACKUPS_SQLITE_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return backup_dir / f"{db_path.stem}_pre_schema_migration_{timestamp}{db_path.suffix}"


def respaldar_sqlite_pre_migracion(connection, backup_dir=None):
    db_path = _ruta_sqlite_connection(connection)
    if db_path is None or not db_path.exists():
        return None
    connection.commit()
    destino = ruta_respaldo_migracion_sqlite(db_path, backup_dir=backup_dir)
    shutil.copy2(db_path, destino)
    return destino


def normalizar_esquema_columnas(connection, tabla=TABLA_REGISTROS):
    columnas = columnas_tabla(connection, tabla)
    existentes = set(columnas)
    respaldo_creado = False
    for columna in columnas:
        if columna in TECHNICAL_COLUMNS:
            continue
        canonica = alias_columna(columna)
        if not canonica or canonica == columna:
            continue
        if not respaldo_creado:
            respaldar_sqlite_pre_migracion(connection)
            respaldo_creado = True
        if canonica not in existentes:
            connection.execute(
                f"ALTER TABLE {quote_identifier(tabla)} "
                f"RENAME COLUMN {quote_identifier(columna)} TO {quote_identifier(canonica)}"
            )
            existentes.discard(columna)
            existentes.add(canonica)
            continue

        connection.execute(
            f"""
            UPDATE {quote_identifier(tabla)}
            SET {quote_identifier(canonica)} = {quote_identifier(columna)}
            WHERE TRIM(COALESCE({quote_identifier(canonica)}, '')) = ''
              AND TRIM(COALESCE({quote_identifier(columna)}, '')) <> ''
            """
        )
        try:
            connection.execute(
                f"ALTER TABLE {quote_identifier(tabla)} DROP COLUMN {quote_identifier(columna)}"
            )
            existentes.discard(columna)
        except sqlite3.OperationalError:
            pass
    connection.commit()


def asegurar_columnas(connection, columnas, tabla=TABLA_REGISTROS):
    normalizar_esquema_columnas(connection, tabla)
    columnas = [alias_columna(columna) for columna in columnas]
    existentes = set(columnas_tabla(connection, tabla))
    for columna in columnas:
        if columna in TECHNICAL_COLUMNS or columna in existentes:
            continue
        connection.execute(
            f"ALTER TABLE {quote_identifier(tabla)} ADD COLUMN {quote_identifier(columna)} TEXT"
        )
        existentes.add(columna)
    connection.commit()


def asegurar_indices(connection, tabla=TABLA_REGISTROS):
    existentes = set(columnas_tabla(connection, tabla))
    for nombre_indice, columnas in INDEXES_REGISTROS:
        if all(columna in existentes for columna in columnas):
            columnas_sql = ", ".join(quote_identifier(columna) for columna in columnas)
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS {quote_identifier(nombre_indice)} "
                f"ON {quote_identifier(tabla)} ({columnas_sql})"
            )
    connection.commit()


def respaldar_excel_pre_sqlite(excel_path=EXCEL_PATH):
    path = Path(excel_path)
    if not path.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    destino = BACKUP_DIR / f"{path.stem}_pre_sqlite_{datetime.now().strftime('%Y%m%d_%H%M%S')}{path.suffix}"
    shutil.copy2(path, destino)
    return destino


def migrar_excel_a_sqlite(excel_path=EXCEL_PATH, db_path=DB_PATH):
    from data import preparar_dataframe

    excel_path = Path(excel_path)
    if not excel_path.exists():
        crear_tablas(db_path=db_path)
        return 0, None

    respaldo = respaldar_excel_pre_sqlite(excel_path)
    df = pd.read_excel(excel_path, engine="openpyxl")
    df = preparar_dataframe(df)
    registros = reemplazar_dataframe_reportes(df, db_path=db_path, source="excel_migration")
    limpiar_cache_consultas()
    return registros, respaldo


def insertar_registro(registro, db_path=DB_PATH, source="streamlit"):
    from data import preparar_dataframe

    if isinstance(registro, pd.Series):
        df = pd.DataFrame([registro.to_dict()])
    elif isinstance(registro, dict):
        df = pd.DataFrame([registro])
    elif isinstance(registro, pd.DataFrame):
        df = registro.copy()
    else:
        raise TypeError("registro debe ser dict, Series o DataFrame")

    df = preparar_dataframe(df)
    insertar_dataframe_reportes(df, db_path=db_path, source=source)
    return len(df)


@cache_data
def leer_registros(db_path=DB_PATH):
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame()

    with conectar_db(path) as connection:
        crear_tablas(db_path=path)
        columnas = columnas_tabla(connection)
        if not columnas:
            return pd.DataFrame()
        data_columns = [col for col in columnas if col not in TECHNICAL_COLUMNS]
        if not data_columns:
            return pd.DataFrame()
        columns_sql = ", ".join(quote_identifier(col) for col in data_columns)
        df = pd.read_sql_query(
            f"SELECT {columns_sql} FROM {quote_identifier(TABLA_REGISTROS)} ORDER BY id",
            connection,
        )

    from data import preparar_dataframe

    return preparar_dataframe(df)


def _normalizar_lista_filtro(valor):
    if valor is None:
        return []
    if isinstance(valor, (list, tuple, set, pd.Index, pd.Series)):
        valores = list(valor)
    else:
        valores = [valor]
    resultado = []
    for item in valores:
        texto = str(item).strip()
        if texto:
            resultado.append(texto)
    return resultado


def _primer_valor_no_vacio(*valores):
    for valor in valores:
        if valor is None:
            continue
        if isinstance(valor, str) and not valor.strip():
            continue
        if isinstance(valor, (list, tuple, set, pd.Index, pd.Series)) and not _normalizar_lista_filtro(valor):
            continue
        return valor
    return None


def _construir_clausula_filtro(columnas_existentes, valores, candidatos, *, modo="exacto"):
    valores = _normalizar_lista_filtro(valores)
    if not valores:
        return None

    columna = _resolver_columna_existente(columnas_existentes, *candidatos)
    if not columna:
        return None

    if modo == "contiene":
        subclausulas = [f"UPPER({quote_identifier(columna)}) LIKE UPPER(?)" for _ in valores]
        parametros = [f"%{valor}%" for valor in valores]
        return f"({ ' OR '.join(subclausulas) })", parametros

    placeholders = ", ".join("?" for _ in valores)
    return f"{quote_identifier(columna)} IN ({placeholders})", valores


def _separar_equipo_modelo_numero(valor):
    texto = str(valor).strip()
    if not texto:
        return "", ""
    if " " not in texto:
        return texto, ""
    modelo, numero = texto.rsplit(" ", 1)
    if numero.isdigit():
        return modelo.strip(), numero.strip()
    return texto, ""


def _construir_clausula_equipos(columnas_existentes, valores):
    valores = _normalizar_lista_filtro(valores)
    if not valores:
        return None

    columna_equipo = _resolver_columna_existente(columnas_existentes, "Equipo")
    columna_modelo = _resolver_columna_existente(columnas_existentes, "Modelo equipo")
    columna_numero = _resolver_columna_existente(columnas_existentes, "Número equipo")
    subclausulas = []
    parametros = []

    for valor in valores:
        texto = str(valor).strip()
        modelo, numero = _separar_equipo_modelo_numero(texto)
        clausulas_valor = []
        params_valor = []

        if columna_equipo:
            clausulas_valor.append(f"{quote_identifier(columna_equipo)} = ?")
            params_valor.append(texto)

        if columna_modelo and columna_numero and numero:
            clausulas_valor.append(
                f"({quote_identifier(columna_modelo)} = ? AND TRIM(COALESCE({quote_identifier(columna_numero)}, '')) = ?)"
            )
            params_valor.extend([modelo, numero])
        elif columna_modelo:
            clausulas_valor.append(f"{quote_identifier(columna_modelo)} = ?")
            params_valor.append(modelo)

        if clausulas_valor:
            subclausulas.append("(" + " OR ".join(clausulas_valor) + ")")
            parametros.extend(params_valor)

    if subclausulas:
        return "(" + " OR ".join(subclausulas) + ")", parametros

    return None


def _normalizar_filtros_busqueda(
    *,
    fecha_desde=None,
    fecha_hasta=None,
    fecha_inicio=None,
    fecha_fin=None,
    turno=None,
    turnos=None,
    equipo=None,
    equipos=None,
    operador=None,
    operadores=None,
    banco=None,
    malla=None,
    fase=None,
    tipo_perforacion=None,
    tipos_detencion=None,
    tipo_alerta=None,
):
    return {
        "fecha_desde": _primer_valor_no_vacio(fecha_desde, fecha_inicio),
        "fecha_hasta": _primer_valor_no_vacio(fecha_hasta, fecha_fin),
        "turno": _primer_valor_no_vacio(turno, turnos),
        "equipo": _primer_valor_no_vacio(equipo, equipos),
        "operador": _primer_valor_no_vacio(operador, operadores),
        "banco": banco,
        "malla": malla,
        "fase": fase,
        "tipo_perforacion": tipo_perforacion,
        "tipos_detencion": _primer_valor_no_vacio(tipos_detencion, tipo_alerta),
    }


def _resolver_columna_existente(columnas_existentes, *candidatos):
    for candidato in candidatos:
        if candidato in columnas_existentes:
            return candidato
    return None


def _construir_filtros_sql(
    columnas_existentes,
    fecha_desde=None,
    fecha_hasta=None,
    turno=None,
    equipo=None,
    operador=None,
    banco=None,
    malla=None,
    fase=None,
    tipo_perforacion=None,
    tipos_detencion=None,
):
    filtros = []
    parametros = []

    columna_fecha = _resolver_columna_existente(columnas_existentes, "Fecha turno", "Fecha")
    if fecha_desde is not None and columna_fecha:
        filtros.append(f"date({quote_identifier(columna_fecha)}) >= date(?)")
        parametros.append(_valor_busqueda_fecha(fecha_desde))
    if fecha_hasta is not None and columna_fecha:
        filtros.append(f"date({quote_identifier(columna_fecha)}) <= date(?)")
        parametros.append(_valor_busqueda_fecha(fecha_hasta))

    mapeo = [
        (turno, ["Turno"], "Turno", "exacto"),
        (operador, ["Operador"], "Operador", "exacto"),
        (banco, ["Banco"], "Banco", "exacto"),
        (malla, ["Malla"], "Malla", "exacto"),
        (fase, ["Fase"], "Fase", "exacto"),
        (tipo_perforacion, ["Tipo de perforación"], "Tipo de perforación", "exacto"),
        (tipos_detencion, ["Tipo detención"], "Tipo detención", "contiene"),
    ]
    for valor, candidatos, etiqueta, modo in mapeo:
        clause = _construir_clausula_filtro(columnas_existentes, valor, candidatos, modo=modo)
        if not clause:
            continue
        clausula_sql, params_clausula = clause
        filtros.append(clausula_sql)
        parametros.extend(params_clausula)

    clause_equipos = _construir_clausula_equipos(columnas_existentes, equipo)
    if clause_equipos:
        clausula_sql, params_clausula = clause_equipos
        filtros.append(clausula_sql)
        parametros.extend(params_clausula)

    if filtros:
        return " WHERE " + " AND ".join(filtros), parametros
    return "", parametros


@cache_data
def consultar_historial_filtrado(
    db_path=DB_PATH,
    fecha_desde=None,
    fecha_hasta=None,
    fecha_inicio=None,
    fecha_fin=None,
    turno=None,
    turnos=None,
    equipo=None,
    equipos=None,
    operador=None,
    operadores=None,
    banco=None,
    malla=None,
    fase=None,
    tipo_perforacion=None,
    tipos_detencion=None,
    limit=None,
    offset=None,
    **_filtros_extra,
):
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame()

    with conectar_db(path) as connection:
        crear_tablas(db_path=path)
        columnas = columnas_tabla(connection)
        if not columnas:
            return pd.DataFrame()
        data_columns = [col for col in columnas if col not in TECHNICAL_COLUMNS]
        if not data_columns:
            return pd.DataFrame()

        filtros = _normalizar_filtros_busqueda(
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            turno=turno,
            turnos=turnos,
            equipo=equipo,
            equipos=equipos,
            operador=operador,
            operadores=operadores,
            banco=banco,
            malla=malla,
            fase=fase,
            tipo_perforacion=tipo_perforacion,
            tipos_detencion=tipos_detencion,
            **_filtros_extra,
        )
        where_sql, params = _construir_filtros_sql(columnas, **filtros)
        if where_sql is None:
            return pd.DataFrame()

        query = f"SELECT {', '.join(quote_identifier(col) for col in data_columns)} FROM {quote_identifier(TABLA_REGISTROS)}{where_sql} ORDER BY id"
        if limit is not None:
            query += " LIMIT ?"
            params.append(int(limit))
        if offset is not None:
            if limit is None:
                query += " LIMIT -1"
            query += " OFFSET ?"
            params.append(int(offset))

        df = pd.read_sql_query(query, connection, params=params)

    from data import preparar_dataframe

    return preparar_dataframe(df)


@cache_data
def consultar_registros_edicion(
    db_path=DB_PATH,
    fecha_desde=None,
    fecha_hasta=None,
    turno=None,
    equipo=None,
    operador=None,
    malla=None,
    limit=200,
):
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame()

    with conectar_db(path) as connection:
        crear_tablas(db_path=path)
        columnas = columnas_tabla(connection)
        if not columnas:
            return pd.DataFrame()
        data_columns = [col for col in columnas if col not in TECHNICAL_COLUMNS]
        select_columns = ["id", *data_columns]

        where_sql, params = _construir_filtros_sql(
            columnas,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            turno=turno,
            equipo=equipo,
            operador=operador,
            malla=malla,
        )
        if where_sql is None:
            return pd.DataFrame()

        query = (
            f"SELECT {', '.join(quote_identifier(col) for col in select_columns)} "
            f"FROM {quote_identifier(TABLA_REGISTROS)}{where_sql} ORDER BY id DESC"
        )
        if limit is not None:
            query += " LIMIT ?"
            params.append(int(limit))
        df = pd.read_sql_query(query, connection, params=params)

    from data import preparar_dataframe

    return preparar_dataframe(df)


def obtener_registro_por_id(registro_id, db_path=DB_PATH):
    path = Path(db_path)
    if not path.exists():
        return {}

    with conectar_db(path) as connection:
        crear_tablas(db_path=path)
        fila = connection.execute(
            f"SELECT * FROM {quote_identifier(TABLA_REGISTROS)} WHERE id = ?",
            (int(registro_id),),
        ).fetchone()
        if not fila:
            return {}
        df = pd.DataFrame([dict(fila)])

    from data import preparar_dataframe

    preparado = preparar_dataframe(df)
    if preparado.empty:
        return {}
    return preparado.iloc[0].to_dict()


@cache_data
def obtener_rango_fechas(db_path=DB_PATH):
    path = Path(db_path)
    if not path.exists():
        return None, None

    with conectar_db(path) as connection:
        crear_tablas(db_path=path)
        columnas = columnas_tabla(connection)
        columna_fecha = _resolver_columna_existente(columnas, "Fecha turno", "Fecha")
        if not columna_fecha:
            return None, None
        query = (
            f"SELECT MIN(date({quote_identifier(columna_fecha)})) AS fecha_min, "
            f"MAX(date({quote_identifier(columna_fecha)})) AS fecha_max "
            f"FROM {quote_identifier(TABLA_REGISTROS)} "
            f"WHERE TRIM(COALESCE({quote_identifier(columna_fecha)}, '')) <> ''"
        )
        fila = connection.execute(query).fetchone()

    if not fila:
        return None, None

    fecha_min = pd.to_datetime(fila["fecha_min"], errors="coerce")
    fecha_max = pd.to_datetime(fila["fecha_max"], errors="coerce")
    return (
        fecha_min.date() if not pd.isna(fecha_min) else None,
        fecha_max.date() if not pd.isna(fecha_max) else None,
    )


@cache_data
def contar_historial_filtrado(
    db_path=DB_PATH,
    fecha_desde=None,
    fecha_hasta=None,
    fecha_inicio=None,
    fecha_fin=None,
    turno=None,
    turnos=None,
    equipo=None,
    equipos=None,
    operador=None,
    operadores=None,
    banco=None,
    malla=None,
    fase=None,
    tipo_perforacion=None,
    tipos_detencion=None,
    **_filtros_extra,
):
    path = Path(db_path)
    if not path.exists():
        return 0

    with conectar_db(path) as connection:
        crear_tablas(db_path=path)
        columnas = columnas_tabla(connection)
        if not columnas:
            return 0

        filtros = _normalizar_filtros_busqueda(
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            turno=turno,
            turnos=turnos,
            equipo=equipo,
            equipos=equipos,
            operador=operador,
            operadores=operadores,
            banco=banco,
            malla=malla,
            fase=fase,
            tipo_perforacion=tipo_perforacion,
            tipos_detencion=tipos_detencion,
            **_filtros_extra,
        )
        where_sql, params = _construir_filtros_sql(columnas, **filtros)
        if where_sql is None:
            return 0

        query = f"SELECT COUNT(*) FROM {quote_identifier(TABLA_REGISTROS)}{where_sql}"
        return int(connection.execute(query, params).fetchone()[0])


@cache_data
def obtener_valores_distintos_columna(columna, db_path=DB_PATH):
    path = Path(db_path)
    if not path.exists():
        return []

    with conectar_db(path) as connection:
        crear_tablas(db_path=path)
        columnas = columnas_tabla(connection)
        candidatos = [columna]
        if columna == "Número equipo":
            candidatos.append("Número equipo")
        if columna == "Modelo equipo":
            candidatos.append("Equipo")
        columna_real = _resolver_columna_existente(columnas, *candidatos)
        if not columna_real:
            if columna == "Equipo":
                modelo_col = _resolver_columna_existente(columnas, "Modelo equipo")
                numero_col = _resolver_columna_existente(columnas, "Número equipo")
                if not (modelo_col and numero_col):
                    return []
                query = (
                    f"SELECT DISTINCT TRIM({quote_identifier(modelo_col)} || ' ' || {quote_identifier(numero_col)}) AS valor "
                    f"FROM {quote_identifier(TABLA_REGISTROS)} "
                    f"WHERE TRIM(COALESCE({quote_identifier(modelo_col)}, '')) <> '' "
                    f"AND TRIM(COALESCE({quote_identifier(numero_col)}, '')) <> '' "
                    f"ORDER BY valor"
                )
                filas = connection.execute(query).fetchall()
                return [str(fila["valor"]).strip() for fila in filas if str(fila["valor"]).strip()]
            return []
        query = (
            f"SELECT DISTINCT {quote_identifier(columna_real)} AS valor "
            f"FROM {quote_identifier(TABLA_REGISTROS)} "
            f"WHERE TRIM(COALESCE({quote_identifier(columna_real)}, '')) <> '' "
            f"ORDER BY valor"
        )
        filas = connection.execute(query).fetchall()

    return [str(fila["valor"]).strip() for fila in filas if str(fila["valor"]).strip()]


@cache_data
def consultar_alertas_operacionales_filtradas(
    db_path=DB_PATH,
    fecha_desde=None,
    fecha_hasta=None,
    fecha_inicio=None,
    fecha_fin=None,
    turno=None,
    turnos=None,
    equipo=None,
    equipos=None,
    operador=None,
    operadores=None,
    tipo_alerta=None,
    tipos_detencion=None,
    banco=None,
    malla=None,
    fase=None,
    tipo_perforacion=None,
    limit=None,
    offset=None,
    horas_turno=12,
    **_filtros_extra,
):
    df_base = consultar_historial_filtrado(
        db_path=db_path,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        turno=turno,
        turnos=turnos,
        equipo=equipo,
        equipos=equipos,
        operador=operador,
        operadores=operadores,
        banco=banco,
        malla=malla,
        fase=fase,
        tipo_perforacion=tipo_perforacion,
        tipos_detencion=tipos_detencion,
        limit=limit,
        offset=offset,
        **_filtros_extra,
    )
    if df_base.empty:
        return {"mensajes": [], "detalle": pd.DataFrame(), "sin_alertas": False, "total_registros": 0}

    resultado = evaluar_alertas_operacionales(df_base, horas_turno=horas_turno)
    detalle = resultado.get("detalle", pd.DataFrame())
    mensajes = list(resultado.get("mensajes", []))
    sin_alertas = bool(resultado.get("sin_alertas", False))

    tipos = _normalizar_lista_filtro(tipo_alerta)
    if tipos and not detalle.empty and "Tipo de alerta" in detalle.columns:
        mascara = pd.Series(False, index=detalle.index)
        serie = detalle["Tipo de alerta"].astype(str)
        for tipo in tipos:
            mascara = mascara | serie.str.contains(tipo, case=False, na=False)
        detalle = detalle[mascara].copy()
        sin_alertas = detalle.empty
        if sin_alertas:
            mensajes = []

    return {
        "mensajes": mensajes,
        "detalle": detalle.reset_index(drop=True) if not detalle.empty else detalle,
        "sin_alertas": sin_alertas,
        "total_registros": len(df_base),
    }


@cache_data
def consultar_resumen_operadores_filtrado(
    db_path=DB_PATH,
    fecha_desde=None,
    fecha_hasta=None,
    fecha_inicio=None,
    fecha_fin=None,
    turno=None,
    turnos=None,
    equipo=None,
    equipos=None,
    operador=None,
    operadores=None,
    banco=None,
    malla=None,
    fase=None,
    tipo_perforacion=None,
    tipos_detencion=None,
    **_filtros_extra,
):
    df = consultar_historial_filtrado(
        db_path=db_path,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        turno=turno,
        turnos=turnos,
        equipo=equipo,
        equipos=equipos,
        operador=operador,
        operadores=operadores,
        banco=banco,
        malla=malla,
        fase=fase,
        tipo_perforacion=tipo_perforacion,
        tipos_detencion=tipos_detencion,
        **_filtros_extra,
    )
    columnas = [
        "Operador",
        "Disponibilidad promedio",
        "Utilización promedio",
        "Rendimiento consolidado m/h",
        "Metros totales perforados",
    ]
    if df.empty or "Operador" not in df.columns:
        return pd.DataFrame(columns=columnas)

    operadores = sorted(set(OPERADORES) | set(df.get("Operador", pd.Series(dtype=str)).dropna().astype(str)))
    filas = []
    for operador_nombre in operadores:
        grupo = df[df["Operador"].astype(str) == operador_nombre].copy()
        kpis = calcular_kpis_consolidados_dataframe(grupo)
        filas.append({
            "Operador": operador_nombre,
            "Disponibilidad promedio": round(kpis["disponibilidad"], 2),
            "Utilización promedio": round(kpis["utilizacion"], 2),
            "Rendimiento consolidado m/h": round(kpis["rendimiento"], 2),
            "Metros totales perforados": round(kpis["metros"], 2),
        })

    return pd.DataFrame(filas, columns=columnas).sort_values("Metros totales perforados", ascending=False)


@cache_data
def consultar_resumen_operacional_equipos_filtrado(
    db_path=DB_PATH,
    fecha_desde=None,
    fecha_hasta=None,
    fecha_inicio=None,
    fecha_fin=None,
    turno=None,
    turnos=None,
    equipo=None,
    equipos=None,
    operador=None,
    operadores=None,
    banco=None,
    malla=None,
    fase=None,
    tipo_perforacion=None,
    tipos_detencion=None,
    **_filtros_extra,
):
    df = consultar_historial_filtrado(
        db_path=db_path,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        turno=turno,
        turnos=turnos,
        equipo=equipo,
        equipos=equipos,
        operador=operador,
        operadores=operadores,
        banco=banco,
        malla=malla,
        fase=fase,
        tipo_perforacion=tipo_perforacion,
        tipos_detencion=tipos_detencion,
        **_filtros_extra,
    )
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
    if df.empty:
        for modelo, numero in EQUIPOS.items():
            for num in numero:
                filas.append({
                    "Modelo equipo": modelo,
                    "Número equipo": limpiar_entero(num),
                    "Equipo": f"{modelo} {limpiar_entero(num)}",
                    "Operador": "",
                    "Metros perforados": 0.0,
                    "Pozos perforados": 0.0,
                    "Rendimiento consolidado m/h": 0.0,
                    "Disponibilidad %": 0.0,
                    "Utilización": 0.0,
                    "Horas efectivas perforando": 0.0,
                    "Horas no efectivas": 0.0,
                    "Horas avería equipo": 0.0,
                    "Mantención Programada": 0.0,
                    "Estado operacional": "Sin marcación",
                    "Marcación": "Sin marcación",
                })
        return pd.DataFrame(filas, columns=columnas)

    numero_equipo_col = _resolver_columna_existente(df.columns, "Número equipo", "Número equipo")
    modelo_equipo_col = _resolver_columna_existente(df.columns, "Modelo equipo", "Equipo")
    if not numero_equipo_col or not modelo_equipo_col:
        return pd.DataFrame(columns=columnas)

    if numero_equipo_col in df.columns:
        df[numero_equipo_col] = df[numero_equipo_col].astype(str).apply(limpiar_entero)

    for modelo, numeros in EQUIPOS.items():
        for numero in numeros:
            grupo = df[
                df[modelo_equipo_col].astype(str).str.strip().eq(str(modelo).strip())
                & df[numero_equipo_col].astype(str).apply(limpiar_entero).eq(limpiar_entero(numero))
            ].copy()
            operador_texto = ", ".join(dict.fromkeys(grupo.get("Operador", pd.Series(dtype=str)).dropna().astype(str)))
            metros = pd.to_numeric(grupo.get("Metros perforados", pd.Series(dtype=float)), errors="coerce").fillna(0)
            pozos = pd.to_numeric(grupo.get("Pozos perforados", pd.Series(dtype=float)), errors="coerce").fillna(0)
            horas_efectivas = pd.to_numeric(grupo.get("Horas efectivas perforando", pd.Series(dtype=float)), errors="coerce").fillna(0)
            horas_no_efectivas = pd.to_numeric(grupo.get("Horas no efectivas", pd.Series(dtype=float)), errors="coerce").fillna(0)
            horas_averia = pd.to_numeric(grupo.get("Horas avería equipo", pd.Series(dtype=float)), errors="coerce").fillna(0)
            horas_mantencion = pd.to_numeric(grupo.get("Mantención Programada", pd.Series(dtype=float)), errors="coerce").fillna(0)
            horas_standby = pd.to_numeric(grupo.get("Standby por falta de tajo/Patio", pd.Series(dtype=float)), errors="coerce").fillna(0)
            horas_sin_marcacion = pd.to_numeric(grupo.get("Sin marcación", pd.Series(dtype=float)), errors="coerce").fillna(0)
            horas_programadas = HORAS_TURNO * max(len(grupo), 1)
            disponibilidad = calcular_disponibilidad(
                horas_averia.sum(),
                horas_turno=horas_programadas,
                horas_mantencion=horas_mantencion.sum(),
                horas_standby=horas_standby.sum(),
                horas_sin_marcacion=horas_sin_marcacion.sum(),
            )
            utilizacion = calcular_utilizacion(
                horas_efectivas.sum(),
                horas_turno=horas_programadas,
                horas_averia=horas_averia.sum(),
                horas_mantencion=horas_mantencion.sum(),
            )
            total_metros = metros[(metros > 0) & (horas_efectivas > 0)].sum()
            total_horas = horas_efectivas[(metros > 0) & (horas_efectivas > 0)].sum()
            rendimiento = total_metros / total_horas if total_horas > 0 else 0
            estado, marcacion = estado_operacional_equipo(
                total_metros,
                pozos.sum(),
                horas_efectivas.sum(),
                horas_no_efectivas.sum(),
                horas_averia.sum(),
                horas_mantencion.sum(),
                horas_standby.sum(),
            )
            filas.append({
                "Modelo equipo": modelo,
                "Número equipo": limpiar_entero(numero),
                "Equipo": f"{modelo} {limpiar_entero(numero)}",
                "Operador": operador_texto,
                "Metros perforados": round(total_metros, 2),
                "Pozos perforados": round(pozos.sum(), 0),
                "Rendimiento consolidado m/h": round(rendimiento, 2),
                "Disponibilidad %": round(disponibilidad, 2),
                "Utilización": round(utilizacion, 2),
                "Horas efectivas perforando": round(horas_efectivas.sum(), 2),
                "Horas no efectivas": round(horas_no_efectivas.sum(), 2),
                "Horas avería equipo": round(horas_averia.sum(), 2),
                "Mantención Programada": round(horas_mantencion.sum(), 2),
                "Estado operacional": estado,
                "Marcación": marcacion,
            })

    return pd.DataFrame(filas, columns=columnas)


@cache_data
def consultar_resumen_aceros_filtrado(
    db_path=DB_PATH,
    fecha_desde=None,
    fecha_hasta=None,
    fecha_inicio=None,
    fecha_fin=None,
    turno=None,
    turnos=None,
    equipo=None,
    equipos=None,
    operador=None,
    operadores=None,
    banco=None,
    malla=None,
    fase=None,
    tipo_perforacion=None,
    tipos_detencion=None,
    **_filtros_extra,
):
    df = consultar_historial_filtrado(
        db_path=db_path,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        turno=turno,
        turnos=turnos,
        equipo=equipo,
        equipos=equipos,
        operador=operador,
        operadores=operadores,
        banco=banco,
        malla=malla,
        fase=fase,
        tipo_perforacion=tipo_perforacion,
        tipos_detencion=tipos_detencion,
        **_filtros_extra,
    )
    columnas = [
        "Modelo equipo",
        "Número equipo",
        "Tipo acero",
        "Número Bit / Tricono",
        "Metros totales perforados",
        "Rendimiento consolidado m/h",
    ]
    if df.empty or not {"Modelo equipo", "Número equipo"}.issubset(df.columns):
        return pd.DataFrame(columns=columnas)

    filas = []
    numero_equipo_col = _resolver_columna_existente(df.columns, "Número equipo", "Número equipo")
    if numero_equipo_col:
        df[numero_equipo_col] = df[numero_equipo_col].astype(str).apply(limpiar_entero)

    for (modelo, numero), grupo in df.groupby(["Modelo equipo", numero_equipo_col], dropna=False):
        metros = pd.to_numeric(grupo.get("Metros perforados", pd.Series(dtype=float)), errors="coerce").fillna(0)
        horas = pd.to_numeric(grupo.get("Horas efectivas perforando", pd.Series(dtype=float)), errors="coerce").fillna(0)
        productivos = (metros > 0) & (horas > 0)
        total_metros = metros[productivos].sum()
        total_horas = horas[productivos].sum()
        rendimiento = total_metros / total_horas if total_horas > 0 else 0
        bit_col = _resolver_columna_existente(grupo.columns, "Número serie Tricono/Bit")
        numeros_bit = ""
        if bit_col:
            valores = []
            for valor in grupo[bit_col].dropna().astype(str):
                texto = valor.strip()
                if texto and texto.lower() not in ("nan", "none", "nat") and texto not in valores:
                    valores.append(texto)
            numeros_bit = ", ".join(valores)
        filas.append({
            "Modelo equipo": modelo,
            "Número equipo": numero,
            "Tipo acero": "Tricono" if str(modelo).strip() == "Sandvik D75KS" else "Bit",
            "Número Bit / Tricono": numeros_bit,
            "Metros totales perforados": round(total_metros, 2),
            "Rendimiento consolidado m/h": round(rendimiento, 2),
        })

    resumen = pd.DataFrame(filas, columns=columnas)
    resumen["_orden_modelo"] = resumen["Modelo equipo"].apply(lambda modelo: {"Sandvik D75KS": 1, "FlexiROC D65": 2, "SmartROC D65": 3}.get(str(modelo).strip(), 99))
    resumen["_orden_numero"] = pd.to_numeric(resumen["Número equipo"], errors="coerce").fillna(999999)
    return resumen.sort_values(["_orden_modelo", "_orden_numero"]).drop(columns=["_orden_modelo", "_orden_numero"])


def _normalizar_busqueda_texto(valor):
    return str(valor or "").strip()


def _valor_busqueda_fecha(valor):
    fecha = pd.to_datetime(pd.Series([valor]), errors="coerce").dt.date.iloc[0]
    if pd.isna(fecha):
        return _normalizar_busqueda_texto(valor)
    return fecha.isoformat()


def _valor_busqueda_numero(valor):
    return _limpiar_entero(valor)


def actualizar_registro(registro_id, cambios, db_path=DB_PATH):
    if not cambios:
        return 0

    with conectar_db(db_path) as connection:
        crear_tablas(db_path=db_path, columnas=list(cambios.keys()))
        asegurar_columnas(connection, cambios.keys())
        set_sql = ", ".join(
            f"{quote_identifier(columna)} = ?"
            for columna in cambios
            if columna not in TECHNICAL_COLUMNS
        )
        valores = [_sqlite_value(valor) for columna, valor in cambios.items() if columna not in TECHNICAL_COLUMNS]
        if not set_sql:
            return 0
        valores.extend([datetime.now().isoformat(timespec="seconds"), registro_id])
        cursor = connection.execute(
            f"""
            UPDATE {quote_identifier(TABLA_REGISTROS)}
            SET {set_sql}, updated_at = ?
            WHERE id = ?
            """,
            valores,
        )
        connection.commit()
        return cursor.rowcount


def actualizar_registro_auditado(
    registro_id,
    cambios,
    motivo,
    db_path=DB_PATH,
    usuario="",
    sync_excel=False,
    excel_path=EXCEL_PATH,
):
    motivo_limpio = str(motivo or "").strip()
    if not motivo_limpio:
        raise ValueError("El motivo de edición es obligatorio.")

    cambios_limpios = {
        columna: valor
        for columna, valor in (cambios or {}).items()
        if columna not in TECHNICAL_COLUMNS
    }
    if not cambios_limpios:
        return {"actualizados": 0, "auditoria": 0, "campos": []}

    crear_tablas(db_path=db_path, columnas=list(cambios_limpios.keys()))
    now = datetime.now().isoformat(timespec="seconds")
    with conectar_db(db_path) as connection:
        asegurar_columnas(connection, cambios_limpios.keys())
        crear_tabla_auditoria_ediciones(connection)
        anterior = connection.execute(
            f"SELECT * FROM {quote_identifier(TABLA_REGISTROS)} WHERE id = ?",
            (int(registro_id),),
        ).fetchone()
        if not anterior:
            return {"actualizados": 0, "auditoria": 0, "campos": []}

        cambios_reales = {}
        for campo, valor_nuevo in cambios_limpios.items():
            valor_anterior = anterior[campo] if campo in anterior.keys() else None
            if _valor_auditoria(valor_anterior) != _valor_auditoria(valor_nuevo):
                cambios_reales[campo] = (valor_anterior, valor_nuevo)

        if not cambios_reales:
            return {"actualizados": 0, "auditoria": 0, "campos": []}

        set_sql = ", ".join(f"{quote_identifier(campo)} = ?" for campo in cambios_reales)
        valores_update = [_sqlite_value(valor_nuevo) for _, valor_nuevo in cambios_reales.values()]
        valores_update.extend([now, int(registro_id)])
        cursor = connection.execute(
            f"""
            UPDATE {quote_identifier(TABLA_REGISTROS)}
            SET {set_sql}, updated_at = ?
            WHERE id = ?
            """,
            valores_update,
        )
        filas_auditoria = [
            (
                int(registro_id),
                now,
                campo,
                _valor_auditoria(valor_anterior),
                _valor_auditoria(valor_nuevo),
                motivo_limpio,
                str(usuario or "").strip(),
            )
            for campo, (valor_anterior, valor_nuevo) in cambios_reales.items()
        ]
        connection.executemany(
            f"""
            INSERT INTO {quote_identifier(TABLA_AUDITORIA_EDICIONES)}
            (
                {quote_identifier("registro_id")},
                {quote_identifier("changed_at")},
                {quote_identifier("campo")},
                {quote_identifier("valor_anterior")},
                {quote_identifier("valor_nuevo")},
                {quote_identifier("motivo")},
                {quote_identifier("usuario")}
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            filas_auditoria,
        )
        connection.commit()

    if sync_excel:
        sincronizar_excel_desde_sqlite(db_path=db_path, excel_path=excel_path)

    return {
        "actualizados": cursor.rowcount,
        "auditoria": len(filas_auditoria),
        "campos": list(cambios_reales.keys()),
    }


def leer_auditoria_ediciones(registro_id=None, db_path=DB_PATH):
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame(columns=list(AUDITORIA_EDICIONES_COLUMNS.keys()))

    with conectar_db(path) as connection:
        crear_tablas(db_path=path)
        crear_tabla_auditoria_ediciones(connection)
        query = f"SELECT * FROM {quote_identifier(TABLA_AUDITORIA_EDICIONES)}"
        params = []
        if registro_id is not None:
            query += " WHERE registro_id = ?"
            params.append(int(registro_id))
        query += " ORDER BY id"
        return pd.read_sql_query(query, connection, params=params)


def sincronizar_excel_desde_sqlite(db_path=DB_PATH, excel_path=EXCEL_PATH):
    from services.export_service import exportar_reportes_excel

    df = leer_registros(db_path=db_path)
    if df.empty:
        return None
    return exportar_reportes_excel(df, excel_path)


def eliminar_registro(registro_id, db_path=DB_PATH):
    with conectar_db(db_path) as connection:
        crear_tablas(db_path=db_path)
        cursor = connection.execute(
            f"DELETE FROM {quote_identifier(TABLA_REGISTROS)} WHERE id = ?",
            (registro_id,),
        )
        connection.commit()
        limpiar_cache_consultas()
        return cursor.rowcount


@cache_data
def existe_registro_duplicado(fecha, turno, numero_equipo, operador, db_path=DB_PATH):
    path = Path(db_path)
    if not path.exists():
        return False, pd.DataFrame()

    fecha_busqueda = _valor_busqueda_fecha(fecha)
    turno_busqueda = _normalizar_busqueda_texto(turno)
    numero_busqueda = _valor_busqueda_numero(numero_equipo)
    operador_busqueda = _normalizar_busqueda_texto(operador)

    with conectar_db(path) as connection:
        crear_tablas(db_path=path)
        columnas = set(columnas_tabla(connection))
        requeridas = {"Fecha turno", "Turno", "Número equipo", "Operador"}
        if requeridas.issubset(columnas):
            query = f"""
                SELECT *
                FROM {quote_identifier(TABLA_REGISTROS)}
                WHERE {quote_identifier("Fecha turno")} = ?
                  AND {quote_identifier("Turno")} = ?
                  AND {quote_identifier("Número equipo")} = ?
                  AND {quote_identifier("Operador")} = ?
                ORDER BY id
            """
            existentes = pd.read_sql_query(
                query,
                connection,
                params=[fecha_busqueda, turno_busqueda, numero_busqueda, operador_busqueda],
            )
            if not existentes.empty:
                from data import preparar_dataframe

                return True, preparar_dataframe(existentes)

    df = leer_registros(db_path=db_path)
    if df.empty:
        return False, pd.DataFrame()

    columnas = {
        "fecha": _buscar_columna(df, "Fecha turno"),
        "turno": _buscar_columna(df, "Turno"),
        "numero": _buscar_columna(df, "Número equipo", "Número equipo"),
        "operador": _buscar_columna(df, "Operador"),
    }
    if not all(columnas.values()):
        return False, pd.DataFrame()

    fecha_obj = pd.to_datetime(pd.Series([fecha]), errors="coerce").dt.date.iloc[0]
    fechas = pd.to_datetime(df[columnas["fecha"]], errors="coerce").dt.date
    mascara = (
        fechas.eq(fecha_obj)
        & df[columnas["turno"]].astype(str).map(_normalizar_texto).eq(_normalizar_texto(turno))
        & df[columnas["numero"]].astype(str).map(_limpiar_entero).eq(_limpiar_entero(numero_equipo))
        & df[columnas["operador"]].astype(str).map(_normalizar_texto).eq(_normalizar_texto(operador))
    )
    existentes = df[mascara].copy()
    return bool(not existentes.empty), existentes


def insertar_dataframe_reportes(df, db_path=DB_PATH, source="dataframe"):
    if df is None or df.empty:
        crear_tablas(db_path=db_path)
        return 0

    rows, columnas = _dataframe_to_rows(df, source=source)
    crear_tablas(db_path=db_path, columnas=columnas)
    sql = _insert_sql(columnas)
    with conectar_db(db_path) as connection:
        asegurar_columnas(connection, columnas)
        connection.executemany(sql, rows)
        connection.commit()
    limpiar_cache_consultas()
    return len(rows)


def reemplazar_dataframe_reportes(df, db_path=DB_PATH, source="excel_export"):
    columnas = list(df.columns) if df is not None else []
    rows, columnas = _dataframe_to_rows(df, source=source)
    crear_tablas(db_path=db_path, columnas=columnas)
    with conectar_db(db_path) as connection:
        asegurar_columnas(connection, columnas)
        connection.execute(f"DELETE FROM {quote_identifier(TABLA_REGISTROS)}")
        if rows:
            connection.executemany(_insert_sql(columnas), rows)
        connection.commit()
    limpiar_cache_consultas()
    return len(rows)


def leer_reportes_sqlite(db_path=DB_PATH):
    return leer_registros(db_path=db_path)


@cache_data
def contar_registros(db_path=DB_PATH):
    if not Path(db_path).exists():
        return 0
    with conectar_db(db_path) as connection:
        crear_tablas(db_path=db_path)
        return int(connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(TABLA_REGISTROS)}").fetchone()[0])


@cache_data
def contar_duplicados_operacionales(db_path=DB_PATH):
    path = Path(db_path)
    if not path.exists():
        return 0

    with conectar_db(path) as connection:
        crear_tablas(db_path=path)
        columnas = set(columnas_tabla(connection))
        requeridas = {"Fecha turno", "Turno", "Número equipo", "Operador"}
        if requeridas.issubset(columnas):
            query = f"""
                SELECT COALESCE(SUM(cantidad), 0)
                FROM (
                    SELECT
                        {quote_identifier("Fecha turno")} AS fecha_turno,
                        {quote_identifier("Turno")} AS turno,
                        {quote_identifier("Número equipo")} AS numero_equipo,
                        {quote_identifier("Operador")} AS operador,
                        COUNT(*) AS cantidad
                    FROM {quote_identifier(TABLA_REGISTROS)}
                    GROUP BY fecha_turno, turno, numero_equipo, operador
                    HAVING COUNT(*) > 1
                )
            """
            try:
                return int(connection.execute(query).fetchone()[0])
            except Exception:
                pass

    df = leer_registros(db_path=db_path)
    if df.empty:
        return 0
    columnas = [
        _buscar_columna(df, "Fecha turno"),
        _buscar_columna(df, "Turno"),
        _buscar_columna(df, "Número equipo", "Número equipo"),
        _buscar_columna(df, "Operador"),
    ]
    if not all(columnas):
        return 0
    base = df[columnas].copy()
    base.columns = ["Fecha turno", "Turno", "Número equipo", "Operador"]
    base["Fecha turno"] = pd.to_datetime(base["Fecha turno"], errors="coerce").dt.date.astype(str)
    base["Turno"] = base["Turno"].astype(str).map(_normalizar_texto)
    base["Número equipo"] = base["Número equipo"].astype(str).map(_limpiar_entero)
    base["Operador"] = base["Operador"].astype(str).map(_normalizar_texto)
    return int(base.duplicated(subset=["Fecha turno", "Turno", "Número equipo", "Operador"], keep=False).sum())


def _dataframe_to_rows(df, source="dataframe"):
    if df is None or df.empty:
        return [], list(df.columns) if df is not None else []

    df_insert = df.copy()
    df_insert = df_insert.rename(columns={col: alias_columna(str(col)) for col in df_insert.columns})
    columnas = [str(col) for col in df_insert.columns if str(col) not in TECHNICAL_COLUMNS]
    if len(set(columnas)) != len(columnas):
        consolidado = df_insert.loc[:, ~df_insert.columns.duplicated()].copy()
        for columna in df_insert.columns[df_insert.columns.duplicated()].unique():
            bloque = df_insert.loc[:, df_insert.columns == columna]
            consolidado[columna] = bloque.bfill(axis=1).iloc[:, 0]
        df_insert = consolidado
        columnas = [str(col) for col in df_insert.columns if str(col) not in TECHNICAL_COLUMNS]
    df_insert = df_insert[columnas].where(pd.notna(df_insert[columnas]), None)
    now = datetime.now().isoformat(timespec="seconds")
    rows = []
    for index, row in enumerate(df_insert.itertuples(index=False, name=None), start=1):
        rows.append(
            (
                now,
                now,
                source,
                index,
                *(_sqlite_value(value) for value in row),
            )
        )
    return rows, columnas


def _insert_sql(columnas):
    insert_columns = ["created_at", "updated_at", "source", "source_row", *columnas]
    columns_sql = ", ".join(quote_identifier(columna) for columna in insert_columns)
    placeholders = ", ".join("?" for _ in insert_columns)
    return f"INSERT INTO {quote_identifier(TABLA_REGISTROS)} ({columns_sql}) VALUES ({placeholders})"


def _sqlite_value(value):
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _valor_auditoria(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    texto = str(value).strip()
    try:
        numero = float(texto)
    except ValueError:
        return texto
    if numero.is_integer():
        return str(int(numero))
    return str(numero)


def _buscar_columna(df, *candidatos):
    normalizadas = {_normalizar_ascii(col): col for col in df.columns}
    for candidato in candidatos:
        columna = normalizadas.get(_normalizar_ascii(candidato))
        if columna:
            return columna
    return None


def _normalizar_texto(valor):
    return _normalizar_ascii(valor)


def _normalizar_ascii(valor):
    from unicodedata import normalize

    texto = str(valor).strip()
    reemplazos = {
        "?": "i",
        "ía": "ía",
        "Día": "Día",
        "día": "día",
    }
    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)
    return normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower().strip()


def _limpiar_entero(valor):
    texto = str(valor).strip()
    if texto.lower() in ("", "nan", "none", "nat"):
        return ""
    try:
        numero = float(texto)
    except ValueError:
        return texto
    return str(int(numero)) if numero.is_integer() else texto
