from datetime import date, timedelta

import pandas as pd

from services import corrective_actions_service


def _accion_base(**overrides):
    data = {
        "fecha": date.today(),
        "equipo": "FlexiROC D65 9272",
        "operador": "Ana Soto",
        "tipo_problema": "Baja utilización",
        "descripcion_problema": "Se detectó baja utilización en el turno.",
        "accion_correctiva": "Revisar secuencia operativa y detenciones.",
        "responsable": "Supervisor Mina",
        "prioridad": "Alta",
        "fecha_compromiso": date.today() + timedelta(days=2),
        "estado": "Pendiente",
        "observacion_final": "",
    }
    data.update(overrides)
    return data


def test_registrar_y_listar_accion_correctiva_crea_tabla(tmp_path):
    db_path = tmp_path / "reportes_perforacion.sqlite"
    accion = corrective_actions_service.registrar_accion_correctiva(_accion_base(), db_path=db_path)

    assert accion["id"] > 0
    df = corrective_actions_service.listar_acciones_correctivas(db_path=db_path)
    assert len(df) == 1
    assert "vencida" in df.columns
    assert "dias_para_compromiso" in df.columns
    assert df.iloc[0]["estado"] == "Pendiente"
    assert df.iloc[0]["prioridad"] == "Alta"


def test_actualizar_estado_accion_y_resumen(tmp_path):
    db_path = tmp_path / "reportes_perforacion.sqlite"
    accion = corrective_actions_service.registrar_accion_correctiva(
        _accion_base(fecha_compromiso=date.today() - timedelta(days=1), prioridad="Crítica"),
        db_path=db_path,
    )

    assert corrective_actions_service.actualizar_estado_accion(
        accion["id"],
        "Cerrado",
        observacion_final="Corregido y validado.",
        db_path=db_path,
    ) == 1

    actualizada = corrective_actions_service.obtener_accion_por_id(accion["id"], db_path=db_path)
    assert actualizada["estado"] == "Cerrado"
    assert actualizada["observacion_final"] == "Corregido y validado."

    resumen = corrective_actions_service.resumen_acciones_correctivas(db_path=db_path)
    assert resumen["total"] == 1
    assert resumen["pendientes"] == 0
    assert resumen["cerradas"] == 1
    assert resumen["criticas"] == 1


def test_crear_accion_desde_observacion_mapea_campos(tmp_path):
    db_path = tmp_path / "reportes_perforacion.sqlite"
    observacion = {
        "Fecha turno": "2026-05-20",
        "Modelo equipo": "FlexiROC D65",
        "Operador": "Ana Soto",
        "Regla": "Metros perforados = 0 con horas efectivas > 0",
        "Estado": "WARNING",
        "Mensaje": "Hay horas efectivas sin metros perforados.",
        "Recomendación operacional": "Revisar procedimiento operativo.",
    }

    accion = corrective_actions_service.crear_accion_desde_observacion(
        observacion,
        db_path=db_path,
        responsable="Supervisor Mina",
    )

    assert accion["id"] > 0
    assert accion["origen_fuente"] == "calidad_datos"
    assert accion["tipo_problema"] == "Metros perforados = 0 con horas efectivas > 0"
    assert accion["accion_correctiva"] == "Revisar procedimiento operativo."
    assert accion["prioridad"] in {"Alta", "Crítica"}


def test_listar_acciones_filtra_por_equipo_estado_y_responsable(tmp_path):
    db_path = tmp_path / "reportes_perforacion.sqlite"
    corrective_actions_service.registrar_accion_correctiva(_accion_base(equipo="Equipo A", responsable="Jefe A"), db_path=db_path)
    corrective_actions_service.registrar_accion_correctiva(_accion_base(equipo="Equipo B", responsable="Jefe B", estado="Cerrado"), db_path=db_path)

    filtradas = corrective_actions_service.listar_acciones_correctivas(
        db_path=db_path,
        equipo=["Equipo A"],
        estado=["Pendiente"],
        responsable=["Jefe A"],
    )
    assert len(filtradas) == 1
    assert filtradas.iloc[0]["equipo"] == "Equipo A"
    assert filtradas.iloc[0]["estado"] == "Pendiente"


def test_registrar_accion_correctiva_rechaza_campos_obligatorios_vacios(tmp_path):
    db_path = tmp_path / "reportes_perforacion.sqlite"
    try:
        corrective_actions_service.registrar_accion_correctiva({"fecha": date.today()}, db_path=db_path)
    except ValueError as exc:
        assert "obligatorio" in str(exc).lower()
    else:
        raise AssertionError("Se esperaba un ValueError por campos obligatorios vacíos.")
