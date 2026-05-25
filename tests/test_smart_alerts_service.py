import db
from services import smart_alerts_service


def _insertar_registros_alerta(db_path):
    registros = [
        {
            "Fecha turno": "2026-05-20",
            "Turno": "Día",
            "Modelo equipo": "FlexiROC D65",
            "Número equipo": "9274",
            "Operador": "Ana Soto",
            "Metros perforados": 140,
            "Horas efectivas perforando": 10,
            "Horas detención No efectivas": 5,
            "Horas detención mecánica": 2,
            "Utilización %": 45,
            "Disponibilidad %": 62,
            "Rendimiento m/h": 14,
            "Tipo detención": "Repaso, Avería mecánica",
            "Causa detención": "Repaso de taladro",
            "Cambio de aceros": 3,
            "Observaciones": "repaso visible",
        },
        {
            "Fecha turno": "2026-05-21",
            "Turno": "Día",
            "Modelo equipo": "FlexiROC D65",
            "Número equipo": "9274",
            "Operador": "Ana Soto",
            "Metros perforados": 130,
            "Horas efectivas perforando": 10,
            "Horas detención No efectivas": 2,
            "Horas detención mecánica": 2,
            "Utilización %": 82,
            "Disponibilidad %": 88,
            "Rendimiento m/h": 13,
            "Tipo detención": "Avería mecánica",
            "Causa detención": "Avería repetida",
            "Cambio de aceros": 0,
        },
        {
            "Fecha turno": "2026-05-22",
            "Turno": "Día",
            "Modelo equipo": "FlexiROC D65",
            "Número equipo": "9274",
            "Operador": "Ana Soto",
            "Metros perforados": 80,
            "Horas efectivas perforando": 10,
            "Horas detención No efectivas": 4,
            "Horas detención mecánica": 3,
            "Utilización %": 50,
            "Disponibilidad %": 65,
            "Rendimiento m/h": 8,
            "Tipo detención": "Avería mecánica",
            "Causa detención": "Avería recurrente",
            "Cambio de aceros": 4,
        },
        {
            "Fecha turno": "2026-05-23",
            "Turno": "Noche",
            "Modelo equipo": "FlexiROC D65",
            "Número equipo": "9274",
            "Operador": "Luis Perez",
            "Metros perforados": 220,
            "Horas efectivas perforando": 10,
            "Horas detención No efectivas": 1,
            "Horas detención mecánica": 0,
            "Utilización %": 92,
            "Disponibilidad %": 98,
            "Rendimiento m/h": 22,
            "Tipo detención": "Combustible",
            "Causa detención": "Cambio de turno",
            "Cambio de aceros": 1,
        },
        {
            "Fecha turno": "2026-05-24",
            "Turno": "Noche",
            "Modelo equipo": "FlexiROC D65",
            "Número equipo": "9274",
            "Operador": "Carlos Rondon",
            "Metros perforados": 100,
            "Horas efectivas perforando": 10,
            "Horas detención No efectivas": 1,
            "Horas detención mecánica": 0,
            "Utilización %": 70,
            "Disponibilidad %": 85,
            "Rendimiento m/h": 10,
            "Tipo detención": "Colación",
            "Causa detención": "Turno estable",
            "Cambio de aceros": 0,
        },
    ]

    for registro in registros:
        db.insertar_registro(registro, db_path=db_path, source="test")


def test_motor_alertas_detecta_alertas_y_persiste_estado(tmp_path):
    db_path = tmp_path / "reportes_test.db"
    _insertar_registros_alerta(db_path)

    resultado = smart_alerts_service.ejecutar_motor_alertas(db_path=db_path)
    alertas = smart_alerts_service.obtener_alertas_inteligentes(db_path=db_path)
    resumen = smart_alerts_service.resumen_alertas_inteligentes(db_path=db_path)

    assert resultado["registros_procesados"] == 5
    assert resultado["nuevas_alertas"] > 0
    assert len(alertas) == resultado["nuevas_alertas"]
    assert smart_alerts_service.obtener_ultimo_registro_procesado(db_path=db_path) == 5
    assert resumen["total"] == len(alertas)
    assert resumen["pendientes"] == len(alertas)

    causas = set(alertas["causa"].astype(str))
    assert "Baja utilización" in causas
    assert "Baja disponibilidad" in causas
    assert "Rendimiento bajo promedio" in causas
    assert "Exceso de horas no efectivas" in causas
    assert "Exceso de repaso" in causas
    assert "Exceso de cambios de aceros" in causas


def test_motor_alertas_es_idempotente_y_soporta_reconocimiento(tmp_path):
    db_path = tmp_path / "reportes_test.db"
    _insertar_registros_alerta(db_path)

    primero = smart_alerts_service.ejecutar_motor_alertas(db_path=db_path)
    segundo = smart_alerts_service.ejecutar_motor_alertas(db_path=db_path)
    alertas = smart_alerts_service.obtener_alertas_inteligentes(db_path=db_path)

    assert primero["nuevas_alertas"] > 0
    assert segundo["nuevas_alertas"] == 0
    assert len(alertas) == primero["nuevas_alertas"]

    claves = alertas.head(2)["alert_key"].tolist()
    actualizadas = smart_alerts_service.marcar_alertas_estado(claves, "vista", db_path=db_path)
    alertas_vistas = smart_alerts_service.obtener_alertas_inteligentes(db_path=db_path, estado=["vista"])
    actualizadas_atendida = smart_alerts_service.marcar_alertas_estado(claves, "atendida", db_path=db_path)
    alertas_atendidas = smart_alerts_service.obtener_alertas_inteligentes(db_path=db_path, estado=["atendida"])

    assert actualizadas == len(claves)
    assert len(alertas_vistas) == len(claves)
    assert actualizadas_atendida == len(claves)
    assert len(alertas_atendidas) == len(claves)


def test_motor_alertas_permite_filtrar_por_criticidad(tmp_path):
    db_path = tmp_path / "reportes_test.db"
    _insertar_registros_alerta(db_path)
    smart_alerts_service.ejecutar_motor_alertas(db_path=db_path)

    criticas = smart_alerts_service.obtener_alertas_inteligentes(
        db_path=db_path,
        criticidad=["CRÍTICA"],
    )
    preventivas = smart_alerts_service.obtener_alertas_inteligentes(
        db_path=db_path,
        criticidad=["PREVENTIVA"],
    )

    assert not criticas.empty
    assert not preventivas.empty
    assert set(criticas["criticidad"].astype(str)) == {"CRÍTICA"}
    assert set(preventivas["criticidad"].astype(str)) == {"PREVENTIVA"}
