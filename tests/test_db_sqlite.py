import pandas as pd

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
