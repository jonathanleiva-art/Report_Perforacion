from pathlib import Path

import pandas as pd

from services import report_service
from services.report_service import ejecutar_guardado_reporte


def datos_formulario_minimos():
    return {
        "identificacion": {
            "modelo_equipo": "FlexiROC D65",
            "numero_equipo": "9274",
            "operador": "Valeria Millan",
            "turno": "Noche",
            "codigo_operador": "M-0001",
            "fecha_turno": "2026-05-23",
            "area_operacional": "Proyecto DES",
        },
        "ubicacion": {
            "banco": ["2360"],
            "malla": ["254"],
            "fase": ["2"],
            "tipo_perforacion": ["Producción"],
            "numero_precorte": 0,
            "numero_bit": "BIT-123",
            "condicion_terreno": ["Blando"],
        },
        "produccion": {
            "petroleo": 0,
            "horometro_inicial": 100,
            "horometro_final": 112,
            "diferencia_horometro": 12,
            "tipo_detencion": [],
            "causa_detencion": "",
            "metros": 100,
            "pozos": 8,
            "observaciones": "",
        },
        "horas": {
            "horas_averia": 0,
            "horas_no_efectivas": 0,
            "horas_efectivas": 12,
            "horas_combustible": 0,
            "horas_agua": 0,
            "horas_colacion": 0,
            "horas_traslado": 0,
            "horas_standby": 0,
            "horas_tronadura": 0,
            "horas_mantencion": 0,
            "horas_cambio_turno": 0,
            "horas_falta_operador": 0,
            "horas_otros": 0,
            "total_horas": 12,
        },
        "kpi": {
            "rendimiento_turno": 8.33,
            "disponibilidad": 100,
            "utilizacion": 100,
        },
    }


def test_ejecutar_guardado_reporte_exitoso_retorna_resultado(monkeypatch):
    llamadas = []
    registro = pd.DataFrame([{"Operador": "Valeria Millan", "Hora registro": "10:00:00"}])
    ruta_guardado = Path("reportes_perforacion.xlsx")
    ruta_respaldo = Path("backup/respaldo.xlsx")

    def crear_registro(payload):
        llamadas.append(("crear_registro", payload))
        return registro

    def anexar_registro(registro_recibido):
        llamadas.append(("anexar_registro", registro_recibido))
        return pd.DataFrame(), ruta_guardado, ruta_respaldo, 246

    def registrar_creacion_reporte(registro_recibido):
        llamadas.append(("registrar_creacion_reporte", registro_recibido))

    monkeypatch.setattr(report_service, "crear_registro", crear_registro)
    monkeypatch.setattr(report_service, "anexar_registro", anexar_registro)
    monkeypatch.setattr(report_service.audit_log, "registrar_creacion_reporte", registrar_creacion_reporte)

    resultado = ejecutar_guardado_reporte(datos_formulario_minimos())

    assert resultado["ok"] is True
    assert resultado["tipo"] == "guardado"
    assert resultado["mensaje"] == ""
    assert resultado["registro"] is registro
    assert resultado["ruta_guardado"] == ruta_guardado
    assert resultado["ruta_respaldo"] == ruta_respaldo
    assert [llamada[0] for llamada in llamadas] == [
        "crear_registro",
        "anexar_registro",
        "registrar_creacion_reporte",
    ]
    assert llamadas[1][1] is registro
    assert llamadas[2][1] is registro


def test_ejecutar_guardado_reporte_permission_error_retorna_error(monkeypatch):
    llamadas = []
    registro = pd.DataFrame([{"Operador": "Valeria Millan", "Hora registro": "10:00:00"}])

    def crear_registro(payload):
        llamadas.append(("crear_registro", payload))
        return registro

    def anexar_registro(registro_recibido):
        llamadas.append(("anexar_registro", registro_recibido))
        raise PermissionError("archivo bloqueado")

    def registrar_creacion_reporte(registro_recibido):
        llamadas.append(("registrar_creacion_reporte", registro_recibido))

    def registrar_evento(*args, **kwargs):
        llamadas.append(("registrar_evento", args, kwargs))

    monkeypatch.setattr(report_service, "crear_registro", crear_registro)
    monkeypatch.setattr(report_service, "anexar_registro", anexar_registro)
    monkeypatch.setattr(report_service.audit_log, "registrar_creacion_reporte", registrar_creacion_reporte)
    monkeypatch.setattr(report_service.audit_log, "registrar_evento", registrar_evento)

    resultado = ejecutar_guardado_reporte(datos_formulario_minimos())

    assert resultado["ok"] is False
    assert resultado["tipo"] == "permission_error"
    assert resultado["mensaje"] == "No se pudo guardar. Cierra el archivo Excel y vuelve a intentar."
    assert resultado["registro"] is registro
    assert resultado["ruta_guardado"] is None
    assert resultado["ruta_respaldo"] is None
    assert "registrar_creacion_reporte" not in [llamada[0] for llamada in llamadas]
    assert [llamada[0] for llamada in llamadas] == [
        "crear_registro",
        "anexar_registro",
        "registrar_evento",
    ]
    assert llamadas[2][1] == ("creacion_reporte",)
    assert llamadas[2][2]["resultado"] == "error"


def test_ejecutar_guardado_reporte_error_guardado_retorna_error(monkeypatch):
    llamadas = []
    registro = pd.DataFrame([{"Operador": "Valeria Millan", "Hora registro": "10:00:00"}])

    def crear_registro(payload):
        llamadas.append(("crear_registro", payload))
        return registro

    def anexar_registro(registro_recibido):
        llamadas.append(("anexar_registro", registro_recibido))
        raise RuntimeError("No se pudo guardar el reporte en SQLite.")

    def registrar_evento(*args, **kwargs):
        llamadas.append(("registrar_evento", args, kwargs))

    monkeypatch.setattr(report_service, "crear_registro", crear_registro)
    monkeypatch.setattr(report_service, "anexar_registro", anexar_registro)
    monkeypatch.setattr(report_service.audit_log, "registrar_evento", registrar_evento)

    resultado = ejecutar_guardado_reporte(datos_formulario_minimos())

    assert resultado["ok"] is False
    assert resultado["tipo"] == "guardado_error"
    assert resultado["mensaje"] == "No se pudo guardar el reporte en SQLite."
    assert resultado["registro"] is registro
    assert resultado["ruta_guardado"] is None
    assert resultado["ruta_respaldo"] is None
    assert [llamada[0] for llamada in llamadas] == [
        "crear_registro",
        "anexar_registro",
        "registrar_evento",
    ]
    assert llamadas[2][1] == ("creacion_reporte",)
    assert llamadas[2][2]["resultado"] == "error"
