import sqlite3

from services import malla_service


def _configurar_db_temporal(monkeypatch, tmp_path):
    db_path = tmp_path / "malla_avance.db"
    monkeypatch.setattr(malla_service.db, "DB_PATH", db_path)
    return db_path


def _datos_malla():
    return {
        "banco": "B1",
        "fase": "F1",
        "malla": "M-01",
        "descripcion": "Malla inicial",
        "fecha": "2026-05-24",
        "turno": "Día",
    }


def _datos_pozo(numero, estado, planificados, perforados):
    return {
        "banco": "B1",
        "fase": "F1",
        "malla": "M-01",
        "numero_pozo": str(numero),
        "tipo_pozo": "Primario",
        "estado": estado,
        "metros_planificados": planificados,
        "metros_perforados": perforados,
        "operador": "Operador Base",
        "equipo": "Equipo 1",
        "fecha": "2026-05-24",
        "turno": "Día",
    }


def test_asegurar_tablas_crea_mallas_y_pozos(monkeypatch, tmp_path):
    db_path = _configurar_db_temporal(monkeypatch, tmp_path)

    malla_service.asegurar_tablas(db_path=db_path)

    with sqlite3.connect(db_path) as connection:
        tablas = {
            fila[0]
            for fila in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert malla_service.TABLA_MALLAS in tablas
    assert malla_service.TABLA_POZOS in tablas


def test_registrar_malla_es_idempotente(monkeypatch, tmp_path):
    db_path = _configurar_db_temporal(monkeypatch, tmp_path)

    resultado_1 = malla_service.registrar_malla(_datos_malla(), db_path=db_path)
    resultado_2 = malla_service.registrar_malla(_datos_malla(), db_path=db_path)
    resumen = malla_service.listar_mallas(db_path=db_path)

    assert resultado_1["ok"] is True
    assert resultado_2["ok"] is True
    assert resultado_1["malla_id"] == resultado_2["malla_id"]
    assert len(resumen) == 1
    assert resumen.iloc[0]["pozos_totales"] == 0


def test_registrar_pozo_y_resumen_avance(monkeypatch, tmp_path):
    db_path = _configurar_db_temporal(monkeypatch, tmp_path)

    malla_service.registrar_malla(_datos_malla(), db_path=db_path)
    malla_service.registrar_pozo(_datos_pozo(1, "pendiente", 10, 0), db_path=db_path)
    malla_service.registrar_pozo(_datos_pozo(2, "perforado", 10, 8), db_path=db_path)
    malla_service.registrar_pozo(_datos_pozo(3, "repaso", 10, 7), db_path=db_path)
    malla_service.registrar_pozo(_datos_pozo(4, "desconocido", 5, 0), db_path=db_path)

    resumen = malla_service.resumen_avance_malla(db_path=db_path)
    pozos = malla_service.listar_pozos(db_path=db_path)

    assert len(pozos) == 4
    assert len(resumen) == 1
    fila = resumen.iloc[0]
    assert fila["pozos_totales"] == 4
    assert fila["pozos_perforados"] == 1
    assert fila["pozos_pendientes"] == 2
    assert float(fila["metros_planificados"]) == 35.0
    assert float(fila["metros_perforados"]) == 15.0
    assert float(fila["porcentaje_avance"]) == 42.86


def test_registrar_pozo_actualiza_si_repite_numero(monkeypatch, tmp_path):
    db_path = _configurar_db_temporal(monkeypatch, tmp_path)

    malla_service.registrar_malla(_datos_malla(), db_path=db_path)
    primero = malla_service.registrar_pozo(_datos_pozo(1, "pendiente", 10, 0), db_path=db_path)
    segundo = malla_service.registrar_pozo(_datos_pozo(1, "perforado", 10, 9), db_path=db_path)
    pozos = malla_service.listar_pozos(db_path=db_path)

    assert primero["pozo_id"] == segundo["pozo_id"]
    assert len(pozos) == 1
    assert pozos.iloc[0]["estado"] == "perforado"
    assert float(pozos.iloc[0]["metros_perforados"]) == 9.0
