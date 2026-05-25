import pandas as pd
from openpyxl import load_workbook

import data
import db


def test_guardar_sqlite_escribe_temporalmente(monkeypatch, tmp_path):
    db_path = tmp_path / "reportes_test.db"
    df = data.preparar_dataframe(
        pd.DataFrame([
            {
                "Fecha turno": "2026-05-23",
                "Turno": "Noche",
                "Número equipo": "9274",
                "Operador": "Valeria Millan",
                "Metros perforados": 120.5,
            }
        ])
    )

    registros = data.guardar_sqlite(df, db_path=db_path)
    resultado = db.leer_registros(db_path=db_path)

    assert registros == 1
    assert len(resultado) == 1
    assert resultado.iloc[0]["Operador"] == "Valeria Millan"
    assert resultado.iloc[0]["Metros perforados"] == 120.5


def test_exportar_reportes_excel_crea_archivo_temporal_formateado(tmp_path):
    excel_path = tmp_path / "reportes_test.xlsx"
    df = data.preparar_dataframe(
        pd.DataFrame([
            {
                "Fecha turno": "2026-05-23",
                "Turno": "Noche",
                "Número equipo": "9274",
                "Operador": "Valeria Millan",
                "Metros perforados": 120.5,
            }
        ])
    )

    ruta = data.exportar_reportes_excel(df, path=excel_path)
    workbook = load_workbook(ruta)
    worksheet = workbook.active

    assert ruta == excel_path
    assert ruta.exists()
    assert worksheet.freeze_panes == "A2"
    assert worksheet.auto_filter.ref == worksheet.dimensions
    assert worksheet["A1"].value == "Fecha turno"
    assert worksheet["A1"].font.bold is True
    assert worksheet["A1"].fill.fgColor.rgb[-6:] == "1F4E78"
    assert worksheet["A2"].number_format == "dd-mm-yyyy"


def test_guardar_sqlite_maneja_error_y_registra_auditoria(monkeypatch, tmp_path):
    db_path = tmp_path / "reportes_test.db"
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
    df = data.preparar_dataframe(
        pd.DataFrame([
            {
                "Fecha turno": "2026-05-23",
                "Turno": "Noche",
                "Número equipo": "9274",
                "Operador": "Valeria Millan",
            }
        ])
    )

    registros = data.guardar_sqlite(df, db_path=db_path)

    assert registros == 0
    assert any(evento[0][0] == "guardado_sqlite" for evento in eventos)
