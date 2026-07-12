import pytest
import pandas as pd

import data
import db


_CREAR_TABLAS = db.crear_tablas
_REEMPLAZAR_DATAFRAME_REPORTES = db.reemplazar_dataframe_reportes


def _limpiar_caches():
    data.leer_excel_cached.clear()
    data.leer_sqlite_cached.clear()


def _configurar_paths_temporales(monkeypatch, tmp_path):
    db_path = tmp_path / "reportes_test.db"
    excel_path = tmp_path / "reportes_test.xlsx"
    backup_dir = tmp_path / "backup"
    monkeypatch.setattr(data.db, "DB_PATH", db_path)
    monkeypatch.setattr(data, "EXCEL_PATH", excel_path)
    monkeypatch.setattr(data, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(data.audit_log, "registrar_evento", lambda *args, **kwargs: None)
    _limpiar_caches()
    return db_path, excel_path, backup_dir


def _parchar_reemplazo_sqlite(monkeypatch, db_path):
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


def test_guardar_reportes_escribe_sqlite_temporal_correctamente(monkeypatch, tmp_path):
    db_path, excel_path, _ = _configurar_paths_temporales(monkeypatch, tmp_path)
    _parchar_reemplazo_sqlite(monkeypatch, db_path)

    df = pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Noche",
            "Número equipo": "9274",
            "Operador": "Valeria Millan",
            "Metros perforados": 120.5,
        },
        {
            "Fecha turno": "2026-05-24",
            "Turno": "Día",
            "Número equipo": "9275",
            "Operador": "Operador Dos",
            "Metros perforados": 75,
        },
    ])

    ruta_excel, respaldo = data.guardar_reportes(df)
    resultado_sqlite = db.leer_registros(db_path=db_path)
    esperado = data.preparar_dataframe(df)

    assert ruta_excel == excel_path
    assert respaldo is None
    assert db_path.exists()
    assert len(resultado_sqlite) == 2
    assert list(resultado_sqlite.columns) == list(esperado.columns)
    assert resultado_sqlite.iloc[0]["Operador"] == "Valeria Millan"
    assert resultado_sqlite.iloc[1]["Operador"] == "Operador Dos"


def test_guardar_reportes_exporta_excel_temporal_correctamente(monkeypatch, tmp_path):
    db_path, excel_path, _ = _configurar_paths_temporales(monkeypatch, tmp_path)
    _parchar_reemplazo_sqlite(monkeypatch, db_path)

    df = pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Noche",
            "Número equipo": "9274",
            "Operador": "Valeria Millan",
            "Metros perforados": 120.5,
        }
    ])

    ruta_excel, respaldo = data.guardar_reportes(df)
    resultado_excel = pd.read_excel(ruta_excel)
    esperado = data.preparar_dataframe(df)

    assert ruta_excel == excel_path
    assert respaldo is None
    assert ruta_excel.exists()
    assert len(resultado_excel) == 1
    assert list(resultado_excel.columns) == list(esperado.columns)
    assert resultado_excel.iloc[0]["Operador"] == "Valeria Millan"


def test_anexar_registro_agrega_una_fila_sin_perder_historico(monkeypatch, tmp_path):
    db_path, excel_path, _ = _configurar_paths_temporales(monkeypatch, tmp_path)
    _parchar_reemplazo_sqlite(monkeypatch, db_path)

    registro_inicial = pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Noche",
            "Número equipo": "9274",
            "Operador": "Valeria Millan",
        }
    ])
    nuevo_registro = pd.DataFrame([
        {
            "Fecha turno": "2026-05-24",
            "Turno": "Día",
            "Número equipo": "9275",
            "Operador": "Operador Nuevo",
        }
    ])

    data.guardar_reportes(registro_inicial)
    final, ruta_excel, respaldo, _ = data.anexar_registro(nuevo_registro)
    resultado_sqlite = db.leer_registros(db_path=db_path)

    assert ruta_excel == excel_path
    assert len(final) == 2
    assert len(resultado_sqlite) == 2
    assert set(final["Operador"]) == {"Valeria Millan", "Operador Nuevo"}
    assert set(resultado_sqlite["Operador"]) == {"Valeria Millan", "Operador Nuevo"}
    assert respaldo is not None


def test_anexar_registro_conserva_registros_previos(monkeypatch, tmp_path):
    db_path, excel_path, _ = _configurar_paths_temporales(monkeypatch, tmp_path)
    _parchar_reemplazo_sqlite(monkeypatch, db_path)

    registro_inicial = pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Noche",
            "Número equipo": "9274",
            "Operador": "Valeria Millan",
        },
        {
            "Fecha turno": "2026-05-24",
            "Turno": "Día",
            "Número equipo": "9275",
            "Operador": "Operador Dos",
        },
    ])
    nuevo_registro = pd.DataFrame([
        {
            "Fecha turno": "2026-05-25",
            "Turno": "Noche",
            "Número equipo": "9276",
            "Operador": "Operador Tres",
        }
    ])

    data.guardar_reportes(registro_inicial)
    final, ruta_excel, _, _lastrowid = data.anexar_registro(nuevo_registro)
    resultado_excel = pd.read_excel(ruta_excel)

    assert ruta_excel == excel_path
    assert len(final) == 3
    assert len(resultado_excel) == 3
    assert {"Valeria Millan", "Operador Dos", "Operador Tres"} == set(final["Operador"])
    assert {"Valeria Millan", "Operador Dos", "Operador Tres"} == set(resultado_excel["Operador"])


def test_guardar_reportes_mantiene_columnas_esperadas(monkeypatch, tmp_path):
    db_path, excel_path, _ = _configurar_paths_temporales(monkeypatch, tmp_path)
    _parchar_reemplazo_sqlite(monkeypatch, db_path)

    df = pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Modelo equipo": "PV271",
            "Número equipo": "9274",
            "Operador": "Valeria Millan",
            "Turno": "Noche",
        }
    ])

    ruta_excel, _ = data.guardar_reportes(df)
    esperado = data.preparar_dataframe(df)
    resultado_excel = pd.read_excel(ruta_excel)
    resultado_sqlite = db.leer_registros(db_path=db_path)

    assert ruta_excel == excel_path
    assert list(resultado_sqlite.columns) == list(esperado.columns)
    assert list(resultado_excel.columns) == list(esperado.columns)
    assert "Equipo" in resultado_excel.columns
    assert resultado_excel.iloc[0]["Equipo"] == "PV271 9274"


def test_guardar_reportes_fallback_controlado_ante_error_sqlite(monkeypatch, tmp_path):
    db_path, excel_path, _ = _configurar_paths_temporales(monkeypatch, tmp_path)

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
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("excel no debe ejecutarse")),
    )

    df = pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Noche",
            "Número equipo": "9274",
            "Operador": "Valeria Millan",
        }
    ])

    with pytest.raises(RuntimeError, match="No se pudo guardar el reporte en SQLite."):
        data.guardar_reportes(df)

    assert not excel_path.exists()
    assert db.leer_registros(db_path=db_path).empty
    assert any(evento[0][0] == "guardado_sqlite" for evento in eventos)
