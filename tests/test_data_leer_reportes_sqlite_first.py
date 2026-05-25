import pandas as pd

import data
import db


def _configurar_entorno(monkeypatch, tmp_path):
    db_path = tmp_path / "reportes_test.db"
    excel_path = tmp_path / "reportes_test.xlsx"
    monkeypatch.setattr(data.db, "DB_PATH", db_path)
    monkeypatch.setattr(data, "EXCEL_PATH", excel_path)
    data.leer_excel_cached.clear()
    data.leer_sqlite_cached.clear()
    return db_path, excel_path


def _registro_base():
    return pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Noche",
            "Número equipo": "9274",
            "Operador": "Valeria Millan",
        }
    ])


def test_leer_reportes_sqlite_devuelve_datos_si_sqlite_tiene_datos(monkeypatch, tmp_path):
    db_path, _ = _configurar_entorno(monkeypatch, tmp_path)
    db.insertar_registro(_registro_base().iloc[0].to_dict(), db_path=db_path, source="test")

    resultado = data.leer_reportes_sqlite(db_path=db_path)

    assert len(resultado) == 1
    assert resultado.iloc[0]["Operador"] == "Valeria Millan"
    assert resultado.iloc[0]["Turno"] == "Noche"


def test_leer_reportes_sqlite_devuelve_dataframe_vacio_si_sqlite_esta_vacio(monkeypatch, tmp_path):
    db_path, _ = _configurar_entorno(monkeypatch, tmp_path)

    resultado = data.leer_reportes_sqlite(db_path=db_path)

    assert resultado.empty


def test_leer_reportes_sqlite_si_sqlite_falla_no_lee_excel(monkeypatch, tmp_path):
    db_path, excel_path = _configurar_entorno(monkeypatch, tmp_path)
    eventos = []
    monkeypatch.setattr(
        data,
        "leer_sqlite_cached",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("sqlite falla")),
    )
    monkeypatch.setattr(
        data.audit_log,
        "registrar_evento",
        lambda *args, **kwargs: eventos.append((args, kwargs)),
    )
    monkeypatch.setattr(
        data.db,
        "migrar_excel_a_sqlite",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no debe migrar")),
    )
    monkeypatch.setattr(
        data,
        "leer_excel_cached",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no debe leer excel")),
    )

    resultado = data.leer_reportes_sqlite(db_path=db_path)

    assert resultado.empty
    assert not excel_path.exists()
    assert any(evento[0][0] == "lectura_sqlite" for evento in eventos)


def test_leer_reportes_sqlite_no_migra_excel_a_sqlite(monkeypatch, tmp_path):
    db_path, excel_path = _configurar_entorno(monkeypatch, tmp_path)
    llamado = {"migrar": False, "excel": False}
    monkeypatch.setattr(
        data,
        "leer_sqlite_cached",
        lambda *args, **kwargs: pd.DataFrame(),
    )
    monkeypatch.setattr(
        data.db,
        "migrar_excel_a_sqlite",
        lambda *args, **kwargs: llamado.__setitem__("migrar", True),
    )
    monkeypatch.setattr(
        data,
        "leer_excel_cached",
        lambda *args, **kwargs: llamado.__setitem__("excel", True),
    )

    resultado = data.leer_reportes_sqlite(db_path=db_path)

    assert resultado.empty
    assert llamado["migrar"] is False
    assert llamado["excel"] is False
    assert not excel_path.exists()


def test_leer_reportes_sqlite_no_usa_excel_como_fallback(monkeypatch, tmp_path):
    db_path, excel_path = _configurar_entorno(monkeypatch, tmp_path)
    monkeypatch.setattr(
        data,
        "leer_sqlite_cached",
        lambda *args, **kwargs: pd.DataFrame(),
    )
    monkeypatch.setattr(
        data,
        "leer_excel_cached",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no debe leerse excel")),
    )

    resultado = data.leer_reportes_sqlite(db_path=db_path)

    assert resultado.empty
    assert not excel_path.exists()
