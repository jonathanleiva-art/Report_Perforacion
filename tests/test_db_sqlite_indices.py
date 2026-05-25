from pathlib import Path

import pandas as pd

import db


def _configurar(monkeypatch, tmp_path):
    db_path = tmp_path / "reportes_indices.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    return db_path


def test_crear_tablas_crea_indices_operacionales(monkeypatch, tmp_path):
    db_path = _configurar(monkeypatch, tmp_path)

    db.crear_tablas(
        db_path=db_path,
        columnas=[
            "Fecha turno",
            "Turno",
            "Número equipo",
            "Operador",
            "Banco",
            "Malla",
        ],
    )

    with db.conectar_db(db_path) as connection:
        indices = {fila["name"] for fila in connection.execute("PRAGMA index_list('registros_perforacion')").fetchall()}

    assert "idx_registros_fecha_turno" in indices
    assert "idx_registros_turno" in indices
    assert "idx_registros_numero_equipo" in indices
    assert "idx_registros_operador" in indices
    assert "idx_registros_banco" in indices
    assert "idx_registros_malla" in indices
    assert "idx_registros_fecha_turno_turno_equipo_operador" in indices


def test_existe_registro_duplicado_y_contar_duplicados_operacionales_usan_sql(monkeypatch, tmp_path):
    db_path = _configurar(monkeypatch, tmp_path)
    df = pd.DataFrame(
        [
            {
                "Fecha turno": "2026-05-24",
                "Turno": "Noche",
                "Número equipo": "9277",
                "Operador": "Valeria Millan",
                "Banco": "B1",
                "Malla": "M1",
            },
            {
                "Fecha turno": "2026-05-24",
                "Turno": "Noche",
                "Número equipo": "9277",
                "Operador": "Valeria Millan",
                "Banco": "B1",
                "Malla": "M1",
            },
        ]
    )

    db.reemplazar_dataframe_reportes(df, db_path=db_path, source="test")

    duplicado, existentes = db.existe_registro_duplicado(
        "2026-05-24",
        "Noche",
        "9277",
        "Valeria Millan",
        db_path=db_path,
    )

    assert duplicado is True
    assert len(existentes) == 2
    assert db.contar_duplicados_operacionales(db_path=db_path) == 2
