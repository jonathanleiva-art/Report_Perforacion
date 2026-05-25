from pathlib import Path

from services import malla_service


class FakeUpload:
    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getbuffer(self):
        return self._data


def _configurar(monkeypatch, tmp_path):
    db_path = tmp_path / "malla_archivos_simple.db"
    planos_dir = tmp_path / "data" / "planos_malla"
    reportes_dir = tmp_path / "data" / "reportes_operadores"
    monkeypatch.setattr(malla_service.db, "DB_PATH", db_path)
    monkeypatch.setattr(malla_service, "PLANOS_MALLA_DIR", planos_dir)
    monkeypatch.setattr(malla_service, "REPORTES_OPERADORES_DIR", reportes_dir)
    return db_path, planos_dir, reportes_dir


def test_registrar_archivo_plano_malla_guarda_archivo_y_lista(monkeypatch, tmp_path):
    db_path, planos_dir, _ = _configurar(monkeypatch, tmp_path)
    archivo = FakeUpload("plano_prueba.pdf", b"pdf-bytes")

    resultado = malla_service.registrar_archivo_plano_malla(archivo, db_path=db_path)

    assert resultado["ok"] is True
    assert resultado["registro"]["nombre_archivo"] == "plano_prueba.pdf"
    assert Path(resultado["registro"]["ruta_archivo"]).exists()
    assert Path(resultado["registro"]["ruta_archivo"]).parent == planos_dir

    listado = malla_service.listar_archivos_planos_malla(db_path=db_path)
    assert len(listado) == 1
    assert listado.iloc[0]["categoria"] == "plano_malla"


def test_registrar_archivo_reporte_operador_guarda_archivo_y_lista(monkeypatch, tmp_path):
    db_path, _, reportes_dir = _configurar(monkeypatch, tmp_path)
    archivo = FakeUpload("reporte_operador.png", b"img-bytes")

    resultado = malla_service.registrar_archivo_reporte_operador(archivo, db_path=db_path)

    assert resultado["ok"] is True
    assert resultado["registro"]["nombre_archivo"] == "reporte_operador.png"
    assert Path(resultado["registro"]["ruta_archivo"]).exists()
    assert Path(resultado["registro"]["ruta_archivo"]).parent == reportes_dir

    listado = malla_service.listar_archivos_reportes_operador(db_path=db_path)
    assert len(listado) == 1
    assert listado.iloc[0]["categoria"] == "reporte_operador"


def test_limpiar_avance_malla_vacia_tablas_y_archivos(monkeypatch, tmp_path):
    db_path, planos_dir, reportes_dir = _configurar(monkeypatch, tmp_path)
    malla_service.registrar_archivo_plano_malla(FakeUpload("plano_a.pdf", b"a"), db_path=db_path)
    malla_service.registrar_archivo_reporte_operador(FakeUpload("reporte_a.jpg", b"b"), db_path=db_path)

    resultado = malla_service.limpiar_avance_malla(db_path=db_path, limpiar_archivos=True)

    assert resultado["ok"] is True
    assert malla_service.listar_archivos_planos_malla(db_path=db_path).empty
    assert malla_service.listar_archivos_reportes_operador(db_path=db_path).empty
    assert not any(planos_dir.iterdir())
    assert not any(reportes_dir.iterdir())
