from services import data_source_selector_service as selector_service
from services import source_adapter_service, source_routing_helpers


def test_mensaje_orientacion_manual_sqlite():
    mensaje = source_routing_helpers.obtener_mensaje_orientacion(
        selector_service.TIPO_MANUAL_SQLITE,
        source_adapter_service.SOPORTE_COMPLETO,
    )

    assert mensaje == "Usar Dashboard principal."


def test_mensaje_orientacion_registro_operacional_excel_completo():
    mensaje = source_routing_helpers.obtener_mensaje_orientacion(
        selector_service.TIPO_REGISTRO_OPERACIONAL_EXCEL,
        source_adapter_service.SOPORTE_COMPLETO,
    )

    assert mensaje == "Usar Dashboard Excel Operacional."


def test_mensaje_orientacion_ciclos_perforacion_parcial():
    mensaje = source_routing_helpers.obtener_mensaje_orientacion(
        selector_service.TIPO_CICLOS_PERFORACION,
        source_adapter_service.SOPORTE_PARCIAL,
    )

    assert mensaje == "Dashboard de ciclos pendiente de integración."


def test_mensaje_orientacion_desconocido_no_soportado():
    mensaje = source_routing_helpers.obtener_mensaje_orientacion(
        selector_service.TIPO_DESCONOCIDO,
        source_adapter_service.SOPORTE_NO_SOPORTADO,
    )

    assert mensaje == "Fuente no soportada por el sistema actual."
