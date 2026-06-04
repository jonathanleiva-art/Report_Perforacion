from pathlib import Path

from services import import_diagnostic_service, import_execution_service, source_service


def _crear_fuente(db_path, archivo, estado="diagnosticada", tipo=None):
    return source_service.crear_fuente_datos(
        nombre_fuente="Fuente prueba",
        tipo_fuente=tipo or import_diagnostic_service.TIPO_REGISTRO_OPERACIONAL,
        archivo_origen=str(archivo) if archivo is not None else None,
        total_registros=3,
        fecha_min="2026-05-01",
        fecha_max="2026-05-03",
        estado=estado,
        db_path=db_path,
    )


def test_validar_fuente_importable_rechaza_fuente_inexistente(tmp_path):
    resultado = import_execution_service.validar_fuente_importable(
        999,
        db_path=tmp_path / "fuentes.db",
    )

    assert not resultado["ok"]
    assert resultado["mensaje"] == "La fuente no existe."


def test_validar_fuente_importable_rechaza_estado_no_diagnosticada(tmp_path):
    db_path = tmp_path / "fuentes.db"
    archivo = tmp_path / "registro.xlsx"
    archivo.write_bytes(b"contenido")
    id_fuente = _crear_fuente(db_path, archivo, estado="activa")

    resultado = import_execution_service.validar_fuente_importable(id_fuente, db_path=db_path)

    assert not resultado["ok"]
    assert resultado["estado"] == "activa"
    assert "diagnosticada" in resultado["mensaje"]


def test_importar_fuente_desconocida_queda_error_importacion(tmp_path):
    db_path = tmp_path / "fuentes.db"
    archivo = tmp_path / "desconocido.xlsx"
    archivo.write_bytes(b"contenido")
    id_fuente = _crear_fuente(
        db_path,
        archivo,
        tipo=import_diagnostic_service.TIPO_DESCONOCIDO,
    )

    resultado = import_execution_service.importar_fuente_diagnosticada(
        id_fuente,
        db_path=db_path,
        imports_dir=tmp_path / "imports",
    )

    fuente = source_service.obtener_fuente_por_id(id_fuente, db_path=db_path)
    assert not resultado["ok"]
    assert resultado["estado"] == import_execution_service.ESTADO_ERROR_IMPORTACION
    assert fuente["estado"] == import_execution_service.ESTADO_ERROR_IMPORTACION


def test_importar_fuente_con_archivo_inexistente_queda_error_importacion(tmp_path):
    db_path = tmp_path / "fuentes.db"
    id_fuente = _crear_fuente(db_path, tmp_path / "no_existe.xlsx")

    resultado = import_execution_service.importar_fuente_diagnosticada(
        id_fuente,
        db_path=db_path,
        imports_dir=tmp_path / "imports",
    )

    fuente = source_service.obtener_fuente_por_id(id_fuente, db_path=db_path)
    assert not resultado["ok"]
    assert resultado["estado"] == import_execution_service.ESTADO_ERROR_IMPORTACION
    assert fuente["estado"] == import_execution_service.ESTADO_ERROR_IMPORTACION


def test_copiar_archivo_a_imports_no_sobrescribe(tmp_path):
    origen = tmp_path / "registro.xlsx"
    origen.write_bytes(b"uno")
    imports_dir = tmp_path / "imports"

    primera = import_execution_service.copiar_archivo_a_imports(origen, imports_dir=imports_dir)
    segunda = import_execution_service.copiar_archivo_a_imports(origen, imports_dir=imports_dir)

    assert primera.exists()
    assert segunda.exists()
    assert primera != segunda
    assert primera.name == "registro.xlsx"
    assert segunda.name == "registro_1.xlsx"
    assert primera.read_bytes() == b"uno"
    assert segunda.read_bytes() == b"uno"


def test_importar_fuente_soportada_queda_pendiente_importador(tmp_path):
    db_path = tmp_path / "fuentes.db"
    archivo = tmp_path / "ciclos.xlsx"
    archivo.write_bytes(b"contenido")
    id_fuente = _crear_fuente(
        db_path,
        archivo,
        tipo=import_diagnostic_service.TIPO_CICLOS,
    )

    resultado = import_execution_service.importar_fuente_diagnosticada(
        id_fuente,
        db_path=db_path,
        imports_dir=tmp_path / "imports",
    )

    fuente = source_service.obtener_fuente_por_id(id_fuente, db_path=db_path)
    assert resultado["ok"]
    assert resultado["estado"] == import_execution_service.ESTADO_PENDIENTE_IMPORTADOR
    assert resultado["registros_importados"] == 0
    assert Path(resultado["ruta_imports"]).exists()
    assert fuente["estado"] == import_execution_service.ESTADO_PENDIENTE_IMPORTADOR
    assert "pendiente" in fuente["observacion"].lower()


def test_importar_fuente_actualiza_error_si_falla_la_copia(tmp_path, monkeypatch):
    db_path = tmp_path / "fuentes.db"
    archivo = tmp_path / "operacional.xlsx"
    archivo.write_bytes(b"contenido")
    id_fuente = _crear_fuente(db_path, archivo)

    def _fallar_copia(*args, **kwargs):
        raise RuntimeError("sin permisos")

    monkeypatch.setattr(import_execution_service, "copiar_archivo_a_imports", _fallar_copia)

    resultado = import_execution_service.importar_fuente_diagnosticada(
        id_fuente,
        db_path=db_path,
        imports_dir=tmp_path / "imports",
    )

    fuente = source_service.obtener_fuente_por_id(id_fuente, db_path=db_path)
    assert not resultado["ok"]
    assert resultado["estado"] == import_execution_service.ESTADO_ERROR_IMPORTACION
    assert "sin permisos" in resultado["mensaje"]
    assert fuente["estado"] == import_execution_service.ESTADO_ERROR_IMPORTACION
