from unicodedata import normalize

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


def _clave_operacional(valor):
    texto = normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    if texto.startswith("producci"):
        return "produccion"
    return texto


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
    tipo_sector=None,
    malla=None,
    numero_precorte=None,
    valores_numericos=None,
    horas_averia=None,
    horas_mantencion=None,
    horas_efectivas=None,
    horas_no_efectivas=None,
    horas_standby=None,
    horas_tronadura=None,
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

    requiere_ubicacion_perforacion = (
        float(metros_perforados or 0) > 0
        or float(horas_efectivas or 0) > 0
    )
    tipo_sector_clave = _clave_operacional(tipo_sector)
    if tipo_sector_clave == "precorte" and not str(numero_precorte or "").strip():
        return _rechazar_validacion(
            tipo="precorte_sin_numero",
            mensaje="Si el tipo de sector es Precorte, debe ingresar numero de precorte.",
            operador=operador,
            modelo_equipo=modelo_equipo,
            numero_equipo=numero_equipo,
            turno=turno,
        )

    if tipo_sector_clave == "produccion" and requiere_ubicacion_perforacion:
        mallas = malla if isinstance(malla, (list, tuple, set)) else [malla]
        if not any(str(valor or "").strip() for valor in mallas):
            return _rechazar_validacion(
                tipo="produccion_sin_malla",
                mensaje="Si el tipo de sector es Produccion, debe ingresar malla.",
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

    if horas_efectivas is not None and report_validation.turno_improductivo_sin_causa(
        horas_efectivas,
        metros_perforados if metros_perforados is not None else 0,
        horas_averia or 0, horas_mantencion or 0,
        horas_standby or 0, horas_tronadura or 0, horas_no_efectivas or 0,
    ):
        return _rechazar_validacion(
            tipo="turno_sin_causa",
            mensaje=report_validation.mensaje_turno_sin_causa(),
            operador=operador,
            modelo_equipo=modelo_equipo,
            numero_equipo=numero_equipo,
            turno=turno,
        )

    advertencias = []
    if horas_no_efectivas is not None and report_validation.horas_sin_categorizar(
        horas_averia or 0, horas_mantencion or 0, horas_no_efectivas,
    ):
        advertencias.append(report_validation.mensaje_horas_sin_categorizar())

    return {"ok": True, "tipo": "", "mensaje": "", "advertencias": advertencias}


def integrar_causa_en_observaciones(observaciones, causa_detencion):
    observaciones = str(observaciones or "").strip()
    causa_detencion = str(causa_detencion or "").strip()
    if not causa_detencion:
        return observaciones
    texto_causa = f"Causa detención histórica: {causa_detencion}"
    if causa_detencion.lower() in observaciones.lower() or texto_causa.lower() in observaciones.lower():
        return observaciones
    return f"{observaciones}\n{texto_causa}" if observaciones else texto_causa


def _tipos_desde_sectores(sectores):
    tipos = []
    for sector in sectores or []:
        tipo = str(sector.get("tipo", "") or "").strip()
        if tipo and tipo not in tipos:
            tipos.append(tipo)
    return tipos


def _numero_precorte_desde_sectores(sectores):
    for sector in sectores or []:
        if sector.get("tipo") == "Precorte":
            numero = str(
                sector.get("numero", "") or sector.get("numero_precorte", "") or ""
            ).strip()
            if numero:
                return numero
    return ""


def construir_datos_registro(datos_formulario):
    identificacion = datos_formulario["identificacion"]
    ubicacion = datos_formulario["ubicacion"]
    produccion = datos_formulario["produccion"]
    horas = datos_formulario["horas"]
    kpi = datos_formulario["kpi"]

    sectores = ubicacion.get("sectores", [])
    tipos_sector = _tipos_desde_sectores(sectores)
    tipo_perforacion = ubicacion.get("tipo_perforacion") or tipos_sector
    identificador_sector = ubicacion.get("identificador_sector", "")
    # Compat backward: tipo_sector y numero_precorte del primer sector
    tipo_sector = sectores[0].get("tipo", "") if sectores else ubicacion.get("tipo_sector", "")
    numero_precorte_operacional = (
        sectores[0].get("numero", "") or sectores[0].get("numero_precorte", "")
        if sectores and sectores[0].get("tipo") == "Precorte"
        else _numero_precorte_desde_sectores(sectores) or ubicacion.get("numero_precorte", "") or ubicacion.get("numero", "")
    )
    sectores_trabajados = unir_valores(tipos_sector or tipo_perforacion)
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
        "Sectores trabajados": sectores_trabajados,
        "Tipo de perforación": unir_valores(tipo_perforacion),
        "Número precorte": numero_precorte_operacional if "Precorte" in tipo_perforacion else "",
        "tipo_sector": tipo_sector,
        "numero_precorte": numero_precorte_operacional if _clave_operacional(tipo_sector) == "precorte" else "",
        "identificador_sector": identificador_sector,
        "sectores_json": ubicacion.get("sectores_json", ""),
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
    import traceback as _tb
    registro = crear_registro(construir_datos_registro(datos_formulario))
    mensaje_permission_error = "No se pudo guardar. Cierra el archivo Excel y vuelve a intentar."

    try:
        _, ruta_guardado, ruta_respaldo, nuevo_id = anexar_registro(registro)
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
        # Incluye traceback completo para diagnóstico — remover después de resolver el bug
        tb_str = _tb.format_exc()
        mensaje_error = f"{exc!r}\n\nTraceback:\n{tb_str}"
        audit_log.registrar_evento(
            "creacion_reporte",
            usuario=identificacion["operador"],
            equipo=identificacion["modelo_equipo"],
            numero_equipo=identificacion["numero_equipo"],
            turno=identificacion["turno"],
            resultado="error",
            detalle=str(exc),
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

    try:
        datos_id = datos_formulario.get("identificacion", {})
        datos_ub = datos_formulario.get("ubicacion", {})
        datos_prod = datos_formulario.get("produccion", {})
        banco = str(datos_ub.get("banco", "")).strip()
        fase = str(datos_ub.get("fase", "")).strip()
        malla = str(datos_ub.get("malla", "")).strip()
        tipo_pf_raw = datos_ub.get("tipo_perforacion", [])
        tipo = unir_valores(tipo_pf_raw) if isinstance(tipo_pf_raw, (list, tuple)) else str(tipo_pf_raw).strip()
        if banco and fase and malla:
            import db as _db
            with _db.conectar_db() as conn:
                conn.execute(
                    """
                    INSERT INTO avance_malla
                    (banco, fase, numero_malla, tipo_perforacion,
                     operador, equipo, numero_equipo, turno,
                     fecha_turno, pozos_perforados, metros_perforados)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        banco, fase, malla, tipo,
                        str(datos_id.get("operador", "")),
                        str(datos_id.get("modelo_equipo", "")),
                        str(datos_id.get("numero_equipo", "")),
                        str(datos_id.get("turno", "")),
                        str(datos_id.get("fecha_turno", "")),
                        int(datos_prod.get("pozos", 0)),
                        float(datos_prod.get("metros", 0)),
                    ),
                )
                conn.commit()
    except Exception as e:
        print(f"avance_malla insert error: {e}")

    try:
        tipo_sector_val = str(registro["tipo_sector"].iloc[0]).strip() if "tipo_sector" in registro.columns else ""
        if tipo_sector_val and nuevo_id:
            import db as _db
            _db.upsert_clasificacion_operacional(
                nuevo_id,
                tipo_sector=tipo_sector_val,
                numero_precorte=str(registro["numero_precorte"].iloc[0]).strip() if "numero_precorte" in registro.columns else "",
                identificador_sector=str(registro["identificador_sector"].iloc[0]).strip() if "identificador_sector" in registro.columns else "",
                usuario=str(datos_formulario.get("identificacion", {}).get("operador", "")),
            )
    except Exception as e:
        print(f"clasificacion_operacional dual-write error: {e}")

    return {
        "ok": True,
        "tipo": "guardado",
        "mensaje": "",
        "registro": registro,
        "ruta_guardado": ruta_guardado,
        "ruta_respaldo": ruta_respaldo,
    }
