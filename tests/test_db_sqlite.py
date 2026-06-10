import sqlite3

import pandas as pd
import pytest

import db


def test_crear_tablas_con_columnas_dinamicas(tmp_path):
    db_path = tmp_path / "reportes_test.db"

    db.crear_tablas(db_path=db_path, columnas=["Fecha turno", "Turno", "Número equipo"])

    assert db_path.exists()
    with db.conectar_db(db_path) as connection:
        columnas = db.columnas_tabla(connection)

    assert "id" in columnas
    assert "created_at" in columnas
    assert "updated_at" in columnas
    assert "source" in columnas
    assert "source_row" in columnas
    assert "Fecha turno" in columnas
    assert "Turno" in columnas
    assert "Número equipo" in columnas


def test_conectar_db_activa_wal_en_sqlite_temporal(tmp_path):
    db_path = tmp_path / "reportes_wal.db"

    with db.conectar_db(db_path) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert int(synchronous) == 1


def test_normalizar_ascii_no_corrompe_signo_interrogacion():
    texto = db._normalizar_ascii(f"{chr(191)}Equipo operativo?")

    assert "?" in texto
    assert texto.endswith("?")


def test_crear_tablas_renombra_columna_legacy_a_canonica(tmp_path):
    db_path = tmp_path / "reportes_legacy.db"
    with db.conectar_db(db_path) as connection:
        connection.execute(
            f"""
            CREATE TABLE {db.quote_identifier(db.TABLA_REGISTROS)} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {db.quote_identifier("Numero equipo")} TEXT
            )
            """
        )
        connection.execute(
            f"INSERT INTO {db.quote_identifier(db.TABLA_REGISTROS)} ({db.quote_identifier('Numero equipo')}) VALUES (?)",
            ("9274",),
        )
        connection.commit()

    db.crear_tablas(db_path=db_path)

    with db.conectar_db(db_path) as connection:
        columnas = db.columnas_tabla(connection)
        fila = connection.execute(
            f"SELECT {db.quote_identifier('Número equipo')} FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
        ).fetchone()

    assert "Número equipo" in columnas
    assert "Numero equipo" not in columnas
    assert fila["Número equipo"] == "9274"


def test_migracion_de_esquema_crea_respaldo_previo(monkeypatch, tmp_path):
    db_path = tmp_path / "reportes_legacy_backup.db"
    backup_dir = tmp_path / "backups_sqlite"
    monkeypatch.setattr(db, "BACKUPS_SQLITE_DIR", backup_dir)
    with db.conectar_db(db_path) as connection:
        connection.execute(
            f"""
            CREATE TABLE {db.quote_identifier(db.TABLA_REGISTROS)} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {db.quote_identifier("Numero equipo")} TEXT
            )
            """
        )
        connection.execute(
            f"INSERT INTO {db.quote_identifier(db.TABLA_REGISTROS)} ({db.quote_identifier('Numero equipo')}) VALUES (?)",
            ("9274",),
        )
        connection.commit()

    db.crear_tablas(db_path=db_path)

    respaldos = list(backup_dir.glob("reportes_legacy_backup_pre_schema_migration_*.db"))
    assert len(respaldos) == 1
    with db.conectar_db(respaldos[0]) as connection:
        columnas_respaldo = db.columnas_tabla(connection)
        fila = connection.execute(
            f"SELECT {db.quote_identifier('Numero equipo')} FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
        ).fetchone()

    assert "Numero equipo" in columnas_respaldo
    assert "Número equipo" not in columnas_respaldo
    assert fila["Numero equipo"] == "9274"


def test_crear_tablas_fusiona_columna_legacy_si_ya_existe_canonica(tmp_path):
    db_path = tmp_path / "reportes_mixtos.db"
    with db.conectar_db(db_path) as connection:
        connection.execute(
            f"""
            CREATE TABLE {db.quote_identifier(db.TABLA_REGISTROS)} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {db.quote_identifier("Numero equipo")} TEXT,
                {db.quote_identifier("Número equipo")} TEXT
            )
            """
        )
        connection.execute(
            f"""
            INSERT INTO {db.quote_identifier(db.TABLA_REGISTROS)}
                ({db.quote_identifier('Numero equipo')}, {db.quote_identifier('Número equipo')})
            VALUES (?, ?)
            """,
            ("9274", ""),
        )
        connection.commit()

    db.crear_tablas(db_path=db_path)

    with db.conectar_db(db_path) as connection:
        columnas = db.columnas_tabla(connection)
        fila = connection.execute(
            f"SELECT {db.quote_identifier('Número equipo')} FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
        ).fetchone()

    assert "Número equipo" in columnas
    assert "Numero equipo" not in columnas
    assert fila["Número equipo"] == "9274"


def test_insertar_y_leer_registro(tmp_path):
    db_path = tmp_path / "reportes_test.db"
    registro = {
        "Fecha turno": "2026-05-23",
        "Turno": "Noche",
        "Número equipo": "9274",
        "Operador": "Valeria Millan",
        "Metros perforados": 120.5,
    }

    insertados = db.insertar_registro(registro, db_path=db_path, source="test")
    resultado = db.leer_registros(db_path=db_path)

    assert insertados == 1
    assert len(resultado) == 1
    assert resultado.iloc[0]["Turno"] == "Noche"
    assert resultado.iloc[0]["Número equipo"] == "9274"
    assert resultado.iloc[0]["Operador"] == "Valeria Millan"
    assert resultado.iloc[0]["Metros perforados"] == 120.5


def test_detectar_duplicado_operacional(tmp_path):
    db_path = tmp_path / "reportes_test.db"
    df = pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Noche",
            "Número equipo": "9274",
            "Operador": "Valeria Millan",
            "Metros perforados": 120.5,
        }
    ])
    db.insertar_dataframe_reportes(df, db_path=db_path, source="test")

    existe, existentes = db.existe_registro_duplicado(
        "2026-05-23",
        "Noche",
        "9274",
        "Valeria Millan",
        db_path=db_path,
    )
    no_existe, no_existentes = db.existe_registro_duplicado(
        "2026-05-23",
        "Día",
        "9274",
        "Valeria Millan",
        db_path=db_path,
    )

    assert existe is True
    assert len(existentes) == 1
    assert no_existe is False
    assert no_existentes.empty


def test_contar_duplicados_operacionales_no_oculta_error_sqlite(tmp_path, monkeypatch, caplog):
    db_path = tmp_path / "reportes_error.db"
    db_path.write_bytes(b"")

    class ConexionConError:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, *_args, **_kwargs):
            raise sqlite3.DatabaseError("fallo controlado")

    monkeypatch.setattr(db, "conectar_db", lambda _path: ConexionConError())
    monkeypatch.setattr(db, "crear_tablas", lambda **_kwargs: None)
    monkeypatch.setattr(db, "columnas_tabla", lambda _connection: ["Fecha turno", "Turno", "N\u00famero equipo", "Operador"])
    db.contar_duplicados_operacionales.clear()

    with pytest.raises(sqlite3.DatabaseError), caplog.at_level("ERROR", logger=db.LOGGER.name):
        db.contar_duplicados_operacionales(db_path=db_path)

    assert "Error al contar duplicados operacionales" in caplog.text


def test_actualizar_registro(tmp_path):
    db_path = tmp_path / "reportes_test.db"
    db.insertar_registro(
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Día",
            "Número equipo": "9274",
            "Operador": "Operador Original",
            "Metros perforados": 100,
        },
        db_path=db_path,
        source="test",
    )
    with db.conectar_db(db_path) as connection:
        registro_id = connection.execute(
            f"SELECT id FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
        ).fetchone()["id"]

    actualizados = db.actualizar_registro(
        registro_id,
        {"Operador": "Operador Actualizado", "Metros perforados": 150},
        db_path=db_path,
    )
    resultado = db.leer_registros(db_path=db_path)

    assert actualizados == 1
    assert len(resultado) == 1
    assert resultado.iloc[0]["Operador"] == "Operador Actualizado"
    assert resultado.iloc[0]["Metros perforados"] == 150


def test_eliminar_registro(tmp_path):
    db_path = tmp_path / "reportes_test.db"
    db.insertar_registro(
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Noche",
            "Número equipo": "9274",
            "Operador": "Valeria Millan",
        },
        db_path=db_path,
        source="test",
    )
    with db.conectar_db(db_path) as connection:
        registro_id = connection.execute(
            f"SELECT id FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
        ).fetchone()["id"]

    eliminados = db.eliminar_registro(registro_id, db_path=db_path)
    resultado = db.leer_registros(db_path=db_path)

    assert eliminados == 1
    assert resultado.empty


def test_reemplazar_dataframe_reportes_reemplaza_contenido(tmp_path):
    db_path = tmp_path / "reportes_test.db"
    df_inicial = pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Día",
            "Número equipo": "9274",
            "Operador": "Operador Inicial",
        }
    ])
    df_reemplazo = pd.DataFrame([
        {
            "Fecha turno": "2026-05-24",
            "Turno": "Noche",
            "Número equipo": "9275",
            "Operador": "Operador Reemplazo",
        },
        {
            "Fecha turno": "2026-05-25",
            "Turno": "Día",
            "Número equipo": "9276",
            "Operador": "Operador Nuevo",
        },
    ])

    db.insertar_dataframe_reportes(df_inicial, db_path=db_path, source="test")
    reemplazados = db.reemplazar_dataframe_reportes(
        df_reemplazo,
        db_path=db_path,
        source="test_replace",
    )
    resultado = db.leer_registros(db_path=db_path)

    assert reemplazados == 2
    assert len(resultado) == 2
    assert "Operador Inicial" not in set(resultado["Operador"])
    assert list(resultado["Operador"]) == ["Operador Reemplazo", "Operador Nuevo"]


def test_reemplazar_dataframe_reportes_con_error_conserva_datos_previos(tmp_path, monkeypatch):
    db_path = tmp_path / "reportes_test.db"
    df_inicial = pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "DÃ­a",
            "NÃºmero equipo": "9274",
            "Operador": "Operador Inicial",
        }
    ])
    df_reemplazo = pd.DataFrame([
        {
            "Fecha turno": "2026-05-24",
            "Turno": "Noche",
            "NÃºmero equipo": "9275",
            "Operador": "Operador Reemplazo",
        }
    ])
    original_insert_sql = db._insert_sql

    def insert_sql_con_error(columnas, tabla=db.TABLA_REGISTROS):
        if tabla == "_tmp_reemplazo_registros":
            return "INSERT INTO tabla_inexistente VALUES (?)"
        return original_insert_sql(columnas, tabla=tabla)

    db.insertar_dataframe_reportes(df_inicial, db_path=db_path, source="test")
    monkeypatch.setattr(db, "_insert_sql", insert_sql_con_error)

    with pytest.raises(sqlite3.DatabaseError):
        db.reemplazar_dataframe_reportes(df_reemplazo, db_path=db_path, source="test_replace")

    resultado = db.leer_registros(db_path=db_path)
    assert len(resultado) == 1
    assert resultado.iloc[0]["Operador"] == "Operador Inicial"
