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

    assert resultado == {"ok": True, "tipo": "", "mensaje": "", "advertencias": []}
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


def test_validar_datos_para_guardado_bloquea_fecha_invalida(monkeypatch):
    llamadas = bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(
        **parametros_base(fecha_turno="sin-fecha")
    )

    assert resultado["ok"] is False
    assert resultado["tipo"] == "fecha_turno_invalida"
    assert resultado["mensaje"] == "Fecha turno vacía o inválida."
    assert [llamada[0] for llamada in llamadas] == ["guardado_rechazado", "error_validacion"]


def test_validar_datos_para_guardado_bloquea_equipo_sin_numero(monkeypatch):
    llamadas = bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(**parametros_base(numero_equipo=""))

    assert resultado["ok"] is False
    assert resultado["tipo"] == "equipo_sin_numero"
    assert resultado["mensaje"] == "Equipo sin número."
    assert llamadas[0][1]["numero_equipo"] == ""


def test_validar_datos_para_guardado_bloquea_horometro_incoherente(monkeypatch):
    llamadas = bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(
        **parametros_base(
            horometro_inicial=120,
            horometro_final=100,
            diferencia_horometro=-20,
        )
    )

    assert resultado["ok"] is False
    assert resultado["tipo"] == "horometro_invalido"
    assert "Horómetro inválido" in resultado["mensaje"]
    assert [llamada[0] for llamada in llamadas] == ["guardado_rechazado", "error_validacion"]


def test_validar_datos_para_guardado_bloquea_pozos_no_enteros(monkeypatch):
    bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(
        **parametros_base(pozos_perforados=1.5)
    )

    assert resultado["ok"] is False
    assert resultado["tipo"] == "pozos_invalidos"
    assert resultado["mensaje"] == "Pozos perforados debe ser un número entero mayor o igual a cero."


def test_validar_datos_para_guardado_bloquea_valores_negativos(monkeypatch):
    bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(
        **parametros_base(valores_numericos={"Metros perforados": -1})
    )

    assert resultado["ok"] is False
    assert resultado["tipo"] == "valores_negativos"
    assert resultado["mensaje"] == "Valores numéricos negativos: Metros perforados"


def test_validar_datos_para_guardado_produccion_sin_malla_sin_actividad_permite(monkeypatch):
    llamadas = bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(
        **parametros_base(
            tipo_sector="Produccion",
            malla=[],
            metros_perforados=0,
            horas_efectivas=0,
            horas_standby=12,
        )
    )

    assert resultado == {"ok": True, "tipo": "", "mensaje": "", "advertencias": []}
    assert llamadas == []


def test_validar_datos_para_guardado_produccion_sin_malla_con_metros_rechaza(monkeypatch):
    llamadas = bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(
        **parametros_base(
            tipo_sector="Produccion",
            malla=[],
            metros_perforados=1,
            horas_efectivas=0,
        )
    )

    assert resultado["ok"] is False
    assert resultado["tipo"] == "produccion_sin_malla"
    assert resultado["mensaje"] == "Si el tipo de sector es Produccion, debe ingresar malla."
    assert [llamada[0] for llamada in llamadas] == ["guardado_rechazado", "error_validacion"]


def test_validar_datos_para_guardado_produccion_sin_malla_con_horas_rechaza(monkeypatch):
    llamadas = bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(
        **parametros_base(
            tipo_sector="Produccion",
            malla=[],
            metros_perforados=0,
            horas_efectivas=0.5,
        )
    )

    assert resultado["ok"] is False
    assert resultado["tipo"] == "produccion_sin_malla"
    assert resultado["mensaje"] == "Si el tipo de sector es Produccion, debe ingresar malla."
    assert [llamada[0] for llamada in llamadas] == ["guardado_rechazado", "error_validacion"]


def test_validar_datos_para_guardado_produccion_con_malla_y_actividad_permite(monkeypatch):
    llamadas = bloquear_auditoria(monkeypatch)

    resultado = validar_datos_para_guardado(
        **parametros_base(
            tipo_sector="Produccion",
            malla=["254"],
            metros_perforados=120,
            horas_efectivas=4,
        )
    )

    assert resultado == {"ok": True, "tipo": "", "mensaje": "", "advertencias": []}
    assert llamadas == []
