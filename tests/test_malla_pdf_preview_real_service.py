from pathlib import Path

from PIL import Image

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None

from services import malla_service


class FakeUpload:
    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getbuffer(self):
        return self._data


def _configurar(monkeypatch, tmp_path):
    db_path = tmp_path / "malla_preview_real.db"
    planos_dir = tmp_path / "data" / "planos_malla"
    preview_dir = planos_dir / "preview"
    monkeypatch.setattr(malla_service.db, "DB_PATH", db_path)
    monkeypatch.setattr(malla_service, "PLANOS_MALLA_DIR", planos_dir)
    monkeypatch.setattr(malla_service, "PLANOS_MALLA_PREVIEW_DIR", preview_dir)
    return db_path, planos_dir, preview_dir


def _crear_pdf_simple(ruta_pdf):
    if fitz is None:
        raise RuntimeError("PyMuPDF no está disponible para crear el PDF de prueba.")
    with fitz.open() as documento:
        pagina = documento.new_page(width=595, height=842)
        pagina.insert_text((72, 72), "Plano de perforación - Vista previa real", fontsize=18)
        pagina.insert_text((72, 110), "Primera página rasterizada por PyMuPDF.", fontsize=11)
        documento.save(str(ruta_pdf))


def test_generar_preview_pdf_real_crea_png_desde_primer_pagina(monkeypatch, tmp_path):
    if fitz is None:
        raise AssertionError("PyMuPDF no está instalado; ejecutar: pip install pymupdf")

    _, _, preview_dir = _configurar(monkeypatch, tmp_path)
    ruta_pdf = tmp_path / "plano_real.pdf"
    _crear_pdf_simple(ruta_pdf)

    ruta_preview = malla_service.generar_preview_pdf_real(ruta_pdf, preview_dir=preview_dir, forzar=True)

    assert ruta_preview is not None
    assert Path(ruta_preview).exists()
    assert Path(ruta_preview).suffix.lower() == ".png"
    assert Path(ruta_preview).parent == preview_dir
    with Image.open(ruta_preview) as imagen:
        assert imagen.width > 0
        assert imagen.height > 0


def test_obtener_preview_plano_malla_usa_rasterizacion_real(monkeypatch, tmp_path):
    if fitz is None:
        raise AssertionError("PyMuPDF no está instalado; ejecutar: pip install pymupdf")

    db_path, _, preview_dir = _configurar(monkeypatch, tmp_path)
    ruta_pdf = tmp_path / "plano_real.pdf"
    _crear_pdf_simple(ruta_pdf)
    archivo = FakeUpload("plano_real.pdf", ruta_pdf.read_bytes())

    plano = malla_service.registrar_archivo_plano_malla(archivo, db_path=db_path)
    ruta_preview = malla_service.obtener_preview_plano_malla(plano["archivo_id"], db_path=db_path, preview_dir=preview_dir)

    assert ruta_preview is not None
    assert Path(ruta_preview).exists()
    assert Path(ruta_preview).suffix.lower() == ".png"
