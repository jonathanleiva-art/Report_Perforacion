from pathlib import Path
import sqlite3

import pandas as pd

from config import BASE_DIR
from schema import (
    NORMALIZED_DATAFRAME_COLUMNS,
    SQLITE_TABLE_REPORTES,
    SQLITE_TECHNICAL_COLUMNS,
    SQLITE_TYPES,
)


DB_PATH = BASE_DIR / "reportes_perforacion.db"


def quote_identifier(identifier):
    return '"' + str(identifier).replace('"', '""') + '"'


def get_connection(db_path=DB_PATH):
    connection = sqlite3.connect(Path(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def crear_tablas_si_no_existen(db_path=DB_PATH):
    with get_connection(db_path) as connection:
        crear_tabla_reportes(connection)


def crear_tabla_reportes(connection=None):
    owns_connection = connection is None
    if owns_connection:
        connection = get_connection()

    try:
        technical_columns = [
            f"{quote_identifier(column)} {column_type}"
            for column, column_type in SQLITE_TECHNICAL_COLUMNS.items()
        ]
        report_columns = [
            f"{quote_identifier(column)} {SQLITE_TYPES[column]}"
            for column in NORMALIZED_DATAFRAME_COLUMNS
        ]
        columns_sql = ",\n            ".join([*technical_columns, *report_columns])
        sql = f"""
        CREATE TABLE IF NOT EXISTS {quote_identifier(SQLITE_TABLE_REPORTES)} (
            {columns_sql}
        )
        """
        connection.execute(sql)
        connection.commit()
    finally:
        if owns_connection:
            connection.close()


def insertar_dataframe_reportes(df, db_path=DB_PATH):
    if df is None or df.empty:
        return 0

    rows = _dataframe_to_rows(df)
    sql = _insert_reportes_sql()

    with get_connection(db_path) as connection:
        crear_tabla_reportes(connection)
        connection.executemany(sql, rows)
        connection.commit()

    return len(rows)


def reemplazar_dataframe_reportes(df, db_path=DB_PATH):
    rows = _dataframe_to_rows(df)
    sql = _insert_reportes_sql()

    with get_connection(db_path) as connection:
        crear_tabla_reportes(connection)
        connection.execute(f"DELETE FROM {quote_identifier(SQLITE_TABLE_REPORTES)}")
        if rows:
            connection.executemany(sql, rows)
        connection.commit()

    return len(rows)


def leer_reportes_sqlite(db_path=DB_PATH):
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame(columns=NORMALIZED_DATAFRAME_COLUMNS)

    columns_sql = ", ".join(quote_identifier(column) for column in NORMALIZED_DATAFRAME_COLUMNS)
    sql = f"SELECT {columns_sql} FROM {quote_identifier(SQLITE_TABLE_REPORTES)} ORDER BY id"

    with get_connection(path) as connection:
        return pd.read_sql_query(sql, connection)


def _dataframe_to_rows(df):
    if df is None or df.empty:
        return []

    df_insert = df.copy()
    for column in NORMALIZED_DATAFRAME_COLUMNS:
        if column not in df_insert.columns:
            df_insert[column] = None

    df_insert = df_insert[NORMALIZED_DATAFRAME_COLUMNS]
    df_insert = df_insert.where(pd.notna(df_insert), None)

    return [
        tuple(_sqlite_value(value) for value in row)
        for row in df_insert.itertuples(index=False, name=None)
    ]


def _insert_reportes_sql():
    columns_sql = ", ".join(quote_identifier(column) for column in NORMALIZED_DATAFRAME_COLUMNS)
    placeholders = ", ".join("?" for _ in NORMALIZED_DATAFRAME_COLUMNS)
    return (
        f"INSERT INTO {quote_identifier(SQLITE_TABLE_REPORTES)} "
        f"({columns_sql}) VALUES ({placeholders})"
    )


def _sqlite_value(value):
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
