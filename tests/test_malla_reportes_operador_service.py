from pathlib import Path

from services import malla_service


class FakeUpload:
    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getbuffer(self):
        return self._data


def _configurar_db_y_directorios(monkeypatch, tmp_path):
    db_path = tmp_path / "malla_reportes_operador.db"
    planos_dir = tmp_path / "data" / "planos_malla"
    reportes_dir = tmp_path / "data" / "reportes_operadores"
    monkeypatch.setattr(malla_service.db, "DB_PATH", db_path)
    monkeypatch.setattr(malla_service, "PLANOS_MALLA_DIR", planos_dir)
    monkeypatch.setattr(malla_service, "REPORTES_OPERADORES_DIR", reportes_dir)
    return db_path, planos_dir, reportes_dir


def _datos_plano():
    return {
        "nombre_plano": "Plano Foto 01",
        "banco": "B1",
        "fase": "F1",
        "malla": "M-01",
        "fecha": "2026-05-24",
        "turno": "Día",
        "observacion": "Plano para validacion de foto",
    }


def _datos_reporte():
    return {
        "operador": "Operador Foto",
        "equipo": "Equipo Foto",
        "fecha": "2026-05-24",
        "turno": "Día",
        "banco": "B1",
        "fase": "F1",
        "malla": "M-01",
        "observacion": "Reporte fotografico manual",
    }


def test_registrar_reporte_operador_guarda_archivo_y_metadatos(monkeypatch, tmp_path):
    db_path, _, reportes_dir = _configurar_db_y_directorios(monkeypatch, tmp_path)
    malla_service.registrar_plano_malla(_datos_plano(), archivo_subido=None, db_path=db_path)
    archivo = FakeUpload("foto_operador.pdf", b"pdf-bytes")

    resultado = malla_service.registrar_reporte_operador(_datos_reporte(), archivo_subido=archivo, db_path=db_path)

    assert resultado["ok"] is True
    assert resultado["reporte_id"] is not None
    registro = resultado["registro"]
    assert registro["operador"] == "Operador Foto"
    assert registro["archivo_foto"] == "foto_operador.pdf"
    assert registro["plano_id"] is not None
    assert Path(registro["archivo_ruta"]).exists()
    assert Path(registro["archivo_ruta"]).parent == reportes_dir


def test_registrar_detalle_reporte_operador_actualiza_y_marca_critico(monkeypatch, tmp_path):
    db_path, _, _ = _configurar_db_y_directorios(monkeypatch, tmp_path)
    plano = malla_service.registrar_plano_malla(_datos_plano(), archivo_subido=None, db_path=db_path)
    reporte = malla_service.registrar_reporte_operador(_datos_reporte(), archivo_subido=None, db_path=db_path)

    primero = malla_service.registrar_detalle_reporte_operador(
        {
            "reporte_id": reporte["reporte_id"],
            "numero_pozo": "1",
            "fase": "F1",
            "banco": "B1",
            "malla": "M-01",
            "tipo_perforacion": "Producción",
            "metros_planificados": 10,
            "metros_perforados": 8,
            "tiempo_perforacion": 2,
            "tricono_bit": "Bit 1",
            "operador": "Operador Foto",
            "equipo": "Equipo Foto",
            "fecha": "2026-05-24",
            "turno": "Día",
            "estado": "pendiente",
            "observacion": "Original",
            "es_critico": False,
            "motivo_critico": "",
        },
        db_path=db_path,
    )
    segundo = malla_service.registrar_detalle_reporte_operador(
        {
            "reporte_id": reporte["reporte_id"],
            "numero_pozo": "1",
            "fase": "F1",
            "banco": "B1",
            "malla": "M-01",
            "tipo_perforacion": "Producción",
            "metros_planificados": 12,
            "metros_perforados": 11,
            "tiempo_perforacion": 3,
            "tricono_bit": "Bit 2",
            "operador": "Operador Foto",
            "equipo": "Equipo Foto",
            "fecha": "2026-05-24",
            "turno": "Día",
            "estado": "perforado",
            "observacion": "Actualizado",
            "es_critico": True,
            "motivo_critico": "Requiere inspeccion",
        },
        db_path=db_path,
    )

    assert primero["detalle_id"] == segundo["detalle_id"]
    registro = segundo["registro"]
    assert float(registro["metros_planificados"]) == 12.0
    assert float(registro["metros_perforados"]) == 11.0
    assert registro["estado"] == "perforado"
    assert int(registro["es_critico"]) == 1
    assert registro["motivo_critico"] == "Requiere inspeccion"


def test_comparar_reporte_operador_con_plano_calcula_coincidencias_y_faltantes(monkeypatch, tmp_path):
    db_path, _, _ = _configurar_db_y_directorios(monkeypatch, tmp_path)
    plano = malla_service.registrar_plano_malla(_datos_plano(), archivo_subido=None, db_path=db_path)
    for numero, metros, estado in [
        ("1", 10, "pendiente"),
        ("2", 12, "perforado"),
        ("3", 8, "pendiente"),
    ]:
        malla_service.registrar_pozo_plano(
            {
                "plano_id": plano["plano_id"],
                "numero_pozo": numero,
                "tipo_pozo": "Primario",
                "metros_planificados": metros,
                "estado_inicial": estado,
                "coordenada_x": float(numero) * 10,
                "coordenada_y": float(numero) * 5,
            },
            db_path=db_path,
        )
    reporte = malla_service.registrar_reporte_operador(_datos_reporte(), archivo_subido=None, db_path=db_path)
    malla_service.registrar_detalle_reporte_operador(
        {
            "reporte_id": reporte["reporte_id"],
            "numero_pozo": "1",
            "fase": "F1",
            "banco": "B1",
            "malla": "M-01",
            "tipo_perforacion": "Producción",
            "metros_planificados": 10,
            "metros_perforados": 9,
            "tiempo_perforacion": 2,
            "tricono_bit": "Bit 1",
            "operador": "Operador Foto",
            "equipo": "Equipo Foto",
            "fecha": "2026-05-24",
            "turno": "Día",
            "estado": "perforado",
            "observacion": "Coincide",
            "es_critico": True,
            "motivo_critico": "Inspeccion",
        },
        db_path=db_path,
    )
    malla_service.registrar_detalle_reporte_operador(
        {
            "reporte_id": reporte["reporte_id"],
            "numero_pozo": "99",
            "fase": "F1",
            "banco": "B1",
            "malla": "M-01",
            "tipo_perforacion": "otro",
            "metros_planificados": 4,
            "metros_perforados": 4,
            "tiempo_perforacion": 1,
            "tricono_bit": "Bit 9",
            "operador": "Operador Foto",
            "equipo": "Equipo Foto",
            "fecha": "2026-05-24",
            "turno": "Día",
            "estado": "pendiente",
            "observacion": "No existe en plano",
            "es_critico": False,
            "motivo_critico": "",
        },
        db_path=db_path,
    )

    comparacion = malla_service.comparar_reporte_operador_con_plano(
        reporte["reporte_id"],
        db_path=db_path,
        plano_id=plano["plano_id"],
    )

    assert comparacion["ok"] is True
    assert comparacion["resumen"]["pozos_coincidentes"] == 1
    assert comparacion["resumen"]["pozos_no_encontrados_plano"] == 1
    assert comparacion["resumen"]["pozos_plan_no_reportados"] == 2
    assert float(comparacion["resumen"]["metros_perforados_total"]) == 13.0
    assert float(comparacion["resumen"]["metros_planificados_plano_total"]) == 30.0
    assert "diferencia_metros" in comparacion["coincidentes"].columns
    assert len(comparacion["no_encontrados_plano"]) == 1
    assert len(comparacion["plan_no_reportado"]) == 2
