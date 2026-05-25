from pathlib import Path

import pandas as pd

import db
from config import EXCEL_PATH
from data import preparar_dataframe
from schema import SQLITE_TABLE_REPORTES


def contar_registros_sqlite():
    if not Path(db.DB_PATH).exists():
        return 0

    with db.get_connection() as connection:
        cursor = connection.execute(f"SELECT COUNT(*) FROM {db.quote_identifier(SQLITE_TABLE_REPORTES)}")
        return cursor.fetchone()[0]


def leer_excel_actual():
    if not Path(EXCEL_PATH).exists():
        return pd.DataFrame()

    df = pd.read_excel(EXCEL_PATH, engine="openpyxl")
    return preparar_dataframe(df)


def main():
    print(f"DB_PATH={db.DB_PATH}")
    print(f"EXCEL_PATH={EXCEL_PATH}")

    db.crear_tablas_si_no_existen()

    registros_antes = contar_registros_sqlite()
    df_excel = leer_excel_actual()
    registros_insertados = db.insertar_dataframe_reportes(df_excel)
    df_sqlite = db.leer_reportes_sqlite()

    print(f"REGISTROS_SQLITE_ANTES={registros_antes}")
    print(f"REGISTROS_EXCEL_LEIDOS={len(df_excel)}")
    print(f"REGISTROS_INSERTADOS={registros_insertados}")
    print(f"REGISTROS_SQLITE_LEIDOS={len(df_sqlite)}")


if __name__ == "__main__":
    main()
