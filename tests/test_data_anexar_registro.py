import pandas as pd
import pytest

import data
import db


def _configurar_entorno(monkeypatch, tmp_path):
    db_path = tmp_path / "reportes_test.db"
    excel_path = tmp_path / "reportes_test.xlsx"
    backup_dir = tmp_path / "backup"
    monkeypatch.setattr(data.db, "DB_PATH", db_path)
    monkeypatch.setattr(data, "EXCEL_PATH", excel_path)
    monkeypatch.setattr(data, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(data.audit_log, "registrar_evento", lambda *args, **kwargs: None)
    data.leer_excel_cached.clear()
    data.leer_sqlite_cached.clear()
    return db_path, excel_path, backup_dir


def _registro_base():
    return pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Noche",
            "Número equipo": "9274",
            "Operador": "Valeria Millan",
            "Metros perforados": 120.5,
        }
    ])


def _registro_nuevo():
    return pd.DataFrame([
        {
            "Fecha turno": "2026-05-24",
            "Turno": "Día",
            "Número equipo": "9275",
            "Operador": "Operador Nuevo",
            "Metros perforados": 75,
        }
    ])


def test_anexar_registro_agrega_una_fila_nueva(monkeypatch, tmp_path):
    db_path, excel_path, _ = _configurar_entorno(monkeypatch, tmp_path)

    data.guardar_reportes(_registro_base())
    final, ruta_excel, respaldo, lastrowid = data.anexar_registro(_registro_nuevo())
    resultado_sqlite = db.leer_registros(db_path=db_path)

    assert ruta_excel == excel_path
    assert len(final) == 2
    assert len(resultado_sqlite) == 2
    assert set(final["Operador"]) == {"Valeria Millan", "Operador Nuevo"}
    assert set(resultado_sqlite["Operador"]) == {"Valeria Millan", "Operador Nuevo"}
    assert respaldo is not None
    assert isinstance(lastrowid, int) and lastrowid > 0


def test_anexar_registro_conserva_historial_previo(monkeypatch, tmp_path):
    db_path, excel_path, _ = _configurar_entorno(monkeypatch, tmp_path)

    data.guardar_reportes(pd.concat([_registro_base(), _registro_nuevo()], ignore_index=True))
    registro_extra = pd.DataFrame([
        {
            "Fecha turno": "2026-05-25",
            "Turno": "Noche",
            "Número equipo": "9276",
            "Operador": "Operador Tres",
            "Metros perforados": 50,
        }
    ])

    final, ruta_excel, _, _lastrowid = data.anexar_registro(registro_extra)
    resultado_excel = pd.read_excel(ruta_excel)
    resultado_sqlite = db.leer_registros(db_path=db_path)

    assert ruta_excel == excel_path
    assert len(final) == 3
    assert len(resultado_excel) == 3
    assert len(resultado_sqlite) == 3
    assert {"Valeria Millan", "Operador Nuevo", "Operador Tres"} == set(final["Operador"])
    assert {"Valeria Millan", "Operador Nuevo", "Operador Tres"} == set(resultado_excel["Operador"])


def test_anexar_registro_devuelve_dataframe_final_path_respaldo_y_lastrowid(monkeypatch, tmp_path):
    _, excel_path, _ = _configurar_entorno(monkeypatch, tmp_path)

    data.guardar_reportes(_registro_base())
    final, ruta_excel, respaldo, lastrowid = data.anexar_registro(_registro_nuevo())

    assert isinstance(final, pd.DataFrame)
    assert ruta_excel == excel_path
    assert respaldo is not None
    assert ruta_excel.exists()
    assert isinstance(lastrowid, int) and lastrowid > 0


def test_anexar_registro_limpia_cache_sin_error(monkeypatch, tmp_path):
    _configurar_entorno(monkeypatch, tmp_path)

    data.limpiar_cache_reportes()

    assert True


def test_anexar_registro_es_incremental_y_no_usa_guardar_reportes(monkeypatch, tmp_path):
    db_path, excel_path, _ = _configurar_entorno(monkeypatch, tmp_path)
    data.guardar_reportes(_registro_base())

    monkeypatch.setattr(
        data,
        "guardar_reportes",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no debe llamarse guardar_reportes")),
    )

    final, ruta_excel, respaldo, lastrowid = data.anexar_registro(_registro_nuevo())

    assert ruta_excel == excel_path
    assert respaldo is not None
    assert len(final) == 2
    assert len(db.leer_registros(db_path=db_path)) == 2
    assert isinstance(lastrowid, int) and lastrowid > 0


def test_anexar_registro_si_sqlite_falla_no_es_exito_operativo(monkeypatch, tmp_path):
    db_path, excel_path, _ = _configurar_entorno(monkeypatch, tmp_path)
    data.guardar_reportes(_registro_base())

    monkeypatch.setattr(
        data.db,
        "insertar_registro",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("sqlite falla")),
    )

    with pytest.raises(RuntimeError, match="No se pudo guardar el reporte en SQLite."):
        data.anexar_registro(_registro_nuevo())

    assert db.leer_registros(db_path=db_path).shape[0] == 1
    assert excel_path.exists()


def test_anexar_registro_excel_falla_despues_de_sqlite_ok(monkeypatch, tmp_path):
    db_path, excel_path, _ = _configurar_entorno(monkeypatch, tmp_path)
    data.guardar_reportes(_registro_base())
    eventos = []
    monkeypatch.setattr(
        data.audit_log,
        "registrar_evento",
        lambda *args, **kwargs: eventos.append((args, kwargs)),
    )
    monkeypatch.setattr(
        data,
        "exportar_reportes_excel",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("excel falla")),
    )

    final, ruta_excel, respaldo, lastrowid = data.anexar_registro(_registro_nuevo())

    assert ruta_excel == excel_path
    assert respaldo is not None
    assert len(final) == 2
    assert len(db.leer_registros(db_path=db_path)) == 2
    assert any(evento[0][0] == "guardado_excel" for evento in eventos)
    assert isinstance(lastrowid, int) and lastrowid > 0
