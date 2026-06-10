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


def test_administracion_planos_malla_lista_plan_y_cantidad_sectores(monkeypatch, tmp_path):
    db_path, _, _ = _configurar(monkeypatch, tmp_path)
    archivo = malla_service.registrar_archivo_plano_malla(FakeUpload("DES_F01_B2296.pdf", b"pdf"), db_path=db_path)
    plan = malla_service.registrar_plan_perforacion(
        {
            "nombre_plan": "DES_F01_B2296",
            "archivo_pdf_id": archivo["archivo_id"],
            "fase": "1",
            "banco": "2296",
            "fecha_plan": "2026-06-05",
        },
        db_path=db_path,
    )
    malla_service.registrar_sector_perforacion(
        {
            "plan_id": plan["plan_id"],
            "tipo_sector": malla_service.TIPOS_SECTOR_PERFORACION[0],
            "malla": "114",
            "pozos_planificados": 10,
            "metros_planificados": 120,
        },
        db_path=db_path,
    )

    administracion = malla_service.listar_administracion_planos_malla(db_path=db_path)

    assert len(administracion) == 1
    assert administracion.iloc[0]["nombre_archivo"] == "DES_F01_B2296.pdf"
    assert administracion.iloc[0]["fase"] == "1"
    assert administracion.iloc[0]["banco"] == "2296"
    assert administracion.iloc[0]["cantidad_sectores"] == 1


def test_detectar_duplicado_plano_y_eliminar_con_auditoria(monkeypatch, tmp_path):
    db_path, _, _ = _configurar(monkeypatch, tmp_path)
    resultado = malla_service.registrar_archivo_plano_malla(FakeUpload("DES_F01_B2296.pdf", b"pdf"), db_path=db_path)

    duplicados = malla_service.detectar_duplicados_plano_malla(nombre_archivo="DES_F01_B2296.pdf", db_path=db_path)
    eliminado = malla_service.eliminar_plano_malla(
        resultado["archivo_id"],
        observacion="Duplicado de prueba",
        db_path=db_path,
    )
    auditoria = malla_service.listar_auditoria_planos_malla(db_path=db_path)

    assert len(duplicados) == 1
    assert eliminado["ok"] is True
    assert malla_service.listar_archivos_planos_malla(db_path=db_path).empty
    assert not Path(resultado["registro"]["ruta_archivo"]).exists()
    acciones = {str(valor).lower() for valor in auditoria["accion"]}
    assert "carga" in acciones
    assert any(valor.startswith("elimin") for valor in acciones)
