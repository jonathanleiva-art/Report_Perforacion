from datetime import date, timedelta
from pathlib import Path
import sys

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from ui.page_header import render_page_header
from data import leer_reportes_sqlite as leer_reportes, limpiar_cache_reportes
from utils import EXCEL_PATH


def _formulario_wizard(df_historial):
    from services.report_service import ejecutar_guardado_reporte, validar_datos_para_guardado
    from services import kpi_service
    from ui.components import section_header
    from ui.forms_sections import (
        render_equipo_operador_fecha,
        render_horas_turno,
        render_produccion_consumos,
        render_ubicacion_condiciones,
    )
    from ui.formatting import dataframe_visible, texto_visible
    from utils import HORAS_TURNO

    PASOS = {
        1: "Identificación",
        2: "Producción y ubicación",
        3: "Horas del turno",
        4: "Confirmar y guardar",
    }

    if "wizard_paso" not in app.st.session_state:
        app.st.session_state["wizard_paso"] = 1

    form_version = app.st.session_state.get("form_version", 0)

    def k(nombre):
        return f"wiz_{nombre}_{form_version}"

    paso_actual = app.st.session_state["wizard_paso"]

    app.st.progress(
        paso_actual / len(PASOS),
        text=f"Paso {paso_actual} de {len(PASOS)}: {PASOS[paso_actual]}",
    )

    # ── Paso 1: Identificación ──────────────────────────────────────────
    if paso_actual == 1:
        section_header(
            "Datos del turno, equipo y operador",
            "Identificación base del reporte operacional.",
            kicker="Paso 1",
        )
        datos_ident = render_equipo_operador_fecha(k)
        app.st.session_state["_wiz_ident"] = datos_ident
        app.render_alerta_reporte_existente(
            datos_ident.get("fecha_turno"),
            datos_ident.get("turno", ""),
            datos_ident.get("numero_equipo", ""),
            datos_ident.get("modelo_equipo", ""),
            contenedor=app.st,
        )

    # ── Paso 2: Producción y ubicación ─────────────────────────────────
    elif paso_actual == 2:
        section_header(
            "Producción y observaciones",
            "Metros, pozos, horómetros, consumos y tipo de detención.",
            kicker="Paso 2",
        )
        datos_prod = render_produccion_consumos(k)
        app.st.session_state["_wiz_prod"] = datos_prod

        section_header(
            "Ubicación y condiciones",
            "Banco, malla, fase y condición del terreno.",
            kicker="Paso 2",
        )
        datos_ubic = render_ubicacion_condiciones(df_historial, k)
        app.st.session_state["_wiz_ubic"] = datos_ubic

    # ── Paso 3: Horas del turno ─────────────────────────────────────────
    elif paso_actual == 3:
        tipo_detencion = app.st.session_state.get("_wiz_prod", {}).get("tipo_detencion", [])
        section_header(
            "Horas del turno",
            "Distribución operacional de horas efectivas, averías y tiempos no efectivos.",
            kicker="Paso 3",
        )
        datos_horas = render_horas_turno(tipo_detencion, k)
        app.st.session_state["_wiz_horas"] = datos_horas

    # ── Paso 4: Confirmar y guardar ─────────────────────────────────────
    elif paso_actual == 4:
        datos_ident = app.st.session_state.get("_wiz_ident", {})
        datos_prod  = app.st.session_state.get("_wiz_prod", {})
        datos_ubic  = app.st.session_state.get("_wiz_ubic", {})
        datos_horas = app.st.session_state.get("_wiz_horas", {})

        modelo_equipo       = datos_ident.get("modelo_equipo", "")
        numero_equipo       = datos_ident.get("numero_equipo", "")
        operador            = datos_ident.get("operador") or ""
        turno               = datos_ident.get("turno", "")
        fecha_turno         = datos_ident.get("fecha_turno")
        metros              = float(datos_prod.get("metros") or 0)
        pozos               = int(datos_prod.get("pozos") or 0)
        petroleo            = float(datos_prod.get("petroleo") or 0)
        horometro_inicial   = float(datos_prod.get("horometro_inicial") or 0)
        horometro_final     = float(datos_prod.get("horometro_final") or 0)
        diferencia_horometro = round(horometro_final - horometro_inicial, 2)
        malla               = datos_ubic.get("malla", [])
        sectores            = datos_ubic.get("sectores", [])
        # Compat con validación existente: primer sector como referencia
        tipo_sector         = sectores[0].get("tipo", "") if sectores else ""
        numero_precorte     = (
            sectores[0].get("numero", "") or sectores[0].get("numero_precorte", "")
            if sectores and sectores[0].get("tipo") == "Precorte" else ""
        )
        horas_efectivas     = float(datos_horas.get("horas_efectivas") or 0)
        horas_averia        = float(datos_horas.get("horas_averia") or 0)
        horas_mantencion    = float(datos_horas.get("horas_mantencion") or 0)
        horas_no_efectivas  = float(datos_horas.get("horas_no_efectivas") or 0)
        horas_standby       = float(datos_horas.get("horas_standby") or 0)
        horas_traslado      = float(datos_horas.get("horas_traslado") or 0)
        horas_tronadura     = float(datos_horas.get("horas_tronadura") or 0)
        horas_otros         = float(datos_horas.get("horas_otros") or 0)
        total_horas         = float(datos_horas.get("total_horas") or 0)
        estatus_equipo      = datos_prod.get("estatus_equipo", "")
        observaciones       = datos_prod.get("observaciones", "")

        kpi_turno = kpi_service.calcular_kpi_operacional_productivo(
            metros=metros,
            pozos=pozos,
            horas_efectivas=horas_efectivas,
            horas_averia=horas_averia,
            horas_mantencion=horas_mantencion,
            horas_traslado=horas_traslado,
            horas_otros=horas_otros,
            horas_no_efectivas=horas_no_efectivas,
            horas_standby=horas_standby,
            estatus_equipo=estatus_equipo,
            observaciones=observaciones,
        )
        rendimiento   = kpi_turno["rendimiento"]
        utilizacion   = kpi_turno["utilizacion_productiva"]
        disponibilidad = kpi_turno["disponibilidad"]

        section_header("Resumen del turno", "Confirma los datos antes de guardar.", kicker="Paso 4")

        fecha_texto = (
            fecha_turno.strftime("%d-%m-%Y")
            if hasattr(fecha_turno, "strftime")
            else str(fecha_turno or "")
        )
        app.st.info(
            f"**Equipo:** {modelo_equipo} {numero_equipo}  \n"
            f"**Operador:** {operador} · **Turno:** {texto_visible(turno)} · **Fecha:** {fecha_texto}  \n"
            f"**Metros:** {metros:.1f} m · **Pozos:** {pozos}  \n"
            f"**Disponibilidad:** {disponibilidad:.0f}% · "
            f"**Utilización:** {utilizacion:.0f}% · "
            f"**Rendimiento:** {rendimiento:.1f} m/h"
        )

        for alerta in kpi_turno.get("alertas_coherencia", []):
            app.st.warning(texto_visible(alerta))

        if app.st.button("Guardar reporte", type="primary", key=k("guardar_wizard")):
            resultado_validacion = validar_datos_para_guardado(
                total_horas=total_horas,
                horas_turno=HORAS_TURNO,
                operador=operador,
                modelo_equipo=modelo_equipo,
                numero_equipo=numero_equipo,
                turno=turno,
                fecha_turno=fecha_turno,
                horometro_inicial=horometro_inicial,
                horometro_final=horometro_final,
                diferencia_horometro=diferencia_horometro,
                metros_perforados=metros,
                pozos_perforados=pozos,
                tipo_sector=tipo_sector,
                malla=malla,
                numero_precorte=numero_precorte,
                valores_numericos={
                    "Petróleo litros": petroleo,
                    "Horómetro inicial": horometro_inicial,
                    "Horómetro final": horometro_final,
                    "Diferencia horómetro": diferencia_horometro,
                    "Horas detención mecánica": horas_averia,
                    "Horas detención No efectivas": horas_no_efectivas,
                    "Horas efectivas perforando": horas_efectivas,
                    "Metros perforados": metros,
                    "Pozos perforados turno": pozos,
                },
                horas_averia=horas_averia,
                horas_mantencion=horas_mantencion,
                horas_efectivas=horas_efectivas,
                horas_no_efectivas=horas_no_efectivas,
                horas_standby=horas_standby,
                horas_tronadura=horas_tronadura,
            )
            for adv in resultado_validacion.get("advertencias", []):
                app.st.warning(texto_visible(adv))
            if not resultado_validacion["ok"]:
                app.st.error(texto_visible(resultado_validacion["mensaje"]))
            else:
                # ── Validar sectores Precorte ──────────────────────────────
                prec_sin_num = [
                    s for s in sectores
                    if s["tipo"] == "Precorte" and not str(s.get("numero", "")).strip()
                ]
                if prec_sin_num:
                    app.st.error(
                        f"{'Los sectores' if len(prec_sin_num) > 1 else 'El sector'} "
                        f"Precorte {'requieren' if len(prec_sin_num) > 1 else 'requiere'} "
                        f"número de precorte operacional."
                    )
                else:
                    reporte_existente, registro_existente = app.render_alerta_reporte_existente(
                        fecha_turno,
                        turno,
                        numero_equipo,
                        modelo_equipo,
                        contenedor=app.st,
                    )
                    if reporte_existente:
                        app.st.error(
                            "No se permite guardar un duplicado. "
                            "Para modificarlo use Edición Controlada o Reconciliación Reportes."
                        )
                    else:
                        datos_formulario = {
                            "identificacion": datos_ident,
                            "ubicacion": datos_ubic,
                            "produccion": {
                                **datos_prod,
                                "horometro_inicial": horometro_inicial,
                                "horometro_final": horometro_final,
                                "diferencia_horometro": diferencia_horometro,
                            },
                            "horas": datos_horas,
                            "kpi": {
                                "rendimiento_turno": rendimiento,
                                "disponibilidad": disponibilidad,
                                "utilizacion": utilizacion,
                            },
                        }
                        resultado_guardado = ejecutar_guardado_reporte(datos_formulario)
                        if not resultado_guardado["ok"]:
                            app.st.error(resultado_guardado["mensaje"])
                        else:
                            app.st.success("Reporte guardado correctamente.")
                            app.st.session_state["wizard_paso"] = 1
                            for clave in ["_wiz_ident", "_wiz_prod", "_wiz_ubic", "_wiz_horas"]:
                                app.st.session_state.pop(clave, None)
                            app.st.session_state["form_version"] = form_version + 1
                            limpiar_cache_reportes()
                            app.limpiar_cache_alertas()
                            app.st.rerun()

    # ── Navegación ──────────────────────────────────────────────────────
    app.st.divider()
    col_atras, _col_esp, col_sig = app.st.columns([1, 3, 1])
    with col_atras:
        if paso_actual > 1:
            if app.st.button("← Atrás", width="stretch", key="wiz_atras"):
                app.st.session_state["wizard_paso"] -= 1
                app.st.rerun()
    with col_sig:
        if paso_actual < len(PASOS):
            if app.st.button("Siguiente →", type="primary", width="stretch", key="wiz_siguiente"):
                app.st.session_state["wizard_paso"] += 1
                app.st.rerun()


def _panel_reportes_pendientes():
    from services.alert_service import EQUIPOS_REPORTES_REQUERIDOS, TURNOS_REPORTES_REQUERIDOS, get_reportes_faltantes

    hoy = date.today()
    fecha_desde = hoy - timedelta(days=6)
    faltantes = get_reportes_faltantes(fecha_desde=fecha_desde, fecha_hasta=hoy)

    app.st.divider()
    app.st.markdown("### Control de turnos pendientes — últimos 7 días")

    total = len(faltantes)
    fechas_n = int(faltantes["Fecha"].nunique()) if not faltantes.empty else 0

    col_m1, col_m2, col_m3 = app.st.columns(3)
    col_m1.metric("Días en rango", 7)
    col_m2.metric("Fechas con faltantes", fechas_n)
    col_m3.metric("Reportes pendientes", total, delta=f"-{total}" if total else None, delta_color="inverse")

    if faltantes.empty:
        app.st.markdown(
            '<div style="background:#0d0e10;border:1px solid #2ECC71;border-radius:6px;'
            'padding:10px 14px;margin-top:6px;">'
            '<span style="color:#2ECC71;font-size:0.88rem;">✓ Todos los turnos de los últimos 7 días están registrados.</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Group by date, most-recent first
    por_fecha = (
        faltantes
        .sort_values("Fecha", ascending=False)
        .groupby("Fecha", sort=False)
    )
    _TURNO_ICON = {"Día": "🌅", "Noche": "🌙"}

    for fecha_val, grupo in por_fecha:
        fecha_d = pd.to_datetime(fecha_val).date()
        dias_atraso = max((hoy - fecha_d).days, 0)
        atraso_color = "#E74C3C" if dias_atraso >= 3 else "#F39C12"

        filas_turno = ""
        for turno in TURNOS_REPORTES_REQUERIDOS:
            sub = grupo[grupo["Turno"] == turno]
            if sub.empty:
                continue
            equipos = sorted(sub["Equipo"].tolist())
            icon = _TURNO_ICON.get(turno, "")
            todos = len(equipos) == len(EQUIPOS_REPORTES_REQUERIDOS)
            chips = "".join(
                f'<span style="background:#1e1f22;border:1px solid #444;color:#d0d0d0;'
                f'font-size:0.72rem;border-radius:3px;padding:1px 6px;margin:2px;">{e}</span>'
                for e in equipos
            )
            filas_turno += (
                f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:2px;margin-top:4px;">'
                f'<span style="color:#E67E22;font-size:0.78rem;min-width:78px;">{icon} {turno}</span>'
                f'{"<span style=\"color:#E74C3C;font-size:0.72rem;\">(todos)</span>" if todos else ""}'
                f'{chips}</div>'
            )

        app.st.markdown(
            f'<div style="background:#0d0e10;border:1px solid #E67E22;border-radius:6px;'
            f'padding:8px 12px;margin-bottom:6px;">'
            f'<div style="display:flex;align-items:baseline;gap:8px;">'
            f'<span style="color:#F0F0F0;font-weight:600;font-size:0.88rem;">'
            f'⚠ {fecha_d.strftime("%d-%m-%Y")}</span>'
            f'<span style="color:#888;font-size:0.78rem;">{fecha_d.strftime("%A").capitalize()}</span>'
            f'<span style="color:{atraso_color};font-size:0.72rem;margin-left:auto;">{dias_atraso}d de atraso</span>'
            f'</div>'
            f'{filas_turno}'
            f'</div>',
            unsafe_allow_html=True,
        )


def main():
    if not app.requerir_acceso():
        return
    render_page_header(
        app.st,
        "Registro Operacional",
        "Ingreso manual de reportes diarios, validación de turno y respaldo operativo | Fuente: Registros manuales SQLite",
    )
    app.st.info(
        "Este formulario crea registros manuales. "
        "Los Ciclos de Perforación Excel se administran desde la fuente de datos de Ciclos y no se mezclan con este ingreso."
    )

    if app.st.session_state.pop("reporte_guardado", False):
        app.st.success("Reporte guardado correctamente en SQLite y exportado a Excel.")

    modo_wizard = app.st.toggle(
        "Modo tablet (formulario por pasos)",
        value=False,
        key="modo_wizard_toggle",
        help="Activa el modo wizard para ingresar el reporte paso a paso desde tablet o móvil.",
    )

    df_reportes = leer_reportes()
    if modo_wizard:
        _formulario_wizard(df_reportes)
    else:
        app.formulario_registro(df_reportes)

    _panel_reportes_pendientes()


main()
