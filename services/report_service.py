from audit import audit_log
from data import anexar_registro, crear_registro
from ui.form_helpers import limpiar_valores_etiquetas, texto_lista, texto_lista_enteros
from utils import unir_valores
from validation import report_validation


def _registrar_rechazo_validacion(*, operador, modelo_equipo, numero_equipo, turno, mensaje):
    audit_log.registrar_guardado_rechazado(
        usuario=operador,
        equipo=modelo_equipo,
        numero_equipo=numero_equipo,
        turno=turno,
        detalle=mensaje,
    )
    audit_log.registrar_error_validacion(
        usuario=operador,
        equipo=modelo_equipo,
        numero_equipo=numero_equipo,
        turno=turno,
        detalle=mensaje,
    )


def _rechazar_validacion(*, tipo, mensaje, operador, modelo_equipo, numero_equipo, turno):
    _registrar_rechazo_validacion(
        operador=operador,
        modelo_equipo=modelo_equipo,
        numero_equipo=numero_equipo,
        turno=turno,
        mensaje=mensaje,
    )
    return {"ok": False, "tipo": tipo, "mensaje": mensaje}


def validar_datos_para_guardado(
    *,
    total_horas,
    horas_turno,
    operador,
    modelo_equipo,
    numero_equipo,
    turno,
    fecha_turno=None,
    horometro_inicial=None,
    horometro_final=None,
    diferencia_horometro=None,
    metros_perforados=None,
    pozos_perforados=None,
    valores_numericos=None,
):
    if not report_validation.horas_turno_validas(total_horas, horas_turno):
        mensaje = report_validation.mensaje_horas_turno_invalidas(total_horas, horas_turno)
        return _rechazar_validacion(
            tipo="horas_invalidas",
            mensaje=mensaje,
            operador=operador,
            modelo_equipo=modelo_equipo,
            numero_equipo=numero_equipo,
            turno=turno,
        )

    if not report_validation.operador_valido(operador):
        mensaje = report_validation.mensaje_operador_vacio()
        return _rechazar_validacion(
            tipo="operador_vacio",
            mensaje=mensaje,
            operador=operador,
            modelo_equipo=modelo_equipo,
            numero_equipo=numero_equipo,
            turno=turno,
        )

    if fecha_turno is not None and not report_validation.fecha_turno_valida(fecha_turno):
        mensaje = report_validation.mensaje_fecha_turno_invalida()
        return _rechazar_validacion(
            tipo="fecha_turno_invalida",
            mensaje=mensaje,
            operador=operador,
            modelo_equipo=modelo_equipo,
            numero_equipo=numero_equipo,
            turno=turno,
        )

    if not report_validation.turno_valido(turno):
        mensaje = report_validation.mensaje_turno_vacio()
        return _rechazar_validacion(
            tipo="turno_vacio",
            mensaje=mensaje,
            operador=operador,
            modelo_equipo=modelo_equipo,
            numero_equipo=numero_equipo,
            turno=turno,
        )

    if not report_validation.equipo_tiene_numero(numero_equipo):
        mensaje = report_validation.mensaje_equipo_sin_numero()
        return _rechazar_validacion(
            tipo="equipo_sin_numero",
            mensaje=mensaje,
            operador=operador,
            modelo_equipo=modelo_equipo,
            numero_equipo=numero_equipo,
            turno=turno,
        )

    if metros_perforados is not None and not report_validation.metros_validos(metros_perforados):
        mensaje = report_validation.mensaje_metros_invalidos()
        return _rechazar_validacion(
            tipo="metros_invalidos",
            mensaje=mensaje,
            operador=operador,
            modelo_equipo=modelo_equipo,
            numero_equipo=numero_equipo,
            turno=turno,
        )

    if pozos_perforados is not None and not report_validation.pozos_validos(pozos_perforados):
        mensaje = report_validation.mensaje_pozos_invalidos()
        return _rechazar_validacion(
            tipo="pozos_invalidos",
            mensaje=mensaje,
            operador=operador,
            modelo_equipo=modelo_equipo,
            numero_equipo=numero_equipo,
            turno=turno,
        )

    if horometro_inicial is not None or horometro_final is not None:
        if not report_validation.horometro_valido(
            horometro_inicial,
            horometro_final,
            diferencia_horometro,
        ):
            mensaje = report_validation.mensaje_horometro_invalido()
            return _rechazar_validacion(
                tipo="horometro_invalido",
                mensaje=mensaje,
                operador=operador,
                modelo_equipo=modelo_equipo,
                numero_equipo=numero_equipo,
                turno=turno,
            )

    negativos = report_validation.valores_numericos_negativos(valores_numericos or {})
    if negativos:
        mensaje = report_validation.mensaje_valores_negativos(negativos.keys())
        return _rechazar_validacion(
            tipo="valores_negativos",
            mensaje=mensaje,
            operador=operador,
            modelo_equipo=modelo_equipo,
            numero_equipo=numero_equipo,
            turno=turno,
        )

    return {"ok": True, "tipo": "", "mensaje": ""}


def integrar_causa_en_observaciones(observaciones, causa_detencion):
    observaciones = str(observaciones or "").strip()
    causa_detencion = str(causa_detencion or "").strip()
    if not causa_detencion:
        return observaciones
    texto_causa = f"Causa detención histórica: {causa_detencion}"
    if causa_detencion.lower() in observaciones.lower() or texto_causa.lower() in observaciones.lower():
        return observaciones
    return f"{observaciones}\n{texto_causa}" if observaciones else texto_causa


def construir_datos_registro(datos_formulario):
    identificacion = datos_formulario["identificacion"]
    ubicacion = datos_formulario["ubicacion"]
    produccion = datos_formulario["produccion"]
    horas = datos_formulario["horas"]
    kpi = datos_formulario["kpi"]

    tipo_perforacion = ubicacion["tipo_perforacion"]
    horas_cambios_aceros = horas.get("horas_cambios_aceros", horas.get("horas_cambio_aceros", 0.0))
    horas_otros = horas.get("horas_otros", 0.0)
    causa_detencion = produccion.get("causa_detencion", "")
    observaciones = integrar_causa_en_observaciones(
        produccion["observaciones"],
        causa_detencion,
    )

    return {
        "Modelo equipo": identificacion["modelo_equipo"],
        "Número equipo": identificacion["numero_equipo"],
        "Operador": identificacion["operador"],
        "Turno": identificacion["turno"],
        "Código operador": identificacion["codigo_operador"],
        "Fecha turno": identificacion["fecha_turno"],
        "Área operacional": identificacion["area_operacional"],
        "Petróleo litros": produccion["petroleo"],
        "Horómetro inicial": produccion["horometro_inicial"],
        "Horómetro final": produccion["horometro_final"],
        "Diferencia horómetro": produccion["diferencia_horometro"],
        "Horas de motor": produccion["diferencia_horometro"],
        "Banco": texto_lista_enteros(limpiar_valores_etiquetas(ubicacion["banco"], enteros=True)),
        "Malla": texto_lista(limpiar_valores_etiquetas(ubicacion["malla"])),
        "Fase": texto_lista_enteros(limpiar_valores_etiquetas(ubicacion["fase"], enteros=True)),
        "Tipo de perforación": unir_valores(tipo_perforacion),
        "Número precorte": ubicacion["numero_precorte"] if "Precorte" in tipo_perforacion else "",
        "Número serie Tricono/Bit": ubicacion["numero_bit"],
        "Condición del terreno": texto_lista(limpiar_valores_etiquetas(ubicacion["condicion_terreno"])),
        "Tipo detención": unir_valores(produccion["tipo_detencion"]),
        "Causa detención": causa_detencion,
        "Horas detención mecánica": horas["horas_averia"],
        "Horas detención No efectivas": horas["horas_no_efectivas"],
        "Horas efectivas perforando": horas["horas_efectivas"],
        "Combustible": horas["horas_combustible"],
        "Relleno de agua": horas["horas_agua"],
        "Colación": horas["horas_colacion"],
        "Traslado": horas["horas_traslado"],
        "Standby por falta de tajo/Patio": horas["horas_standby"],
        "Tronadura": horas["horas_tronadura"],
        "Mantención Programada": horas["horas_mantencion"],
        "Cambio de aceros": horas_cambios_aceros,
        "Avería": horas["horas_averia"],
        "Cambio turno": horas["horas_cambio_turno"],
        "Falta operador": horas["horas_falta_operador"],
        "Otros": horas_otros,
        "Total horas ingresadas": horas["total_horas"],
        "Metros perforados": produccion["metros"],
        "Pozos perforados turno": produccion["pozos"],
        "Rendimiento m/h": round(kpi["rendimiento_turno"], 2),
        "Disponibilidad %": round(kpi["disponibilidad"], 2),
        "Utilización": round(kpi["utilizacion"], 2),
        "Observaciones": observaciones,
        "Estatus del Equipo": produccion.get("estatus_equipo", ""),
    }


def ejecutar_guardado_reporte(datos_formulario):
    registro = crear_registro(construir_datos_registro(datos_formulario))
    mensaje_permission_error = "No se pudo guardar. Cierra el archivo Excel y vuelve a intentar."

    try:
        _, ruta_guardado, ruta_respaldo = anexar_registro(registro)
    except PermissionError:
        identificacion = datos_formulario["identificacion"]
        audit_log.registrar_evento(
            "creacion_reporte",
            usuario=identificacion["operador"],
            equipo=identificacion["modelo_equipo"],
            numero_equipo=identificacion["numero_equipo"],
            turno=identificacion["turno"],
            resultado="error",
            detalle=mensaje_permission_error,
        )
        return {
            "ok": False,
            "tipo": "permission_error",
            "mensaje": mensaje_permission_error,
            "registro": registro,
            "ruta_guardado": None,
            "ruta_respaldo": None,
        }
    except Exception as exc:
        identificacion = datos_formulario["identificacion"]
        mensaje_error = str(exc) or "No se pudo guardar el reporte."
        audit_log.registrar_evento(
            "creacion_reporte",
            usuario=identificacion["operador"],
            equipo=identificacion["modelo_equipo"],
            numero_equipo=identificacion["numero_equipo"],
            turno=identificacion["turno"],
            resultado="error",
            detalle=mensaje_error,
        )
        return {
            "ok": False,
            "tipo": "guardado_error",
            "mensaje": mensaje_error,
            "registro": registro,
            "ruta_guardado": None,
            "ruta_respaldo": None,
        }

    audit_log.registrar_creacion_reporte(registro)
    return {
        "ok": True,
        "tipo": "guardado",
        "mensaje": "",
        "registro": registro,
        "ruta_guardado": ruta_guardado,
        "ruta_respaldo": ruta_respaldo,
    }
