import pandas as pd

import data
import db


_CREAR_TABLAS = db.crear_tablas


def _limpiar_caches():
    data.leer_excel_cached.clear()
    data.leer_sqlite_cached.clear()


def _configurar_paths_temporales(monkeypatch, tmp_path):
    db_path = tmp_path / "reportes_test.db"
    excel_path = tmp_path / "reportes_test.xlsx"
    monkeypatch.setattr(data.db, "DB_PATH", db_path)
    monkeypatch.setattr(data, "EXCEL_PATH", excel_path)
    monkeypatch.setattr(data.audit_log, "registrar_evento", lambda *args, **kwargs: None)
    _limpiar_caches()
    return db_path, excel_path


def test_leer_reportes_delega_en_sqlite(monkeypatch, tmp_path):
    _configurar_paths_temporales(monkeypatch, tmp_path)
    esperado = pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Noche",
            "Operador": "Valeria Millan",
        }
    ])
    llamadas = {"sqlite": 0, "legacy": 0}

    def sqlite_stub():
        llamadas["sqlite"] += 1
        return esperado

    def legacy_stub():
        llamadas["legacy"] += 1
        raise AssertionError("leer_reportes() no debe usar la ruta legacy en el wrapper actual")

    monkeypatch.setattr(data, "leer_reportes_sqlite", sqlite_stub)
    monkeypatch.setattr(data, "leer_reportes_excel_legacy", legacy_stub)

    resultado = data.leer_reportes()

    assert resultado.equals(esperado)
    assert llamadas["sqlite"] == 1
    assert llamadas["legacy"] == 0


def test_leer_reportes_delega_en_sqlite_aun_si_devuelve_vacio(monkeypatch, tmp_path):
    _configurar_paths_temporales(monkeypatch, tmp_path)
    llamadas = {"sqlite": 0, "legacy": 0}

    def sqlite_stub():
        llamadas["sqlite"] += 1
        return pd.DataFrame()

    def legacy_stub():
        llamadas["legacy"] += 1
        raise AssertionError("leer_reportes() no debe leer Excel automáticamente")

    monkeypatch.setattr(data, "leer_reportes_sqlite", sqlite_stub)
    monkeypatch.setattr(data, "leer_reportes_excel_legacy", legacy_stub)

    resultado = data.leer_reportes()

    assert resultado.empty
    assert llamadas["sqlite"] == 1
    assert llamadas["legacy"] == 0


def test_leer_reportes_excel_legacy_lee_excel_temporal(monkeypatch, tmp_path):
    _, excel_path = _configurar_paths_temporales(monkeypatch, tmp_path)
    pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Día",
            "Número equipo": "9275",
            "Operador": "Operador Excel",
        }
    ]).to_excel(excel_path, index=False)

    resultado = data.leer_reportes_excel_legacy()

    assert len(resultado) == 1
    assert resultado.iloc[0]["Operador"] == "Operador Excel"
    assert resultado.iloc[0]["Turno"] == "Día"


def test_leer_reportes_excel_legacy_devuelve_vacio_si_no_existe_excel(monkeypatch, tmp_path):
    _configurar_paths_temporales(monkeypatch, tmp_path)

    resultado = data.leer_reportes_excel_legacy()

    assert resultado.empty


def test_leer_reportes_excel_legacy_devuelve_vacio_si_excel_falla(monkeypatch, tmp_path):
    _configurar_paths_temporales(monkeypatch, tmp_path)
    monkeypatch.setattr(data, "leer_excel_cached", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("fallo excel")))

    resultado = data.leer_reportes_excel_legacy()

    assert resultado.empty


def test_limpiar_cache_reportes_es_seguro(monkeypatch, tmp_path):
    _configurar_paths_temporales(monkeypatch, tmp_path)

    data.limpiar_cache_reportes()

    assert True
