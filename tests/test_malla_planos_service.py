from pathlib import Path

from services import malla_service


class FakeUpload:
    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getbuffer(self):
        return self._data


def _configurar_db_y_directorio(monkeypatch, tmp_path):
    db_path = tmp_path / "malla_planos.db"
    planos_dir = tmp_path / "data" / "planos_malla"
    monkeypatch.setattr(malla_service.db, "DB_PATH", db_path)
    monkeypatch.setattr(malla_service, "PLANOS_MALLA_DIR", planos_dir)
    return db_path, planos_dir


def _datos_plano():
    return {
        "nombre_plano": "Plano Base 01",
        "banco": "B1",
        "fase": "F1",
        "malla": "M-01",
        "fecha": "2026-05-24",
        "turno": "Día",
        "observacion": "Carga manual inicial",
    }


def test_registrar_plano_malla_guarda_archivo_y_metadatos(monkeypatch, tmp_path):
    db_path, planos_dir = _configurar_db_y_directorio(monkeypatch, tmp_path)
    archivo = FakeUpload("plano_base.pdf", b"contenido-pdf")

    resultado = malla_service.registrar_plano_malla(_datos_plano(), archivo_subido=archivo, db_path=db_path)

    assert resultado["ok"] is True
    assert resultado["plano_id"] is not None
    registro = resultado["registro"]
    assert registro["nombre_plano"] == "Plano Base 01"
    assert registro["archivo_nombre"] == "plano_base.pdf"
    assert Path(registro["archivo_ruta"]).exists()
    assert Path(registro["archivo_ruta"]).parent == planos_dir


def test_registrar_plano_malla_actualiza_si_repite_clave(monkeypatch, tmp_path):
    db_path, _ = _configurar_db_y_directorio(monkeypatch, tmp_path)
    archivo_1 = FakeUpload("plano_1.png", b"uno")
    archivo_2 = FakeUpload("plano_2.png", b"dos")

    primero = malla_service.registrar_plano_malla(_datos_plano(), archivo_subido=archivo_1, db_path=db_path)
    segundo = malla_service.registrar_plano_malla(_datos_plano(), archivo_subido=archivo_2, db_path=db_path)

    assert primero["plano_id"] == segundo["plano_id"]
    assert segundo["registro"]["archivo_nombre"] == "plano_2.png"


def test_registrar_pozo_plano_y_resumen(monkeypatch, tmp_path):
    db_path, _ = _configurar_db_y_directorio(monkeypatch, tmp_path)
    plano = malla_service.registrar_plano_malla(_datos_plano(), archivo_subido=None, db_path=db_path)

    for numero, tipo, metros, estado in [
        ("1", "Primario", 10, "pendiente"),
        ("2", "Primario", 8, "perforado"),
        ("3", "Repaso", 6, "repaso"),
    ]:
        resultado = malla_service.registrar_pozo_plano(
            {
                "plano_id": plano["plano_id"],
                "numero_pozo": numero,
                "tipo_pozo": tipo,
                "metros_planificados": metros,
                "estado_inicial": estado,
                "coordenada_x": float(numero) * 10,
                "coordenada_y": float(numero) * -5,
            },
            db_path=db_path,
        )
        assert resultado["ok"] is True

    resumen = malla_service.resumen_planos_malla(db_path=db_path)
    pozos = malla_service.listar_pozos_plano(db_path=db_path, plano_id=plano["plano_id"])

    assert len(resumen) == 1
    fila = resumen.iloc[0]
    assert int(fila["total_pozos_registrados"]) == 3
    assert float(fila["metros_planificados"]) == 24.0
    assert "Primario" in fila["tipos_pozo"]
    assert "pendiente" in fila["estados"]
    assert len(pozos) == 3
    assert float(pozos.iloc[0]["coordenada_x"]) == 10.0
    assert float(pozos.iloc[0]["coordenada_y"]) == -5.0


def test_registrar_pozo_plano_rechaza_sin_plano_o_numero(monkeypatch, tmp_path):
    db_path, _ = _configurar_db_y_directorio(monkeypatch, tmp_path)

    resultado_sin_plano = malla_service.registrar_pozo_plano(
        {
            "plano_id": None,
            "numero_pozo": "1",
            "tipo_pozo": "Primario",
            "metros_planificados": 10,
            "estado_inicial": "pendiente",
        },
        db_path=db_path,
    )
    resultado_sin_numero = malla_service.registrar_pozo_plano(
        {
            "plano_id": 1,
            "numero_pozo": "",
            "tipo_pozo": "Primario",
            "metros_planificados": 10,
            "estado_inicial": "pendiente",
        },
        db_path=db_path,
    )

    assert resultado_sin_plano["ok"] is False
    assert resultado_sin_numero["ok"] is False
