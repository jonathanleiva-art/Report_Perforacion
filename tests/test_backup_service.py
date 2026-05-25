from pathlib import Path
import zipfile

import pandas as pd

import db
from services import backup_service


def test_generar_respaldo_manual_copia_sqlite_excel_y_zip_pdf(tmp_path):
    db_path = tmp_path / "reportes.db"
    excel_path = tmp_path / "reportes.xlsx"
    pdf_dir = tmp_path / "reportes_pdf"
    backup_dir = tmp_path / "backup"

    db.insertar_registro(
        {
            "Fecha turno": "2026-05-24",
            "Turno": "Día",
            "Número equipo": "9274",
            "Operador": "Operador",
        },
        db_path=db_path,
        source="test",
    )
    pd.DataFrame([{"Fecha turno": "2026-05-24"}]).to_excel(excel_path, index=False)
    pdf_dir.mkdir()
    (pdf_dir / "reporte.pdf").write_bytes(b"%PDF-1.4")

    respaldos = backup_service.generar_respaldo_manual(
        db_path=db_path,
        excel_path=excel_path,
        reportes_pdf_dir=pdf_dir,
        backup_dir=backup_dir,
    )

    rutas = [item["ruta"] for item in respaldos]
    assert len(rutas) == 3
    assert all(ruta.exists() for ruta in rutas)
    assert any(ruta.suffix == ".db" for ruta in rutas)
    assert any(ruta.suffix == ".xlsx" for ruta in rutas)
    zip_path = next(ruta for ruta in rutas if ruta.suffix == ".zip")
    with zipfile.ZipFile(zip_path) as archivo:
        assert "reporte.pdf" in archivo.namelist()


def test_respaldar_archivo_no_sobrescribe_destino_existente(tmp_path, monkeypatch):
    origen = tmp_path / "reportes.db"
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    origen.write_text("nuevo", encoding="utf-8")
    destino_existente = backup_dir / "sqlite_reportes_perforacion_20260524_210000.db"
    destino_existente.write_text("existente", encoding="utf-8")

    destino = backup_service.respaldar_archivo(
        origen,
        "sqlite_reportes_perforacion",
        backup_dir=backup_dir,
        timestamp="20260524_210000",
    )

    assert destino != destino_existente
    assert destino.name == "sqlite_reportes_perforacion_20260524_210000_1.db"
    assert destino.read_text(encoding="utf-8") == "nuevo"
    assert destino_existente.read_text(encoding="utf-8") == "existente"


def test_verificar_integridad_reporta_sqlite_excel_y_auditoria(tmp_path):
    db_path = tmp_path / "reportes.db"
    excel_path = tmp_path / "reportes.xlsx"
    db.insertar_registro(
        {
            "Fecha turno": "2026-05-24",
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
    db.actualizar_registro_auditado(
        registro_id,
        {"Metros perforados": 120},
        "Corrección de prueba",
        db_path=db_path,
    )
    pd.DataFrame(
        [
            {
                "Fecha turno": "2026-05-24",
                "Turno": "Día",
                "Número equipo": "9274",
                "Operador": "Operador Original",
            }
        ]
    ).to_excel(excel_path, index=False)

    integridad = backup_service.verificar_integridad(db_path=db_path, excel_path=excel_path)

    assert integridad["existe_base_datos"] is True
    assert integridad["existe_excel"] is True
    assert integridad["registros_sqlite"] == 1
    assert integridad["registros_excel"] == 1
    assert integridad["fecha_ultimo_registro"] == "2026-05-24"
    assert integridad["auditorias_ediciones"] == 1


def test_exportar_datos_filtrados_y_auditoria_a_excel(tmp_path):
    db_path = tmp_path / "reportes.db"
    backup_dir = tmp_path / "backup"
    db.insertar_registro(
        {
            "Fecha turno": "2026-05-24",
            "Turno": "Día",
            "Número equipo": "9274",
            "Operador": "Operador",
            "Malla": "M-01",
        },
        db_path=db_path,
        source="test",
    )
    with db.conectar_db(db_path) as connection:
        registro_id = connection.execute(
            f"SELECT id FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
        ).fetchone()["id"]
    db.actualizar_registro_auditado(
        registro_id,
        {"Malla": "M-02"},
        "Corrección de malla",
        db_path=db_path,
    )

    datos_path, datos_df = backup_service.exportar_datos_filtrados_excel(
        {"fecha_desde": "2026-05-24", "fecha_hasta": "2026-05-24"},
        db_path=db_path,
        backup_dir=backup_dir,
    )
    auditoria_path, auditoria_df = backup_service.exportar_auditoria_ediciones_excel(
        db_path=db_path,
        backup_dir=backup_dir,
    )

    assert datos_path.exists()
    assert auditoria_path.exists()
    assert len(datos_df) == 1
    assert len(auditoria_df) == 1
    assert pd.read_excel(datos_path, engine="openpyxl").shape[0] == 1
    assert pd.read_excel(auditoria_path, engine="openpyxl").shape[0] == 1
