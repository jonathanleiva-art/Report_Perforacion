from pathlib import Path

from services import malla_service


class FakeUpload:
    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getbuffer(self):
        return self._data


def _configurar(monkeypatch, tmp_path):
    db_path = tmp_path / "malla_control_simple.db"
    planos_dir = tmp_path / "data" / "planos_malla"
    monkeypatch.setattr(malla_service.db, "DB_PATH", db_path)
    monkeypatch.setattr(malla_service, "PLANOS_MALLA_DIR", planos_dir)
    return db_path, planos_dir


def test_registrar_archivo_plano_malla_y_registrar_pozos_control(monkeypatch, tmp_path):
    db_path, planos_dir = _configurar(monkeypatch, tmp_path)
    archivo = FakeUpload("plano_control.pdf", b"pdf-bytes")

    plano = malla_service.registrar_archivo_plano_malla(archivo, db_path=db_path)
    assert plano["ok"] is True
    assert Path(plano["registro"]["ruta_archivo"]).parent == planos_dir

    primero = malla_service.registrar_pozo_malla_control(
        {
            "archivo_plano_id": plano["archivo_id"],
            "numero_pozo": "1",
            "tipo_pozo": "Producción",
            "metros_planificados": 12.5,
            "estado": "pendiente",
            "realizado": False,
            "observacion": "Inicial",
        },
        db_path=db_path,
    )
    segundo = malla_service.registrar_pozo_malla_control(
        {
            "archivo_plano_id": plano["archivo_id"],
            "numero_pozo": "2",
            "tipo_pozo": "Buffer",
            "metros_planificados": 10,
            "estado": "realizado",
            "realizado": True,
            "observacion": "Hecho",
        },
        db_path=db_path,
    )

    assert primero["ok"] is True
    assert segundo["ok"] is True

    pozos = malla_service.listar_pozos_malla_control(db_path=db_path, archivo_plano_id=plano["archivo_id"])
    assert len(pozos) == 2
    assert set(pozos["estado"].tolist()) == {"pendiente", "realizado"}
    assert bool(pozos.iloc[1]["realizado"]) is True


def test_actualizar_pozo_malla_control_y_resumen(monkeypatch, tmp_path):
    db_path, _ = _configurar(monkeypatch, tmp_path)
    plano = malla_service.registrar_archivo_plano_malla(FakeUpload("plano_control.pdf", b"x"), db_path=db_path)
    pozo = malla_service.registrar_pozo_malla_control(
        {
            "archivo_plano_id": plano["archivo_id"],
            "numero_pozo": "10",
            "tipo_pozo": "Precorte",
            "metros_planificados": 8,
            "estado": "pendiente",
            "realizado": False,
            "observacion": "Pendiente inicial",
        },
        db_path=db_path,
    )

    actualizado = malla_service.actualizar_pozo_malla_control(
        pozo["pozo_id"],
        {
            "numero_pozo": "10",
            "tipo_pozo": "Precorte",
            "metros_planificados": 9.5,
            "estado": "realizado",
            "realizado": True,
            "observacion": "Marcado como realizado",
        },
        db_path=db_path,
    )

    assert actualizado["ok"] is True
    assert actualizado["registro"]["estado"] == "realizado"
    assert bool(actualizado["registro"]["realizado"]) is True

    resumen = malla_service.resumen_malla_control(db_path=db_path, archivo_plano_id=plano["archivo_id"])
    assert resumen["pozos_totales"] == 1
    assert resumen["pozos_realizados"] == 1
    assert resumen["pozos_pendientes"] == 0
    assert float(resumen["metros_planificados_totales"]) == 9.5
    assert float(resumen["metros_realizados_estimados"]) == 9.5
    assert float(resumen["porcentaje_avance"]) == 100.0
    assert float(resumen["avance_metros"]) == 100.0


def test_limpiar_avance_malla_limpia_tablas_nuevas(monkeypatch, tmp_path):
    db_path, _ = _configurar(monkeypatch, tmp_path)
    plano = malla_service.registrar_archivo_plano_malla(FakeUpload("plano_control.pdf", b"x"), db_path=db_path)
    malla_service.registrar_pozo_malla_control(
        {
            "archivo_plano_id": plano["archivo_id"],
            "numero_pozo": "1",
            "tipo_pozo": "Otro",
            "metros_planificados": 1,
            "estado": "pendiente",
            "realizado": False,
            "observacion": "",
        },
        db_path=db_path,
    )

    resultado = malla_service.limpiar_avance_malla(db_path=db_path, limpiar_archivos=True)

    assert resultado["ok"] is True
    assert malla_service.listar_archivos_planos_malla(db_path=db_path).empty
    assert malla_service.listar_pozos_malla_control(db_path=db_path).empty
