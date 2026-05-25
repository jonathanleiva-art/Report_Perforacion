from services import malla_service


def _configurar_db_y_directorio(monkeypatch, tmp_path):
    db_path = tmp_path / "malla_planos_edicion.db"
    planos_dir = tmp_path / "data" / "planos_malla"
    monkeypatch.setattr(malla_service.db, "DB_PATH", db_path)
    monkeypatch.setattr(malla_service, "PLANOS_MALLA_DIR", planos_dir)
    return db_path, planos_dir


def _datos_plano():
    return {
        "nombre_plano": "Plano Edicion",
        "banco": "B1",
        "fase": "F1",
        "malla": "M-01",
        "fecha": "2026-05-24",
        "turno": "Día",
        "observacion": "Plano para edicion",
    }


def test_editar_pozo_plano_actualiza_campos_y_observacion(monkeypatch, tmp_path):
    db_path, _ = _configurar_db_y_directorio(monkeypatch, tmp_path)
    plano = malla_service.registrar_plano_malla(_datos_plano(), archivo_subido=None, db_path=db_path)
    pozo = malla_service.registrar_pozo_plano(
        {
            "plano_id": plano["plano_id"],
            "numero_pozo": "1",
            "tipo_pozo": "Primario",
            "metros_planificados": 10,
            "estado_inicial": "pendiente",
            "coordenada_x": 0,
            "coordenada_y": 0,
            "observacion": "Original",
        },
        db_path=db_path,
    )

    resultado = malla_service.editar_pozo_plano(
        pozo["pozo_id"],
        {
            "coordenada_x": 12.5,
            "coordenada_y": -7.25,
            "tipo_pozo": "Repaso",
            "metros_planificados": 14,
            "estado": "perforado",
            "observacion": "Actualizado manualmente",
        },
        db_path=db_path,
    )

    assert resultado["ok"] is True
    registro = resultado["registro"]
    assert float(registro["coordenada_x"]) == 12.5
    assert float(registro["coordenada_y"]) == -7.25
    assert registro["tipo_pozo"] == "Repaso"
    assert float(registro["metros_planificados"]) == 14.0
    assert registro["estado_inicial"] == "perforado"
    assert registro["observacion"] == "Actualizado manualmente"


def test_editar_pozo_plano_rechaza_inexistente(monkeypatch, tmp_path):
    db_path, _ = _configurar_db_y_directorio(monkeypatch, tmp_path)

    resultado = malla_service.editar_pozo_plano(
        9999,
        {
            "coordenada_x": 1,
            "coordenada_y": 1,
            "tipo_pozo": "Primario",
            "metros_planificados": 5,
            "estado": "pendiente",
            "observacion": "No debe existir",
        },
        db_path=db_path,
    )

    assert resultado["ok"] is False
    assert resultado["pozo_id"] is None


def test_listar_pozos_plano_incluye_observacion(monkeypatch, tmp_path):
    db_path, _ = _configurar_db_y_directorio(monkeypatch, tmp_path)
    plano = malla_service.registrar_plano_malla(_datos_plano(), archivo_subido=None, db_path=db_path)
    malla_service.registrar_pozo_plano(
        {
            "plano_id": plano["plano_id"],
            "numero_pozo": "2",
            "tipo_pozo": "Primario",
            "metros_planificados": 8,
            "estado_inicial": "pendiente",
            "coordenada_x": 3,
            "coordenada_y": 4,
            "observacion": "Observacion visible",
        },
        db_path=db_path,
    )

    pozos = malla_service.listar_pozos_plano(db_path=db_path, plano_id=plano["plano_id"])

    assert len(pozos) == 1
    assert pozos.iloc[0]["observacion"] == "Observacion visible"
