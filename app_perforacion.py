import sqlite3
from datetime import date, timedelta

import pandas as pd
import streamlit as st
import html

from config import REPORTS_PDF_DIR, VERSION_PATH
from audit import audit_log
from data import leer_reportes_sqlite as leer_reportes, limpiar_cache_reportes, preparar_dataframe, reparar_texto
from services import catalog_service, kpi_service
from schema import columnas_equivalentes
from ui.formatting import dataframe_visible, texto_visible
from utils import (
    COLUMNAS_HORAS_DETENCION,
    EXCEL_PATH,
    HORAS_TURNO,
    color_estado_operacional,
    color_texto_estado_operacional,
    limpiar_entero,
    ruta_imagen_equipo,
)
from validation import report_validation

SISTEMA_TITULO = "Sistema de Gestión Operacional de Perforación"
REPORTES_PDF_DIR = REPORTS_PDF_DIR

def version_sistema():
    if VERSION_PATH.exists():
        return VERSION_PATH.read_text(encoding="utf-8").splitlines()[0].strip()
    return "v1.0.5 - Dashboard KPI Profesional"


def configurar_pagina_principal():
    st.set_page_config(
        page_title=SISTEMA_TITULO,
        page_icon="⛏️",
        layout="wide",
    )


def requerir_acceso(admin=False):
    import os
    from ui.auth import requerir_login  # carga .env en os.environ como efecto secundario

    if os.environ.get("REPORT_PERFORACION_AUTH_ENABLED", "true").strip().lower() == "false":
        return True
    return requerir_login(st, admin=admin)


def render_usuario_sidebar():
    from ui.auth import render_usuario_sidebar as _render_usuario_sidebar

    _render_usuario_sidebar(st)


def render_command_header():
    from ui.auth import usuario_actual

    usuario = usuario_actual() or {}
    nombre = html.escape(texto_visible(usuario.get("nombre", "Usuario")))
    rol = html.escape(texto_visible(str(usuario.get("rol", "usuario")).upper()))
    version = html.escape(texto_visible(version_sistema()))
    st.markdown(
        f"""
        <div class="rp-command-header">
            <div class="rp-command-inner">
                <div class="rp-brand">
                    <div class="rp-brand-mark">RP</div>
                    <div>
                        <div class="rp-brand-title">Perforación</div>
                        <div class="rp-brand-subtitle">Operational Intelligence Hub</div>
                    </div>
                </div>
                <div class="rp-header-meta">
                    <span class="rp-chip">{nombre}</span>
                    <span class="rp-chip">{rol}</span>
                    <span class="rp-chip">Versión {version}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(titulo, subtitulo=""):
    from ui.page_header import render_page_header as _render_page_header

    _render_page_header(st, titulo, subtitulo)


def limpiar_formulario():
    st.session_state["form_version"] = st.session_state.get("form_version", 0) + 1


def equipos_esperados():
    return catalog_service.equipos_esperados_activos()


def existe_reporte_duplicado(df, fecha_turno, turno, modelo_equipo, numero_equipo, operador):
    return report_validation.existe_reporte_duplicado(
        df,
        fecha_turno,
        turno,
        modelo_equipo,
        numero_equipo,
        operador,
    )


def validar_duplicado_sqlite(fecha_turno, turno, numero_equipo, operador):
    try:
        import db

        return db.existe_registro_duplicado(fecha_turno, turno, numero_equipo, operador)
    except Exception as exc:
        audit_log.registrar_evento(
            "validacion_duplicado_sqlite",
            resultado="error",
            detalle=str(exc),
        )
        return False, pd.DataFrame()


def validar_equipo_unico_turno(fecha_turno, turno, numero_equipo):
    """Devuelve (ocupado: bool, operador: str|None) si el equipo ya tiene registro en ese turno/fecha."""
    try:
        import db

        return db.equipo_ocupado_en_turno(fecha_turno, turno, numero_equipo)
    except Exception:
        return False, None


def buscar_reporte_por_llave(fecha_turno, turno, numero_equipo):
    try:
        import db

        return db.buscar_reporte_por_llave(fecha_turno, turno, numero_equipo)
    except Exception as exc:
        audit_log.registrar_evento(
            "validacion_llave_reporte",
            numero_equipo=numero_equipo,
            turno=turno,
            resultado="error",
            detalle=str(exc),
        )
        return pd.DataFrame()


def render_alerta_reporte_existente(fecha_turno, turno, numero_equipo, modelo_equipo="", contenedor=st):
    existente = buscar_reporte_por_llave(fecha_turno, turno, numero_equipo)
    if existente.empty:
        return False, existente

    fila = existente.iloc[0].to_dict()
    fecha_texto = (
        fecha_turno.strftime("%Y-%m-%d")
        if hasattr(fecha_turno, "strftime")
        else str(fecha_turno or "")
    )
    contenedor.warning("⚠️ Este reporte ya fue ingresado para esta fecha, turno y equipo.")
    contenedor.caption(
        "Registro existente: "
        f"ID {fila.get('id', '')} · "
        f"Operador: {texto_visible(fila.get('Operador', ''))} · "
        f"Modelo: {texto_visible(fila.get('Modelo equipo', modelo_equipo))} · "
        f"Creado: {texto_visible(fila.get('created_at', ''))} · "
        f"Llave: {fecha_texto} / {texto_visible(turno)} / {numero_equipo}"
    )
    columnas = [
        columna
        for columna in ["id", "created_at", "Fecha turno", "Turno", "Número equipo", "Modelo equipo", "Operador"]
        if columna in existente.columns
    ]
    if columnas:
        contenedor.dataframe(dataframe_visible(existente[columnas]), width="stretch", hide_index=True)
    return True, existente


def mostrar_alerta_reportes_faltantes(df):
    columnas = {"Fecha turno", "Turno", "Modelo equipo", "Número equipo"}
    if df.empty or not columnas.issubset(df.columns):
        return

    fechas = pd.to_datetime(df["Fecha turno"], errors="coerce").dt.date.dropna().unique()
    turnos = df["Turno"].dropna().astype(str).str.strip()
    turnos = sorted(turno for turno in turnos.unique() if turno)

    if len(fechas) != 1 or len(turnos) != 1:
        st.info("Selecciona una sola fecha y un solo turno para validar reportes faltantes por equipo.")
        return

    fecha = fechas[0]
    turno = turnos[0]
    registrados = set(
        zip(
            df["Modelo equipo"].astype(str).str.strip(),
            df["Número equipo"].astype(str).apply(limpiar_entero),
        )
    )
    faltantes = [
        f"{modelo} {numero}"
        for modelo, numero in equipos_esperados()
        if (modelo, limpiar_entero(numero)) not in registrados
    ]
    fecha_texto = pd.to_datetime(fecha).strftime("%d-%m-%Y")

    if faltantes:
        st.warning(
            f"Faltan reportes por registrar para la fecha {fecha_texto} turno {turno}: "
            + ", ".join(faltantes)
        )
    else:
        st.success(f"Reportes completos: los {len(equipos_esperados())} equipos activos están registrados para esta fecha y turno.")


_EQUIPOS_FLOTA_ALERTA = catalog_service.FLOTA_EQUIPOS
_TURNOS_ESPERADOS_ALERTA = ["Día", "Noche"]


def _calcular_turnos_faltantes():
    from services.alert_service import get_reportes_faltantes
    import db

    faltantes_df = get_reportes_faltantes(equipos=_EQUIPOS_FLOTA_ALERTA, turnos=_TURNOS_ESPERADOS_ALERTA)
    with db.get_connection() as connection:
        total_registros = connection.execute(
            f"SELECT COUNT(*) FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
        ).fetchone()[0]
        ultima_fecha = connection.execute(
            f"SELECT MAX({db.quote_identifier('Fecha turno')}) FROM {db.quote_identifier(db.TABLA_REGISTROS)}"
        ).fetchone()[0]

    metadata = {
        "db_path": str(db.DB_PATH),
        "total_registros": int(total_registros or 0),
        "ultima_fecha": ultima_fecha or "Sin fecha",
    }
    if faltantes_df.empty:
        return {}, metadata

    faltantes: dict[str, dict[str, list[str]]] = {}
    for _, fila in faltantes_df.iterrows():
        fecha = pd.to_datetime(fila["Fecha"], errors="coerce")
        if pd.isna(fecha):
            continue
        fecha_str = fecha.date().isoformat()
        turno = str(fila["Turno"]).strip()
        equipo = str(fila["Equipo"]).strip()
        faltantes.setdefault(fecha_str, {}).setdefault(turno, []).append(equipo)

    return faltantes, metadata


def _render_actualizar_alertas():
    if st.button("Actualizar alertas", key="actualizar_alertas_turnos_faltantes"):
        limpiar_cache_alertas()
        st.rerun()


def limpiar_cache_alertas():
    st.cache_data.clear()
    limpiar_cache_reportes()


def _render_metadata_alertas(metadata, contenedor=st):
    contenedor.caption(
        "BD activa: "
        f"{metadata.get('db_path', 'Sin ruta')} · "
        f"Última fecha leída: {metadata.get('ultima_fecha', 'Sin fecha')} · "
        f"Registros leídos: {metadata.get('total_registros', 0)}"
    )


def _render_sidebar_turnos_faltantes():
    faltantes, _ = _calcular_turnos_faltantes()
    if not faltantes:
        st.sidebar.markdown(
            '<div style="border-left:3px solid #2ECC71;padding:4px 8px;font-size:0.78rem;color:#2ECC71;">'
            '✓ Turnos al día</div>',
            unsafe_allow_html=True,
        )
        return

    total_combos = sum(
        len(eqs) for td in faltantes.values() for eqs in td.values()
    )
    fechas_recientes = sorted(faltantes.keys(), reverse=True)[:3]
    items_html = "".join(
        f'<div style="font-size:0.72rem;color:#BDC3C7;">'
        f'{date.fromisoformat(f).strftime("%d-%m")} — '
        + ", ".join(faltantes[f].keys())
        + "</div>"
        for f in fechas_recientes
    )
    st.sidebar.markdown(
        f'<div style="border-left:3px solid #E67E22;padding:4px 8px;margin-bottom:4px;">'
        f'<div style="font-size:0.78rem;font-weight:600;color:#E67E22;">⚠ {total_combos} registro(s) faltante(s)</div>'
        f'{items_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_panel_turnos_faltantes():
    _render_actualizar_alertas()
    faltantes, metadata = _calcular_turnos_faltantes()
    _render_metadata_alertas(metadata)

    if not faltantes:
        st.markdown(
            '<div style="background:#0d0e10;border:1px solid #2ECC71;border-radius:8px;padding:12px 16px;margin-bottom:16px;">'
            '<span style="color:#2ECC71;font-size:0.88rem;">✓ Todos los turnos Día y Noche están registrados para todos los equipos desde el inicio del proyecto hasta hoy.</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    total_combos = sum(len(eqs) for td in faltantes.values() for eqs in td.values())
    total_fechas = len(faltantes)
    total_turnos_inc = sum(len(td) for td in faltantes.values())

    st.markdown(
        f'<div style="background:#0d0e10;border:1px solid #E67E22;border-radius:8px;padding:16px;margin-bottom:16px;">'
        f'<h4 style="color:#E67E22;margin:0 0 12px 0;">⚠ Registros faltantes desde inicio del proyecto</h4>'
        f'<div style="display:flex;gap:28px;margin-bottom:10px;">'
        f'<div><div style="font-size:1.6rem;font-weight:700;color:#E67E22;">{total_combos}</div>'
        f'<div style="font-size:0.7rem;color:#BDC3C7;">registros faltantes</div></div>'
        f'<div><div style="font-size:1.6rem;font-weight:700;color:#E67E22;">{total_fechas}</div>'
        f'<div style="font-size:0.7rem;color:#BDC3C7;">fechas afectadas</div></div>'
        f'<div><div style="font-size:1.6rem;font-weight:700;color:#E67E22;">{total_turnos_inc}</div>'
        f'<div style="font-size:0.7rem;color:#BDC3C7;">turnos incompletos</div></div>'
        f'</div>'
        f'<p style="color:#BDC3C7;margin:0 0 12px 0;font-size:0.78rem;">Flota: {", ".join(_EQUIPOS_FLOTA_ALERTA)}</p>',
        unsafe_allow_html=True,
    )

    fechas_ordenadas = sorted(faltantes.keys(), reverse=True)
    mes_actual = None
    filas_html = ""
    for fecha_str in fechas_ordenadas:
        fecha_d = date.fromisoformat(fecha_str)
        mes = fecha_d.strftime("%B %Y").capitalize()
        if mes != mes_actual:
            if mes_actual is not None:
                filas_html += "</div>"
            filas_html += (
                f'<div style="color:#E67E22;font-size:0.78rem;font-weight:600;'
                f'margin:10px 0 4px 0;border-bottom:1px solid #333;padding-bottom:2px;">{mes}</div>'
                f'<div>'
            )
            mes_actual = mes

        turno_rows = ""
        for turno, equipos in faltantes[fecha_str].items():
            icon = "🌅" if turno == "Día" else "🌙"
            chips = "".join(
                f'<span style="background:#1e1f22;border:1px solid #444;color:#d0d0d0;'
                f'font-size:0.68rem;border-radius:3px;padding:1px 5px;margin:1px 2px;">{e}</span>'
                for e in equipos
            )
            turno_rows += (
                f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:2px;margin-top:3px;">'
                f'<span style="color:#E67E22;font-size:0.75rem;min-width:72px;">{icon} {turno}</span>'
                f'{chips}</div>'
            )

        filas_html += (
            f'<div style="padding:6px 0;border-bottom:1px solid #1e1f22;">'
            f'<span style="color:#F0F0F0;font-size:0.82rem;font-weight:500;">⚠ {fecha_d.strftime("%d-%m-%Y")}</span>'
            f'{turno_rows}'
            f'</div>'
        )

    if mes_actual is not None:
        filas_html += "</div>"

    st.markdown(filas_html + "</div>", unsafe_allow_html=True)


def normalizar_nombre_columna(nombre):
    return kpi_service.normalizar_nombre_columna(nombre)


def buscar_columna(df, *candidatos):
    return kpi_service.buscar_columna(df, *candidatos)


def serie_numerica(df, *columnas):
    return kpi_service.serie_numerica(df, *columnas)


def totales_productivos(df):
    return kpi_service.totales_productivos(df)


def columnas_horas_turno():
    return ["Horas efectivas perforando", *COLUMNAS_HORAS_DETENCION]


def etiqueta_hora(columna):
    etiquetas = {
        "Horas detención mecánica": "Avería mecánica",
        "Relleno de agua": "Relleno de agua",
        "Cambio turno": "Cambio Turno",
    }
    return texto_visible(etiquetas.get(columna, columna))


def estado_operacional_equipo(metros, pozos, horas_efectivas, horas_no_efectivas, horas_averia, horas_mantencion):
    return kpi_service.estado_operacional_equipo(
        metros,
        pozos,
        horas_efectivas,
        horas_no_efectivas,
        horas_averia,
        horas_mantencion,
    )


def resumen_operacional_equipos(df):
    return kpi_service.resumen_operacional_equipos(df)


def formulario_registro(df_historial):
    from services.report_service import ejecutar_guardado_reporte, validar_datos_para_guardado
    from ui.components import section_header
    from ui.forms_sections import (
        render_equipo_operador_fecha,
        render_horas_turno,
        render_kpi_turno,
        render_preview_duplicado,
        render_produccion_consumos,
        render_ubicacion_condiciones,
    )

    section_header(
        "Registro operacional",
        "Ingreso estructurado para terreno: turno, equipo, operador, produccion, horas y observaciones.",
        kicker="Formulario",
    )
    form_version = st.session_state.get("form_version", 0)

    def k(nombre):
        return f"{nombre}_{form_version}"

    section_header("Datos del turno, equipo y operador", "Identificacion base del reporte operacional.", kicker="Paso 1")
    datos_identificacion = render_equipo_operador_fecha(k)
    modelo_equipo       = datos_identificacion.get("modelo_equipo", "")
    numero_equipo       = datos_identificacion.get("numero_equipo", "")
    operador            = datos_identificacion.get("operador") or ""
    codigo_operador     = datos_identificacion.get("codigo_operador", "")
    turno               = datos_identificacion.get("turno", "")
    fecha_turno         = datos_identificacion.get("fecha_turno")
    area_operacional    = datos_identificacion.get("area_operacional", "")
    reporte_existente_llave, registro_existente_llave = render_alerta_reporte_existente(
        fecha_turno,
        turno,
        numero_equipo,
        modelo_equipo,
    )

    section_header("Ubicacion y condiciones", "Contexto de banco, malla, fase, sector y condicion del terreno.", kicker="Paso 2")
    datos_ubicacion = render_ubicacion_condiciones(df_historial, k)
    banco               = datos_ubicacion.get("banco", [])
    malla               = datos_ubicacion.get("malla", [])
    fase                = datos_ubicacion.get("fase", [])
    tipo_perforacion    = datos_ubicacion.get("tipo_perforacion", [])
    condicion_terreno   = datos_ubicacion.get("condicion_terreno", [])
    numero_bit          = datos_ubicacion.get("numero_bit", "")
    _sectores           = datos_ubicacion.get("sectores", [])
    tipo_sector_reg     = _sectores[0].get("tipo", "Producción") if _sectores else "Producción"
    numero_precorte     = (
        _sectores[0].get("numero", "")
        if _sectores and _sectores[0].get("tipo") == "Precorte" else ""
    )

    section_header("Produccion y observaciones", "Metros, pozos, horometro, consumos, detenciones y estado del equipo.", kicker="Paso 3")
    datos_produccion = render_produccion_consumos(k)
    metros               = datos_produccion.get("metros", 0.0)
    pozos                = datos_produccion.get("pozos", 0)
    petroleo             = datos_produccion.get("petroleo", 0.0)
    horometro_inicial    = datos_produccion.get("horometro_inicial", 0.0)
    horometro_final      = datos_produccion.get("horometro_final", 0.0)
    diferencia_horometro = datos_produccion.get("diferencia_horometro", 0.0)
    tipo_detencion       = datos_produccion.get("tipo_detencion", [])
    estatus_equipo       = datos_produccion.get("estatus_equipo", "")
    observaciones        = datos_produccion.get("observaciones", "")

    section_header("Horas del turno", "Distribucion operacional de horas efectivas, averias y tiempos no efectivos.", kicker="Paso 4")
    datos_horas = render_horas_turno(tipo_detencion, k)
    horas_efectivas      = datos_horas.get("horas_efectivas", 0.0)
    horas_averia         = datos_horas.get("horas_averia", 0.0)
    horas_combustible    = datos_horas.get("horas_combustible", 0.0)
    horas_agua           = datos_horas.get("horas_agua", 0.0)
    horas_colacion       = datos_horas.get("horas_colacion", 0.0)
    horas_traslado       = datos_horas.get("horas_traslado", 0.0)
    horas_standby        = datos_horas.get("horas_standby", 0.0)
    horas_tronadura      = datos_horas.get("horas_tronadura", 0.0)
    horas_mantencion     = datos_horas.get("horas_mantencion", 0.0)
    horas_cambio_turno   = datos_horas.get("horas_cambio_turno", 0.0)
    horas_falta_operador = datos_horas.get("horas_falta_operador", 0.0)
    horas_otros          = datos_horas.get("horas_otros", 0.0)
    horas_no_efectivas   = datos_horas.get("horas_no_efectivas", 0.0)
    total_horas          = datos_horas.get("total_horas", 0.0)

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
    rendimiento_turno = kpi_turno.get("rendimiento", 0.0)
    utilizacion       = kpi_turno.get("utilizacion_productiva", 0.0)
    disponibilidad    = kpi_turno.get("disponibilidad", 0.0)

    section_header("KPI del turno", "Indicadores calculados antes de guardar el reporte.", kicker="Control")
    render_kpi_turno(rendimiento_turno, utilizacion, disponibilidad)
    for alerta in kpi_turno.get("alertas_coherencia", []):
        st.warning(texto_visible(alerta))

    duplicado_preview, registro_existente_preview = validar_duplicado_sqlite(
        fecha_turno,
        turno,
        numero_equipo,
        operador,
    )
    if duplicado_preview and not reporte_existente_llave:
        render_preview_duplicado(registro_existente_preview)

    if st.button("Guardar reporte", type="primary", key=k("guardar_reporte")):
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
            tipo_sector=tipo_sector_reg,
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
            st.warning(texto_visible(adv))
        if not resultado_validacion.get("ok"):
            st.error(texto_visible(resultado_validacion.get("mensaje", "")))
            return

        reporte_existente_llave, registro_existente_llave = render_alerta_reporte_existente(
            fecha_turno,
            turno,
            numero_equipo,
            modelo_equipo,
        )
        if reporte_existente_llave:
            mensaje = "Este reporte ya fue ingresado para esta fecha, turno y equipo."
            audit_log.registrar_guardado_rechazado(
                usuario=operador,
                equipo=modelo_equipo,
                numero_equipo=numero_equipo,
                turno=turno,
                detalle=mensaje,
            )
            st.error("No se permite guardar un duplicado. Para modificarlo use Edición Controlada o Reconciliación Reportes.")
            return

        duplicado_sqlite, registro_existente = validar_duplicado_sqlite(
            fecha_turno,
            turno,
            numero_equipo,
            operador,
        )
        if duplicado_sqlite:
            mensaje = "Registro duplicado detectado: ya existe un reporte para este equipo, fecha, turno y operador."
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
            st.error(texto_visible(mensaje))
            columnas_existente = [
                columna
                for columna in ["Fecha turno", "Modelo equipo", "Número equipo", "Operador", "Turno", "Metros perforados", "Hora registro"]
                if columna in registro_existente.columns
            ]
            if columnas_existente:
                st.dataframe(dataframe_visible(registro_existente[columnas_existente]), width="stretch", hide_index=True)
            st.info("Si necesita corregir información, use edición de registro en vez de crear uno nuevo.")
            return

        datos_formulario = {
            "identificacion": datos_identificacion,
            "ubicacion": datos_ubicacion,
            "produccion": datos_produccion,
            "horas": datos_horas,
            "kpi": {
                "rendimiento_turno": rendimiento_turno,
                "disponibilidad": disponibilidad,
                "utilizacion": utilizacion,
            },
        }
        resultado_guardado = ejecutar_guardado_reporte(datos_formulario)
        if not resultado_guardado["ok"]:
            st.error(resultado_guardado["mensaje"])
            return

        registro = resultado_guardado["registro"]
        ruta_guardado = resultado_guardado["ruta_guardado"]
        ruta_respaldo = resultado_guardado["ruta_respaldo"]
        st.session_state["reporte_guardado"] = True
        st.session_state["ultimo_guardado"] = {
            "ruta": str(ruta_guardado),
            "respaldo": str(ruta_respaldo) if ruta_respaldo else "",
            "equipo": f"{modelo_equipo} {limpiar_entero(numero_equipo)}",
            "fecha_turno": fecha_turno.strftime("%d-%m-%Y") if hasattr(fecha_turno, "strftime") else str(fecha_turno),
            "turno": turno,
            "hora_registro": registro.get("Hora registro", pd.Series([""])).iloc[0] if "Hora registro" in registro.columns else "",
        }
        limpiar_cache_alertas()
        limpiar_formulario()
        st.rerun()


def _render_inicio():
    from dashboard import dashboard as dashboard_view
    from ui.alerts_view import mostrar_alertas_operacionales
    from ui.data_status import mostrar_estado_datos
    from ui.data_source import FUENTE_CICLOS, cargar_dataframe_fuente, seleccionar_fuente_datos
    from ui.filters import aplicar_filtros
    from ui.home import render_inicio
    from ui.pdf_section import seccion_reporte_pdf

    df_reportes = leer_reportes()
    fuente_dashboard = seleccionar_fuente_datos(st, key="app_principal_fuente_dashboard")
    df_dashboard = cargar_dataframe_fuente(fuente_dashboard)
    render_inicio(df_dashboard)

    if st.session_state.pop("reporte_guardado", False):
        ultimo = st.session_state.get("ultimo_guardado", {})
        detalle = (
            f"Reporte guardado correctamente en SQLite y exportado a Excel: {ultimo.get('ruta', EXCEL_PATH)}"
            f" | Equipo: {ultimo.get('equipo', '')}"
            f" | Fecha turno: {ultimo.get('fecha_turno', '')}"
            f" | Turno: {texto_visible(ultimo.get('turno', ''))}"
            f" | Hora registro: {ultimo.get('hora_registro', '')}"
        )
        st.success(detalle)
        if ultimo.get("respaldo"):
            st.caption(f"Respaldo previo creado: {ultimo['respaldo']}")

    mostrar_estado_datos(df_reportes)
    render_panel_turnos_faltantes()

    with st.expander("Nuevo reporte operacional", expanded=fuente_dashboard != FUENTE_CICLOS):
        if fuente_dashboard == FUENTE_CICLOS:
            st.info(
                "Esta fuente corresponde a ciclos importados desde Excel. "
                "Para ingresar reportes manuales cambie a fuente Registros manuales."
            )
        else:
            formulario_registro(df_reportes)

    st.caption(f"Fuente de datos activa para dashboard/reportes: {fuente_dashboard}")
    dashboard_view(
        df_dashboard,
        aplicar_filtros_fn=aplicar_filtros,
        mostrar_alerta_reportes_faltantes_fn=mostrar_alerta_reportes_faltantes,
        mostrar_alertas_operacionales_fn=mostrar_alertas_operacionales,
        seccion_reporte_pdf_fn=seccion_reporte_pdf,
        resumen_operacional_equipos_fn=resumen_operacional_equipos,
        equipos_esperados_fn=equipos_esperados,
        ruta_imagen_equipo_fn=ruta_imagen_equipo,
        limpiar_entero_fn=limpiar_entero,
        color_estado_operacional_fn=color_estado_operacional,
        color_texto_estado_operacional_fn=color_texto_estado_operacional,
        columnas_horas_turno_fn=columnas_horas_turno,
        etiqueta_hora_fn=etiqueta_hora,
    )


def main():
    from ui.theme import aplicar_tema_profesional

    configurar_pagina_principal()
    aplicar_tema_profesional()

    pg = st.navigation(
        {
            "⛏ Operacional": [
                st.Page(_render_inicio, title="Inicio", default=True, icon="🏠"),
                st.Page("pages/01_Registro_Operacional.py", title="Registro Operacional"),
                st.Page("pages/02_Dashboard_Operacional.py", title="Dashboard Operacional"),
                st.Page("pages/03_Avance_Operacional.py", title="Avance Operacional"),
                st.Page("pages/06_Alertas_Operacionales.py", title="Alertas Operacionales"),
                st.Page("pages/24_Alertas_Registros.py", title="Alertas de Registros"),
            ],
            "📊 Análisis": [
                st.Page("pages/08_Panel_Ejecutivo.py", title="Panel Ejecutivo"),
                st.Page("pages/09_Analisis_Mensual.py", title="Análisis Mensual"),
                st.Page("pages/10_Dashboard_Excel_Operacional.py", title="Dashboard Excel"),
            ],
            "📄 Documentos": [
                st.Page("pages/07_Reportes_PDF.py", title="Reportes PDF"),
                st.Page("pages/04_Gestion_Planos.py", title="Gestión Planos"),
            ],
            "⚙️ Administración": [
                st.Page("pages/11_Alertas_Inteligentes.py", title="Alertas Inteligentes"),
                st.Page("pages/12_Calidad_Datos.py", title="Calidad Datos"),
                st.Page("pages/25_Editar_Registro.py", title="Editar Registro", icon="✏️"),
                st.Page("pages/17_Edicion_Controlada_Auditoria.py", title="Edición Controlada"),
                st.Page("pages/16_Auditoria_Historial.py", title="Auditoría Historial"),
                st.Page("pages/18_Respaldos_Exportacion.py", title="Respaldos Exportación"),
                st.Page("pages/19_Administracion_Operadores.py", title="Administración Operadores"),
                st.Page("pages/20_Administrar_Fuentes_Excel.py", title="Administrar Fuentes"),
                st.Page("pages/21_Fuentes_Datos.py", title="Fuentes Datos"),
                st.Page("pages/22_Importar_Excel.py", title="Importar Excel"),
                st.Page("pages/23_Administracion_Catalogos.py", title="Administración Catálogos"),
            ],
        }
    )

    if not requerir_acceso():
        return

    render_command_header()

    with st.sidebar:
        render_usuario_sidebar()
        st.divider()
        _render_sidebar_turnos_faltantes()
        st.divider()
        st.caption("Datos oficiales: reportes_perforacion.db")
        st.caption(f"Excel de respaldo/exportación: {EXCEL_PATH}")
        if st.button("Recargar datos"):
            limpiar_cache_reportes()
            st.rerun()

    pg.run()


if __name__ == "__main__":
    main()
