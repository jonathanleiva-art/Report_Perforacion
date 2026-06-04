from contextlib import closing
from pathlib import Path
import sqlite3

import pandas as pd

from config import DATABASE_PATH
from operators import actualizar_operador as _actualizar_operador
from services import ciclos_service


def listar_operadores(db_path=DATABASE_PATH):
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame(columns=["codigo_operador", "nombre_operador", "activo", "observacion", "updated_at"])
    with closing(sqlite3.connect(path)) as connection:
        try:
            return pd.read_sql_query(
                """
                SELECT codigo_operador, nombre_operador, activo, observacion, updated_at
                FROM operadores
                ORDER BY codigo_operador
                """,
                connection,
            )
        except sqlite3.Error:
            return pd.DataFrame(columns=["codigo_operador", "nombre_operador", "activo", "observacion", "updated_at"])


def listar_pendientes_ciclos(db_path=DATABASE_PATH):
    df = ciclos_service.leer_ciclos(db_path=db_path)
    columnas = ["codigo_original", "codigo_normalizado", "registros", "observacion"]
    if df.empty or "operador_pendiente" not in df.columns:
        return pd.DataFrame(columns=columnas)

    pendientes = df[
        df["operador_pendiente"].fillna(0).astype(int).eq(1)
        & df["operador_codigo_normalizado"].fillna("").astype(str).str.strip().ne("")
    ].copy()
    if pendientes.empty:
        return pd.DataFrame(columns=columnas)

    resultado = (
        pendientes.groupby(["operador_display", "operador_codigo_normalizado"], dropna=False)
        .size()
        .reset_index(name="registros")
        .rename(
            columns={
                "operador_display": "codigo_original",
                "operador_codigo_normalizado": "codigo_normalizado",
            }
        )
        .sort_values("registros", ascending=False)
        .reset_index(drop=True)
    )
    resultado["observacion"] = "operador pendiente de identificar"
    return resultado[columnas]


def actualizar_operador(codigo, nombre, db_path=DATABASE_PATH):
    return _actualizar_operador(codigo, nombre, db_path=db_path)


def sincronizar_operadores_ciclos(db_path=DATABASE_PATH):
    return ciclos_service.sincronizar_operadores_ciclos(db_path=db_path)
