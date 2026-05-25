from services import report_service
from services.report_service import validar_datos_para_guardado


def bloquear_auditoria(monkeypatch):
    llamadas = []

    def registrar_guardado_rechazado(**kwargs):
        llamadas.append(("guardado_rechazado", kwargs))

    def registrar_error_validacion(**kwargs):
        llamadas.append(("error_validacion", kwargs))

    monkeypatch.setattr(
        report_service.audit_log,
        "registrar_guardado_rechazado",
        registrar_guardado_rechazado,
    )
    monkeypatch.setattr(
        report_service.audit_log,
        "registrar_error_validacion",
        registrar_error_validacion,
    )
    return llamadas


def parametros_base(**overrides):
    parametros = {
        "total_horas": 12,
        "horas_turno": 12,
        "operador": "Valeria Millan",
        "modelo_equipo": "Sandvik D75KS",
        "numero_equipo": "9277",
        "turno": "Noche",
    }
    parametros.update(overrides)
    return parametros


def test_validar_datos_para_guardado_horas_validas_retorna_ok_true(monkeypatch):
    llamadas = bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(**parametros_base())

    assert resultado == {"ok": True, "tipo": "", "mensaje": ""}
    assert llamadas == []


def test_validar_datos_para_guardado_horas_invalidas(monkeypatch):
    llamadas = bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(**parametros_base(total_horas=0))

    assert resultado["ok"] is False
    assert resultado["tipo"] == "horas_invalidas"
    assert resultado["mensaje"] == "No se puede guardar. El turno suma 0.00 h y debe sumar 12.00 h."
    assert [llamada[0] for llamada in llamadas] == ["guardado_rechazado", "error_validacion"]
    assert llamadas[0][1]["detalle"] == resultado["mensaje"]
    assert llamadas[1][1]["detalle"] == resultado["mensaje"]


def test_validar_datos_para_guardado_operador_vacio(monkeypatch):
    llamadas = bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(**parametros_base(operador="   "))

    assert resultado["ok"] is False
    assert resultado["tipo"] == "operador_vacio"
    assert resultado["mensaje"] == "Debe ingresar el nombre del operador."
    assert [llamada[0] for llamada in llamadas] == ["guardado_rechazado", "error_validacion"]
    assert llamadas[0][1]["usuario"] == "   "
    assert llamadas[0][1]["detalle"] == resultado["mensaje"]
    assert llamadas[1][1]["detalle"] == resultado["mensaje"]


def test_validar_datos_para_guardado_prioriza_horas_sobre_operador(monkeypatch):
    llamadas = bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(**parametros_base(total_horas=0, operador=""))

    assert resultado["ok"] is False
    assert resultado["tipo"] == "horas_invalidas"
    assert resultado["mensaje"] == "No se puede guardar. El turno suma 0.00 h y debe sumar 12.00 h."
    assert [llamada[0] for llamada in llamadas] == ["guardado_rechazado", "error_validacion"]
