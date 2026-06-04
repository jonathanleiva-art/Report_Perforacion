from contextlib import closing
from pathlib import Path
import sqlite3

import pandas as pd

from config import DATABASE_PATH


TABLA_FUENTES = "fuentes_datos"


COLUMNAS_FUENTES = {
    "id_fuente": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "nombre_fuente": "TEXT NOT NULL",
    "tipo_fuente": "TEXT NOT NULL",
    "archivo_origen": "TEXT",
    "fecha_importacion": "TEXT",
    "total_registros": "INTEGER",
    "fecha_min": "TEXT",
    "fecha_max": "TEXT",
    "estado": "TEXT DEFAULT 'activa'",
    "activo": "INTEGER DEFAULT 1",
    "observacion": "TEXT",
}


def quote_identifier(identifier):
    return '"' + str(identifier).replace('"', '""') + '"'


def _columnas_tabla(connection, tabla):
    filas = connection.execute(f"PRAGMA table_info({quote_identifier(tabla)})").fetchall()
    columnas = []
    for fila in filas:
        try:
            columnas.append(fila["name"])
        except (TypeError, IndexError):
            columnas.append(fila[1])
    return columnas


def asegurar_tabla_fuentes_datos(connection):
    columnas_sql = ", ".join(
        f"{quote_identifier(nombre)} {tipo}"
        for nombre, tipo in COLUMNAS_FUENTES.items()
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quote_identifier(TABLA_FUENTES)} (
            {columnas_sql}
        )
        """
    )

    existentes = set(_columnas_tabla(connection, TABLA_FUENTES))
    for nombre, tipo in COLUMNAS_FUENTES.items():
        if nombre in existentes or nombre == "id_fuente":
            continue
        connection.execute(
            f"ALTER TABLE {quote_identifier(TABLA_FUENTES)} "
            f"ADD COLUMN {quote_identifier(nombre)} {tipo}"
        )

    connection.execute(
        f"CREATE INDEX IF NOT EXISTS {quote_identifier('idx_fuentes_datos_tipo_activo')} "
        f"ON {quote_identifier(TABLA_FUENTES)} ({quote_identifier('tipo_fuente')}, {quote_identifier('activo')})"
    )
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS {quote_identifier('idx_fuentes_datos_archivo')} "
        f"ON {quote_identifier(TABLA_FUENTES)} ({quote_identifier('archivo_origen')})"
    )
    connection.commit()


def _estado_activo_desde_estado(estado, activo):
    if activo is not None:
        return 1 if activo else 0
    texto = str(estado or "activa").strip().lower()
    return 0 if texto in {"inactiva", "eliminada", "desactivada"} else 1


def crear_fuente_datos(
    *,
    nombre_fuente,
    tipo_fuente,
    archivo_origen=None,
    fecha_importacion=None,
    total_registros=None,
    fecha_min=None,
    fecha_max=None,
    estado="activa",
    activo=None,
    observacion=None,
    db_path=DATABASE_PATH,
):
    if not str(nombre_fuente or "").strip():
        raise ValueError("nombre_fuente es obligatorio.")
    if not str(tipo_fuente or "").strip():
        raise ValueError("tipo_fuente es obligatorio.")

    activo_valor = _estado_activo_desde_estado(estado, activo)
    with closing(sqlite3.connect(Path(db_path))) as connection:
        connection.row_factory = sqlite3.Row
        asegurar_tabla_fuentes_datos(connection)
        cursor = connection.execute(
            f"""
            INSERT INTO {quote_identifier(TABLA_FUENTES)}
            (nombre_fuente, tipo_fuente, archivo_origen, fecha_importacion, total_registros,
             fecha_min, fecha_max, estado, activo, observacion)
            VALUES (?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?, ?, ?, ?, ?)
            """,
            (
                str(nombre_fuente).strip(),
                str(tipo_fuente).strip(),
                archivo_origen,
                fecha_importacion,
                total_registros,
                fecha_min,
                fecha_max,
                estado,
                activo_valor,
                observacion,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def listar_fuentes_datos(db_path=DATABASE_PATH, solo_activas=False, incluir_eliminadas=True):
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame(columns=list(COLUMNAS_FUENTES))

    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        asegurar_tabla_fuentes_datos(connection)
        sql = f"SELECT * FROM {quote_identifier(TABLA_FUENTES)}"
        condiciones = []
        params = []
        if solo_activas:
            condiciones.append(f"{quote_identifier('activo')} = 1")
        if not incluir_eliminadas:
            condiciones.append(f"COALESCE({quote_identifier('estado')}, '') <> 'eliminada'")
        if condiciones:
            sql += " WHERE " + " AND ".join(condiciones)
        sql += " ORDER BY fecha_importacion DESC, id_fuente DESC"
        return pd.read_sql_query(sql, connection, params=params)


def obtener_fuente_por_id(id_fuente, db_path=DATABASE_PATH):
    with closing(sqlite3.connect(Path(db_path))) as connection:
        connection.row_factory = sqlite3.Row
        asegurar_tabla_fuentes_datos(connection)
        fila = connection.execute(
            f"SELECT * FROM {quote_identifier(TABLA_FUENTES)} WHERE id_fuente = ?",
            (int(id_fuente),),
        ).fetchone()
        return dict(fila) if fila else None


def actualizar_estado_fuente(id_fuente, estado, db_path=DATABASE_PATH, activo=None, observacion=None):
    activo_valor = _estado_activo_desde_estado(estado, activo)
    with closing(sqlite3.connect(Path(db_path))) as connection:
        asegurar_tabla_fuentes_datos(connection)
        sets = [
            f"{quote_identifier('estado')} = ?",
            f"{quote_identifier('activo')} = ?",
        ]
        params = [estado, activo_valor]
        if observacion is not None:
            sets.append(f"{quote_identifier('observacion')} = ?")
            params.append(observacion)
        params.append(int(id_fuente))
        cursor = connection.execute(
            f"UPDATE {quote_identifier(TABLA_FUENTES)} SET {', '.join(sets)} WHERE id_fuente = ?",
            params,
        )
        connection.commit()
        return int(cursor.rowcount or 0)


def eliminar_fuente_datos_logico(id_fuente, db_path=DATABASE_PATH, observacion=None):
    return actualizar_estado_fuente(
        id_fuente,
        "eliminada",
        db_path=db_path,
        activo=0,
        observacion=observacion,
    )
