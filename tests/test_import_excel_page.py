from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from services import import_diagnostic_service


class FakeUpload:
    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getbuffer(self):
        return self._data


def _page_module():
    path = Path(__file__).resolve().parents[1] / "pages" / "12_Importar_Excel.py"
    spec = spec_from_file_location("importar_excel_page", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _diagnostico_base(**overrides):
    base = {
        "archivo": "temp_uploads/archivo.xlsx",
        "hoja_principal_detectada": "Registro",
        "tipo_fuente_detectado": import_diagnostic_service.TIPO_REGISTRO_OPERACIONAL,
        "total_filas_leidas": 10,
        "fecha_min": "2026-05-01",
        "fecha_max": "2026-05-03",
        "estado_diagnostico": "ok",
        "columnas_faltantes": [],
        "columnas_reconocidas": ["turno", "numero_equipo"],
        "observaciones": [],
    }
    base.update(overrides)
    return base


def test_nombre_archivo_seguro_limpia_ruta_y_caracteres():
    page = _page_module()

    assert page._nombre_archivo_seguro("../Registro:MAYO.xlsx") == "Registro_MAYO.xlsx"
    assert page._nombre_archivo_seguro("") == "archivo.xlsx"


def test_guardar_upload_temporal_usa_timestamp_y_no_sobrescribe(tmp_path):
    page = _page_module()
    ahora = datetime(2026, 6, 4, 8, 0, 0, 123456)
    upload = FakeUpload("Registro.xlsx", b"excel-bytes")

    primera = page.guardar_upload_temporal(upload, carpeta=tmp_path, ahora=ahora)
    segunda = page.guardar_upload_temporal(upload, carpeta=tmp_path, ahora=ahora)

    assert primera.exists()
    assert segunda.exists()
    assert primera != segunda
    assert primera.name == "20260604_080000_123456_Registro.xlsx"
    assert segunda.name == "20260604_080000_123456_Registro_1.xlsx"
    assert primera.read_bytes() == b"excel-bytes"


def test_fuente_confirmable_bloquea_desconocido_error_o_faltantes():
    page = _page_module()

    assert page.fuente_confirmable(_diagnostico_base())
    assert not page.fuente_confirmable(_diagnostico_base(tipo_fuente_detectado=import_diagnostic_service.TIPO_DESCONOCIDO))
    assert not page.fuente_confirmable(_diagnostico_base(estado_diagnostico="error"))
    assert not page.fuente_confirmable(_diagnostico_base(columnas_faltantes=["metros"]))


def test_construir_observacion_diagnostico_incluye_resumen():
    page = _page_module()
    observacion = page.construir_observacion_diagnostico(_diagnostico_base())

    assert observacion.startswith("Diagnóstico previo Excel:")
    assert "registro_operacional_excel" in observacion
    assert "Registro" in observacion
