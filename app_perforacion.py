from pathlib import Path

import pandas as pd
import streamlit as st

from audit import audit_log
from alerts import evaluar_alertas_operacionales
from data import leer_reportes_sqlite as leer_reportes, limpiar_cache_reportes, preparar_dataframe, reparar_texto
from dashboard import dashboard as dashboard_view
from services import kpi_service
from services.report_service import ejecutar_guardado_reporte, validar_datos_para_guardado
from schema import columnas_equivalentes
from ui.alerts_view import mostrar_alertas_operacionales
from ui.data_status import mostrar_estado_datos, mostrar_estado_respaldo_sqlite
from ui.filters import aplicar_filtros
from ui.forms_sections import render_equipo_operador_fecha, render_horas_turno, render_kpi_turno, render_preview_duplicado, render_produccion_consumos, render_ubicacion_condiciones
from ui.formatting import dataframe_visible, texto_visible
from ui.home import render_inicio
from ui.pdf_section import seccion_reporte_pdf
from ui.theme import aplicar_tema_profesional
from utils import (
    EQUIPOS,
    EXCEL_PATH,
    HORAS_TURNO,
    limpiar_entero,
    ruta_imagen_equipo,
)
from validation import report_validation

REPORTES_PDF_DIR = Path(EXCEL_PATH).parent / "reportes_pdf"
VERSION_PATH = Path(EXCEL_PATH).parent / "VERSION.txt"

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


st.set_page_config(
    page_title="Reporte de Perforación",
    page_icon="⛏️",
    layout="wide",
)

aplicar_tema_profesional()


def limpiar_formulario():
    st.session_state["form_version"] = st.session_state.get("form_version", 0) + 1


def equipos_esperados():
    return [(modelo, numero) for modelo, numeros in EQUIPOS.items() for numero in numeros]


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
        st.success("Reportes completos: los 6 equipos están registrados para esta fecha y turno.")


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
    st.header("Registro operacional")
    form_version = st.session_state.get("form_version", 0)

    def k(nombre):
        return f"{nombre}_{form_version}"

    datos_identificacion = render_equipo_operador_fecha(k)
    modelo_equipo = datos_identificacion["modelo_equipo"]
    numero_equipo = datos_identificacion["numero_equipo"]
    operador = datos_identificacion["operador"]
    codigo_operador = datos_identificacion["codigo_operador"]
    turno = datos_identificacion["turno"]
    fecha_turno = datos_identificacion["fecha_turno"]
    area_operacional = datos_identificacion["area_operacional"]

    datos_ubicacion = render_ubicacion_condiciones(df_historial, k)
    banco = datos_ubicacion["banco"]
    malla = datos_ubicacion["malla"]
    fase = datos_ubicacion["fase"]
    tipo_perforacion = datos_ubicacion["tipo_perforacion"]
    numero_precorte = datos_ubicacion["numero_precorte"]
    condicion_terreno = datos_ubicacion["condicion_terreno"]
    numero_bit = datos_ubicacion["numero_bit"]
    datos_produccion = render_produccion_consumos(k)
    metros = datos_produccion["metros"]
    pozos = datos_produccion["pozos"]
    petroleo = datos_produccion["petroleo"]
    horometro_inicial = datos_produccion["horometro_inicial"]
    horometro_final = datos_produccion["horometro_final"]
    diferencia_horometro = datos_produccion["diferencia_horometro"]
    tipo_detencion = datos_produccion["tipo_detencion"]
    causa_detencion = datos_produccion["causa_detencion"]
    observaciones = datos_produccion["observaciones"]

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

    rendimiento_turno = kpi_service.calcular_rendimiento_consolidado(pd.DataFrame([{
        "Metros perforados": metros,
        "Horas efectivas perforando": horas_efectivas,
    }]))
    utilizacion = kpi_service.calcular_utilizacion(horas_efectivas)
    disponibilidad = kpi_service.calcular_disponibilidad(
        horas_averia,
        horas_mantencion=horas_mantencion,
    )

    render_kpi_turno(rendimiento_turno, utilizacion, disponibilidad)

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
        )
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


def main():
    st.title("Sistema de Reporte de Perforación")
    st.caption(f"Aplicación oficial: {EXCEL_PATH.parent} | Versión actual: {version_sistema()}")

    with st.sidebar:
        st.caption("Datos oficiales: reportes_perforacion.db")
        st.caption(f"Excel de respaldo/exportación: {EXCEL_PATH}")
        if st.button("Recargar datos"):
            limpiar_cache_reportes()
            st.rerun()

    df_reportes = leer_reportes()
    render_inicio(df_reportes)

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

    with st.expander("Nuevo reporte operacional", expanded=True):
        formulario_registro(df_reportes)

    dashboard_view(
        df_reportes,
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


if __name__ == "__main__":
    main()
