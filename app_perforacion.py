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
    EXCEL_PATH,
    HORAS_TURNO,
    limpiar_entero,
    ruta_imagen_equipo,
)
from validation import report_validation

SISTEMA_TITULO = "Sistema de Gestión Operacional de Perforación"
REPORTES_PDF_DIR = REPORTS_PDF_DIR

DETENCION_HORAS_COLUMNAS = {
    "Falla Operacional": "Falla Operacional",
    "Avería mecánica": "Horas detención mecánica",
    "Cambio de aceros": "Cambio de aceros",
    "Geología": "Geología",
    "Seguridad": "Seguridad",
    "Colación": "Colación",
    "Relleno de agua": "Relleno de agua",
    "Combustible": "Combustible",
    "Traslado": "Traslado",
    "Cambio Turno": "Cambio turno",
    "Standby por falta de tajo/Patio": "Standby por falta de tajo/Patio",
    "Mantención Programada": "Mantención Programada",
    "Tronadura": "Tronadura",
    "Falta operador": "Falta operador",
    "Otros": "Otros",
}

COLUMNAS_HORAS_DETENCION = list(dict.fromkeys(DETENCION_HORAS_COLUMNAS.values()))


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
    from ui.auth import requerir_login

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


def color_estado_operacional(estado):
    return {
        "Operativo": "#DCFCE7",
        "Operativo parcial": "#FEF3C7",
        "Avería": "#FEE2E2",
        "Mantención Programada": "#DBEAFE",
        "Sin marcación": "#F3F4F6",
    }.get(estado, "#FFFFFF")


def color_texto_estado_operacional(estado):
    return {
        "Operativo": "#166534",
        "Operativo parcial": "#92400E",
        "Avería": "#991B1B",
        "Mantención Programada": "#1E40AF",
        "Sin marcación": "#4B5563",
    }.get(estado, "#0F172A")


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
    modelo_equipo = datos_identificacion["modelo_equipo"]
    numero_equipo = datos_identificacion["numero_equipo"]
    operador = datos_identificacion["operador"]
    codigo_operador = datos_identificacion["codigo_operador"]
    turno = datos_identificacion["turno"]
    fecha_turno = datos_identificacion["fecha_turno"]
    area_operacional = datos_identificacion["area_operacional"]

    section_header("Ubicacion y condiciones", "Contexto de banco, malla, fase, sector y condicion del terreno.", kicker="Paso 2")
    datos_ubicacion = render_ubicacion_condiciones(df_historial, k)
    banco = datos_ubicacion["banco"]
    malla = datos_ubicacion["malla"]
    fase = datos_ubicacion["fase"]
    tipo_perforacion = datos_ubicacion["tipo_perforacion"]
    numero_precorte = datos_ubicacion["numero_precorte"]
    condicion_terreno = datos_ubicacion["condicion_terreno"]
    numero_bit = datos_ubicacion["numero_bit"]
    section_header("Produccion y observaciones", "Metros, pozos, horometro, consumos, detenciones y estado del equipo.", kicker="Paso 3")
    datos_produccion = render_produccion_consumos(k)
    metros = datos_produccion["metros"]
    pozos = datos_produccion["pozos"]
    petroleo = datos_produccion["petroleo"]
    horometro_inicial = datos_produccion["horometro_inicial"]
    horometro_final = datos_produccion["horometro_final"]
    diferencia_horometro = datos_produccion["diferencia_horometro"]
    tipo_detencion = datos_produccion["tipo_detencion"]
    estatus_equipo = datos_produccion.get("estatus_equipo", "")
    observaciones = datos_produccion["observaciones"]

    section_header("Horas del turno", "Distribucion operacional de horas efectivas, averias y tiempos no efectivos.", kicker="Paso 4")
    datos_horas = render_horas_turno(tipo_detencion, k)
    horas_efectivas = datos_horas["horas_efectivas"]
    horas_averia = datos_horas["horas_averia"]
    horas_combustible = datos_horas["horas_combustible"]
    horas_agua = datos_horas["horas_agua"]
    horas_colacion = datos_horas["horas_colacion"]
    horas_traslado = datos_horas["horas_traslado"]
    horas_standby = datos_horas["horas_standby"]
    horas_tronadura = datos_horas["horas_tronadura"]
    horas_mantencion = datos_horas["horas_mantencion"]
    horas_cambio_turno = datos_horas["horas_cambio_turno"]
    horas_falta_operador = datos_horas["horas_falta_operador"]
    horas_otros = datos_horas.get("horas_otros", 0.0)
    horas_no_efectivas = datos_horas["horas_no_efectivas"]
    total_horas = datos_horas["total_horas"]

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
    rendimiento_turno = kpi_turno["rendimiento"]
    utilizacion = kpi_turno["utilizacion_productiva"]
    disponibilidad = kpi_turno["disponibilidad"]

    section_header("KPI del turno", "Indicadores calculados antes de guardar el reporte.", kicker="Control")
    render_kpi_turno(rendimiento_turno, utilizacion, disponibilidad)
    for alerta in kpi_turno["alertas_coherencia"]:
        st.warning(texto_visible(alerta))

    duplicado_preview, registro_existente_preview = validar_duplicado_sqlite(
        fecha_turno,
        turno,
        numero_equipo,
        operador,
    )
    if duplicado_preview:
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
            tipo_sector=datos_ubicacion.get("tipo_sector"),
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
        if not resultado_validacion["ok"]:
            st.error(texto_visible(resultado_validacion["mensaje"]))
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
            ],
            "📊 Análisis": [
                st.Page("pages/08_Panel_Ejecutivo.py", title="Panel Ejecutivo"),
                st.Page("pages/09_Analisis_Mensual.py", title="Análisis Mensual"),
                st.Page("pages/10_Dashboard_Excel_Operacional.py", title="Dashboard Excel"),
                st.Page("pages/15_Machine_Learning.py", title="Machine Learning"),
            ],
            "📄 Documentos": [
                st.Page("pages/07_Reportes_PDF.py", title="Reportes PDF"),
                st.Page("pages/14_Biblioteca_Tecnica.py", title="Biblioteca Técnica"),
                st.Page("pages/04_Gestion_Planos.py", title="Gestión Planos"),
                st.Page("pages/05_Ortomosaico_Vista_Mina.py", title="Ortomosaico Vista Mina"),
            ],
            "⚙️ Administración": [
                st.Page("pages/11_Alertas_Inteligentes.py", title="Alertas Inteligentes"),
                st.Page("pages/12_Calidad_Datos.py", title="Calidad Datos"),
                st.Page("pages/13_Acciones_Correctivas.py", title="Acciones Correctivas"),
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
        st.caption("Datos oficiales: reportes_perforacion.db")
        st.caption(f"Excel de respaldo/exportación: {EXCEL_PATH}")
        if st.button("Recargar datos"):
            limpiar_cache_reportes()
            st.rerun()

    pg.run()


if __name__ == "__main__":
    main()
