import sqlite3

from services import source_service


def test_crear_fuente_datos_crea_tabla_y_registro(tmp_path):
    db_path = tmp_path / "fuentes.db"

    id_fuente = source_service.crear_fuente_datos(
        nombre_fuente="Excel prueba",
        tipo_fuente="excel_prueba",
        archivo_origen="prueba.xlsx",
        total_registros=10,
        fecha_min="2026-05-01",
        fecha_max="2026-05-03",
        observacion="Carga de prueba",
        db_path=db_path,
    )

    fuente = source_service.obtener_fuente_por_id(id_fuente, db_path=db_path)
    assert fuente["nombre_fuente"] == "Excel prueba"
    assert fuente["tipo_fuente"] == "excel_prueba"
    assert fuente["archivo_origen"] == "prueba.xlsx"
    assert fuente["total_registros"] == 10
    assert fuente["fecha_min"] == "2026-05-01"
    assert fuente["fecha_max"] == "2026-05-03"
    assert fuente["estado"] == "activa"
    assert fuente["activo"] == 1


def test_listar_fuentes_datos_devuelve_registros(tmp_path):
    db_path = tmp_path / "fuentes.db"
    source_service.crear_fuente_datos(
        nombre_fuente="Manual SQLite",
        tipo_fuente="sqlite_manual",
        db_path=db_path,
    )
    source_service.crear_fuente_datos(
        nombre_fuente="Excel ciclos",
        tipo_fuente="excel_ciclos",
        db_path=db_path,
    )

    fuentes = source_service.listar_fuentes_datos(db_path=db_path)

    assert len(fuentes) == 2
    assert {"Manual SQLite", "Excel ciclos"} == set(fuentes["nombre_fuente"])


def test_actualizar_estado_fuente_actualiza_estado_y_activo(tmp_path):
    db_path = tmp_path / "fuentes.db"
    id_fuente = source_service.crear_fuente_datos(
        nombre_fuente="Excel ciclos",
        tipo_fuente="excel_ciclos",
        db_path=db_path,
    )

    actualizadas = source_service.actualizar_estado_fuente(
        id_fuente,
        "inactiva",
        db_path=db_path,
        observacion="Desactivada para prueba",
    )

    fuente = source_service.obtener_fuente_por_id(id_fuente, db_path=db_path)
    assert actualizadas == 1
    assert fuente["estado"] == "inactiva"
    assert fuente["activo"] == 0
    assert fuente["observacion"] == "Desactivada para prueba"


def test_eliminar_fuente_datos_logico_no_borra_fila(tmp_path):
    db_path = tmp_path / "fuentes.db"
    id_fuente = source_service.crear_fuente_datos(
        nombre_fuente="Excel operacional",
        tipo_fuente="excel_registro_operacional",
        db_path=db_path,
    )

    eliminadas = source_service.eliminar_fuente_datos_logico(
        id_fuente,
        db_path=db_path,
        observacion="Eliminación lógica de prueba",
    )

    fuente = source_service.obtener_fuente_por_id(id_fuente, db_path=db_path)
    activas = source_service.listar_fuentes_datos(db_path=db_path, solo_activas=True)
    assert eliminadas == 1
    assert fuente is not None
    assert fuente["estado"] == "eliminada"
    assert fuente["activo"] == 0
    assert fuente["observacion"] == "Eliminación lógica de prueba"
    assert activas.empty


def test_asegurar_tabla_fuentes_migra_tabla_existente_sin_borrar_datos(tmp_path):
    db_path = tmp_path / "fuentes_legacy.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE fuentes_datos (
                id_fuente INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_fuente TEXT NOT NULL,
                tipo_fuente TEXT NOT NULL,
                activo INTEGER DEFAULT 1
            )
            """
        )
        connection.execute(
            "INSERT INTO fuentes_datos (nombre_fuente, tipo_fuente, activo) VALUES (?, ?, 1)",
            ("Legacy", "excel_ciclos"),
        )
        connection.commit()

    fuentes = source_service.listar_fuentes_datos(db_path=db_path)

    assert len(fuentes) == 1
    assert fuentes.iloc[0]["nombre_fuente"] == "Legacy"
    assert "estado" in fuentes.columns
    assert "archivo_origen" in fuentes.columns
    assert "observacion" in fuentes.columns
