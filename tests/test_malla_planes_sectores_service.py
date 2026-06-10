from contextlib import closing
import sqlite3

from services import malla_service


def test_crear_tablas_planes_y_sectores_perforacion(tmp_path):
    db_path = tmp_path / "malla_planes.db"

    malla_service.asegurar_tablas(db_path=db_path)

    with closing(sqlite3.connect(db_path)) as connection:
        tablas = {
            fila[0]
            for fila in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "planes_perforacion" in tablas
    assert "sectores_perforacion" in tablas


def test_registrar_plan_y_sector_perforacion(tmp_path):
    db_path = tmp_path / "malla_planes.db"
    plan = malla_service.registrar_plan_perforacion(
        {
            "nombre_plan": "Plan Banco 101",
            "fase": "F1",
            "banco": "101",
            "fecha_plan": "2026-06-04",
            "observacion": "Plan inicial",
        },
        db_path=db_path,
    )

    sector = malla_service.registrar_sector_perforacion(
        {
            "plan_id": plan["plan_id"],
            "tipo_sector": "Producción",
            "identificador_sector": "Producción Malla 114",
            "malla": "114",
            "secuencia_tronadura": "T-01",
            "pozos_planificados": 25,
            "metros_planificados": 300,
            "pasadura": "1.5",
            "diametro": "10.5",
            "estado": "Planificado",
            "observacion": "",
        },
        db_path=db_path,
    )

    assert plan["ok"] is True
    assert sector["ok"] is True
    sectores = malla_service.listar_sectores_perforacion(db_path=db_path, plan_id=plan["plan_id"])
    assert len(sectores) == 1
    assert sectores.iloc[0]["malla"] == "114"
    assert sectores.iloc[0]["pasadura"] == "1.5"
    assert sectores.iloc[0]["diametro"] == "10.5"


def test_validar_sector_perforacion_reglas_obligatorias():
    sin_tipo = malla_service.validar_sector_perforacion({"tipo_sector": ""})
    precorte_sin_numero = malla_service.validar_sector_perforacion({"tipo_sector": "Precorte"})
    produccion_sin_malla = malla_service.validar_sector_perforacion({"tipo_sector": "Producción"})
    negativos = malla_service.validar_sector_perforacion(
        {"tipo_sector": "Otro", "pozos_planificados": -1, "metros_planificados": -5}
    )

    assert sin_tipo["ok"] is False
    assert precorte_sin_numero["ok"] is False
    assert produccion_sin_malla["ok"] is False
    assert negativos["ok"] is False


def test_resumen_plan_perforacion_por_tipos_sector(tmp_path):
    db_path = tmp_path / "malla_planes.db"
    plan = malla_service.registrar_plan_perforacion(
        {"nombre_plan": "Plan F2", "fase": "F2", "banco": "120"},
        db_path=db_path,
    )
    registros = [
        {"tipo_sector": "Producción", "identificador_sector": "Malla 115", "malla": "115", "metros_planificados": 200, "pozos_planificados": 10},
        {"tipo_sector": "Buffer 1", "identificador_sector": "Buffer 1", "metros_planificados": 80, "pozos_planificados": 4},
        {"tipo_sector": "Buffer 2", "identificador_sector": "Buffer 2", "metros_planificados": 60, "pozos_planificados": 3},
        {"tipo_sector": "Precorte", "identificador_sector": "Precorte 01", "numero_precorte": "01", "metros_planificados": 40, "pozos_planificados": 2},
    ]
    for registro in registros:
        registro["plan_id"] = plan["plan_id"]
        resultado = malla_service.registrar_sector_perforacion(registro, db_path=db_path)
        assert resultado["ok"] is True

    resumen = malla_service.resumen_plan_perforacion(plan["plan_id"], db_path=db_path)

    assert resumen["total_sectores"] == 4
    assert resumen["total_pozos_planificados"] == 19
    assert resumen["total_metros_planificados"] == 380
    assert resumen["produccion_planificada"] == 200
    assert resumen["buffer_planificado"] == 140
    assert resumen["precorte_planificado"] == 40


def test_actualizar_sector_perforacion_audita_cambios(tmp_path):
    db_path = tmp_path / "malla_planes.db"
    plan = malla_service.registrar_plan_perforacion(
        {"nombre_plan": "Plan editable", "fase": "F1", "banco": "101"},
        db_path=db_path,
    )
    sector = malla_service.registrar_sector_perforacion(
        {
            "plan_id": plan["plan_id"],
            "tipo_sector": "Producción",
            "identificador_sector": "Malla 114",
            "malla": "114",
            "pozos_planificados": 10,
            "metros_planificados": 100,
        },
        db_path=db_path,
    )

    resultado = malla_service.actualizar_sector_perforacion(
        sector["sector_id"],
        {"malla": "115", "metros_planificados": 120},
        motivo="Corrección de plano",
        usuario="tester",
        db_path=db_path,
    )

    auditoria = malla_service.leer_auditoria_sectores_perforacion(sector["sector_id"], db_path=db_path)
    actualizado = malla_service.obtener_sector_perforacion(sector["sector_id"], db_path=db_path)

    assert resultado["ok"] is True
    assert set(resultado["campos"]) == {"malla", "metros_planificados"}
    assert actualizado["malla"] == "115"
    assert len(auditoria) == 2
    assert set(auditoria["campo"]) == {"malla", "metros_planificados"}


def test_desactivar_sector_perforacion_no_borra_y_excluye_listado(tmp_path):
    db_path = tmp_path / "malla_planes.db"
    plan = malla_service.registrar_plan_perforacion(
        {"nombre_plan": "Plan desactivar", "fase": "F1", "banco": "101"},
        db_path=db_path,
    )
    sector = malla_service.registrar_sector_perforacion(
        {
            "plan_id": plan["plan_id"],
            "tipo_sector": "Buffer 1",
            "identificador_sector": "Buffer norte",
            "pozos_planificados": 4,
            "metros_planificados": 80,
        },
        db_path=db_path,
    )

    resultado = malla_service.desactivar_sector_perforacion(
        sector["sector_id"],
        motivo="Sector duplicado",
        usuario="tester",
        db_path=db_path,
    )

    activos = malla_service.listar_sectores_perforacion(db_path=db_path, plan_id=plan["plan_id"])
    todos = malla_service.listar_sectores_perforacion(db_path=db_path, plan_id=plan["plan_id"], incluir_inactivos=True)
    auditoria = malla_service.leer_auditoria_sectores_perforacion(sector["sector_id"], db_path=db_path)

    assert resultado["ok"] is True
    assert activos.empty
    assert len(todos) == 1
    assert int(todos.iloc[0]["activo"]) == 0
    assert auditoria.iloc[0]["campo"] == "activo"
