from services import data_source_selector_service as selector_service
from services import source_adapter_service


def obtener_mensaje_orientacion(tipo_fuente, soporte):
    tipo = str(tipo_fuente or "").strip()
    nivel_soporte = str(soporte or "").strip()

    if tipo == selector_service.TIPO_MANUAL_SQLITE:
        return "Usar Dashboard principal."
    if (
        tipo == selector_service.TIPO_REGISTRO_OPERACIONAL_EXCEL
        and nivel_soporte == source_adapter_service.SOPORTE_COMPLETO
    ):
        return "Usar Dashboard Excel Operacional."
    if (
        tipo == selector_service.TIPO_CICLOS_PERFORACION
        and nivel_soporte == source_adapter_service.SOPORTE_PARCIAL
    ):
        return "Dashboard de ciclos pendiente de integración."
    if nivel_soporte == source_adapter_service.SOPORTE_NO_SOPORTADO:
        return "Fuente no soportada por el sistema actual."
    return "Validar soporte antes de usar esta fuente."
