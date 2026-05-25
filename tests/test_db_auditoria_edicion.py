import pytest

import db


def _crear_registro_base(db_path):
    db.insertar_registro(
        {
            "Fecha turno": "2026-05-24",
            "Turno": "Día",
            "Número equipo": "9274",
            "Operador": "Operador Original",
            "Malla": "M-01",
            "Metros perforados": 100,
            "Observaciones": "Sin observaciones",
        },
        db_path=db_path,
        source="test",
    )
    with db.conectar_db(db_path) as connection:
        return connection.execute(
            f"SELECT id FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
        ).fetchone()["id"]


def test_crear_tablas_crea_tabla_auditoria_ediciones(tmp_path):
    db_path = tmp_path / "reportes_test.db"

    db.crear_tablas(db_path=db_path, columnas=["Fecha turno", "Turno", "Número equipo"])

    with db.conectar_db(db_path) as connection:
        tablas = {
            fila["name"]
            for fila in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        columnas = db.columnas_tabla(connection, db.TABLA_AUDITORIA_EDICIONES)

    assert db.TABLA_AUDITORIA_EDICIONES in tablas
    assert "registro_id" in columnas
    assert "campo" in columnas
    assert "valor_anterior" in columnas
    assert "valor_nuevo" in columnas
    assert "motivo" in columnas


def test_actualizar_registro_auditado_rechaza_motivo_vacio(tmp_path):
    db_path = tmp_path / "reportes_test.db"
    registro_id = _crear_registro_base(db_path)

    with pytest.raises(ValueError, match="motivo"):
        db.actualizar_registro_auditado(
            registro_id,
            {"Operador": "Operador Nuevo"},
            "   ",
            db_path=db_path,
        )

    auditoria = db.leer_auditoria_ediciones(registro_id, db_path=db_path)
    assert auditoria.empty


def test_actualizar_registro_auditado_guarda_cambios_y_auditoria(tmp_path):
    db_path = tmp_path / "reportes_test.db"
    registro_id = _crear_registro_base(db_path)

    resultado = db.actualizar_registro_auditado(
        registro_id,
        {
            "Operador": "Operador Corregido",
            "Metros perforados": 125,
            "Observaciones": "Corrección validada",
        },
        "Corrección solicitada por supervisión",
        db_path=db_path,
        usuario="test-user",
    )
    registro = db.obtener_registro_por_id(registro_id, db_path=db_path)
    auditoria = db.leer_auditoria_ediciones(registro_id, db_path=db_path)

    assert resultado["actualizados"] == 1
    assert resultado["auditoria"] == 3
    assert registro["Operador"] == "Operador Corregido"
    assert registro["Metros perforados"] == 125
    assert set(auditoria["campo"]) == {"Operador", "Metros perforados", "Observaciones"}

    fila_operador = auditoria[auditoria["campo"] == "Operador"].iloc[0]
    assert fila_operador["registro_id"] == registro_id
    assert fila_operador["valor_anterior"] == "Operador Original"
    assert fila_operador["valor_nuevo"] == "Operador Corregido"
    assert fila_operador["motivo"] == "Corrección solicitada por supervisión"
    assert fila_operador["usuario"] == "test-user"


def test_actualizar_registro_auditado_no_audita_valores_sin_cambio(tmp_path):
    db_path = tmp_path / "reportes_test.db"
    registro_id = _crear_registro_base(db_path)

    resultado = db.actualizar_registro_auditado(
        registro_id,
        {"Operador": "Operador Original", "Metros perforados": 100},
        "Revisión sin cambios reales",
        db_path=db_path,
    )
    auditoria = db.leer_auditoria_ediciones(registro_id, db_path=db_path)

    assert resultado == {"actualizados": 0, "auditoria": 0, "campos": []}
    assert auditoria.empty


def test_consultar_registros_edicion_incluye_id_y_filtra_malla(tmp_path):
    db_path = tmp_path / "reportes_test.db"
    registro_id = _crear_registro_base(db_path)

    resultados = db.consultar_registros_edicion(
        db_path=db_path,
        fecha_desde="2026-05-24",
        fecha_hasta="2026-05-24",
        turno=["Día"],
        operador=["Operador Original"],
        malla=["M-01"],
    )

    assert len(resultados) == 1
    assert int(resultados.iloc[0]["id"]) == registro_id
