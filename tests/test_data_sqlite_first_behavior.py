import pandas as pd
import pytest

import data
import db


_CREAR_TABLAS = db.crear_tablas
_REEMPLAZAR_DATAFRAME_REPORTES = db.reemplazar_dataframe_reportes


def _limpiar_caches():
    data.leer_excel_cached.clear()
    data.leer_sqlite_cached.clear()


def _configurar_entorno(monkeypatch, tmp_path):
    db_path = tmp_path / "reportes_test.db"
    excel_path = tmp_path / "reportes_test.xlsx"
    backup_dir = tmp_path / "backup"
    monkeypatch.setattr(data.db, "DB_PATH", db_path)
    monkeypatch.setattr(data, "EXCEL_PATH", excel_path)
    monkeypatch.setattr(data, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(data.audit_log, "registrar_evento", lambda *args, **kwargs: None)
    _limpiar_caches()
    return db_path, excel_path


def _parchar_sqlite_temporal(monkeypatch, db_path):
    monkeypatch.setattr(
        data.db,
        "crear_tablas",
        lambda db_path=db_path, columnas=None: _CREAR_TABLAS(db_path=db_path, columnas=columnas),
    )
    monkeypatch.setattr(
        data.db,
        "reemplazar_dataframe_reportes",
        lambda df, db_path=db_path, source="streamlit_save": _REEMPLAZAR_DATAFRAME_REPORTES(
            df,
            db_path=db_path,
            source=source,
        ),
    )


def _df_base():
    return pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Noche",
            "Número equipo": "9274",
            "Operador": "Valeria Millan",
            "Metros perforados": 120.5,
        }
    ])


def test_sqlite_ok_excel_ok_comportamiento_actual(monkeypatch, tmp_path):
    """
    SQLite-first: si ambos pasos funcionan, el guardado se confirma y Excel queda exportado.
    """
    db_path, excel_path = _configurar_entorno(monkeypatch, tmp_path)
    _parchar_sqlite_temporal(monkeypatch, db_path)

    ruta_excel, respaldo = data.guardar_reportes(_df_base())

    assert ruta_excel == excel_path
    assert respaldo is None
    assert db_path.exists()
    assert ruta_excel.exists()
    assert len(db.leer_registros(db_path=db_path)) == 1


def test_sqlite_ok_excel_fail_comportamiento_actual(monkeypatch, tmp_path):
    """
    SQLite-first: si SQLite ya guardó bien pero Excel falla, el guardado principal se conserva.
    """
    db_path, excel_path = _configurar_entorno(monkeypatch, tmp_path)
    _parchar_sqlite_temporal(monkeypatch, db_path)
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

    ruta_excel, respaldo = data.guardar_reportes(_df_base())

    assert ruta_excel == excel_path
    assert respaldo is None
    assert db_path.exists()
    assert len(db.leer_registros(db_path=db_path)) == 1
    assert not excel_path.exists()
    assert any(evento[0][0] == "guardado_excel" for evento in eventos)


def test_sqlite_fail_excel_ok_comportamiento_actual(monkeypatch, tmp_path):
    """
    SQLite-first: si SQLite falla, no debe considerarse guardado exitoso ni usar Excel como respaldo operativo.
    """
    db_path, excel_path = _configurar_entorno(monkeypatch, tmp_path)
    llamado = {"excel": False}

    monkeypatch.setattr(
        data.db,
        "reemplazar_dataframe_reportes",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("sqlite falla")),
    )
    monkeypatch.setattr(
        data,
        "exportar_reportes_excel",
        lambda *args, **kwargs: llamado.__setitem__("excel", True),
    )

    with pytest.raises(RuntimeError, match="No se pudo guardar el reporte en SQLite."):
        data.guardar_reportes(_df_base())

    assert llamado["excel"] is False
    assert not excel_path.exists()
    assert db.leer_registros(db_path=db_path).empty


def test_sqlite_fail_excel_fail_comportamiento_actual(monkeypatch, tmp_path):
    """
    SQLite-first: si SQLite falla, Excel no debe entrar en juego y el error debe ser claro.
    """
    db_path, excel_path = _configurar_entorno(monkeypatch, tmp_path)
    llamado = {"excel": False}
    eventos = []

    monkeypatch.setattr(
        data.audit_log,
        "registrar_evento",
        lambda *args, **kwargs: eventos.append((args, kwargs)),
    )
    monkeypatch.setattr(
        data.db,
        "reemplazar_dataframe_reportes",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("sqlite falla")),
    )
    monkeypatch.setattr(
        data,
        "exportar_reportes_excel",
        lambda *args, **kwargs: llamado.__setitem__("excel", True),
    )

    with pytest.raises(RuntimeError, match="No se pudo guardar el reporte en SQLite."):
        data.guardar_reportes(_df_base())

    assert llamado["excel"] is False
    assert not excel_path.exists()
    assert db.leer_registros(db_path=db_path).empty
    assert any(evento[0][0] == "guardado_sqlite" for evento in eventos)
