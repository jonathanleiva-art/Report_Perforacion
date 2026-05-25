from pathlib import Path

from PIL import Image

from services import malla_service


class FakeUpload:
    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getbuffer(self):
        return self._data


def _configurar(monkeypatch, tmp_path):
    db_path = tmp_path / "malla_preview.db"
    planos_dir = tmp_path / "data" / "planos_malla"
    preview_dir = planos_dir / "preview"
    monkeypatch.setattr(malla_service.db, "DB_PATH", db_path)
    monkeypatch.setattr(malla_service, "PLANOS_MALLA_DIR", planos_dir)
    monkeypatch.setattr(malla_service, "PLANOS_MALLA_PREVIEW_DIR", preview_dir)
    return db_path, planos_dir, preview_dir


def test_generar_preview_plano_malla_crea_png_asistido(monkeypatch, tmp_path):
    db_path, planos_dir, preview_dir = _configurar(monkeypatch, tmp_path)
    archivo = FakeUpload("plano_control.pdf", b"%PDF-1.4\npreview-bytes")

    plano = malla_service.registrar_archivo_plano_malla(archivo, db_path=db_path)
    registro = malla_service.obtener_archivo_plano_malla(plano["archivo_id"], db_path=db_path)

    ruta_preview = malla_service.generar_preview_plano_malla(registro, preview_dir=preview_dir, forzar=True)

    assert ruta_preview is not None
    assert Path(ruta_preview).exists()
    assert Path(ruta_preview).suffix.lower() == ".png"
    assert Path(ruta_preview).parent == preview_dir
    with Image.open(ruta_preview) as imagen:
        assert imagen.size == (1400, 1800)


def test_obtener_preview_plano_malla_reutiliza_preview_existente(monkeypatch, tmp_path):
    db_path, _, preview_dir = _configurar(monkeypatch, tmp_path)
    archivo = FakeUpload("plano_control.pdf", b"%PDF-1.4\npreview-bytes")

    plano = malla_service.registrar_archivo_plano_malla(archivo, db_path=db_path)
    ruta_preview_1 = malla_service.obtener_preview_plano_malla(plano["archivo_id"], db_path=db_path, preview_dir=preview_dir)
    ruta_preview_2 = malla_service.obtener_preview_plano_malla(plano["archivo_id"], db_path=db_path, preview_dir=preview_dir)

    assert ruta_preview_1 == ruta_preview_2
    assert Path(ruta_preview_1).exists()
