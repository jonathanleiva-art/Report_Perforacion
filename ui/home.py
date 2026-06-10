from pathlib import Path

import pandas as pd
import streamlit as st

from alerts import evaluar_alertas_operacionales
from config import REPORTS_PDF_DIR
import db
from schema import columnas_equivalentes
from utils import EXCEL_PATH


REPORTES_PDF_DIR = REPORTS_PDF_DIR


def contar_pdfs_generados():
    if not REPORTES_PDF_DIR.exists():
        return 0
    return sum(1 for _ in REPORTES_PDF_DIR.glob("*.pdf"))


def ultima_fecha_registrada(df):
    columna_fecha = next((col for col in columnas_equivalentes("fecha_turno") if col in df.columns), None)
    if not columna_fecha:
        return None

    fechas = pd.to_datetime(df[columna_fecha], errors="coerce")
    fechas_validas = fechas.dropna()
    if fechas_validas.empty:
        return None
    return fechas_validas.max()


def contar_alertas_actuales(df):
    try:
        resultado = evaluar_alertas_operacionales(df)
        detalle = resultado.get("detalle", pd.DataFrame())
        if isinstance(detalle, pd.DataFrame):
            return len(detalle)
    except Exception:
        pass
    return None


def _render_accesos(accesos):
    for titulo, descripcion, pagina in accesos:
        st.markdown(
            f"""
            <div class="home-card">
                <h4>{titulo}</h4>
                <p>{descripcion}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if hasattr(st, "page_link"):
            st.page_link(pagina, label=f"Ir a {titulo}", width="stretch")
        elif st.button(f"Ir a {titulo}", key=f"nav_{Path(pagina).stem}", width="stretch"):
            st.switch_page(pagina)


def render_inicio(df_reportes):
    total_registros = db.contar_registros() if db.DB_PATH.exists() else len(df_reportes)
    fecha_min, fecha_max = db.obtener_rango_fechas() if db.DB_PATH.exists() else (None, None)
    ultima_fecha = fecha_max or ultima_fecha_registrada(df_reportes)
    total_pdfs = contar_pdfs_generados()
    if db.DB_PATH.exists():
        try:
            total_alertas = len(db.consultar_alertas_operacionales_filtradas()["detalle"])
        except Exception:
            total_alertas = contar_alertas_actuales(df_reportes)
    else:
        total_alertas = contar_alertas_actuales(df_reportes)

    st.markdown('<div class="rp-section-title">Centro de control</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="home-lead">
            <p>
                Sistema operacional para registrar, analizar y auditar reportes de perforación.
                Consolida historial, alertas, trazabilidad, PDF y estado de flota en una vista de trabajo.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Excel activo: {EXCEL_PATH.resolve()}")

    st.markdown(
        """
        <div class="rp-control-strip">
            <div class="rp-control-tile">Registro</div>
            <div class="rp-control-tile">Dashboard</div>
            <div class="rp-control-tile">Alertas</div>
            <div class="rp-control-tile">Respaldo</div>
            <div class="rp-control-tile">Análisis</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Registros", f"{total_registros:,}")
    col2.metric(
        "Última fecha",
        ultima_fecha.strftime("%d-%m-%Y") if ultima_fecha is not None else "Sin datos",
    )
    col3.metric("PDFs generados", f"{total_pdfs:,}")
    col4.metric(
        "Alertas actuales",
        f"{total_alertas:,}" if total_alertas is not None else "No disponible",
    )

    grupos = [
        (
            "Operación diaria",
            [
                ("Registro Operacional", "Ingreso de reportes diarios y control de turno.", "pages/01_Registro_Operacional.py"),
                ("Dashboard Operacional", "KPIs, filtros, productividad y seguimiento por equipo.", "pages/02_Dashboard_Operacional.py"),
                ("Reportes PDF", "Generación y consulta de reportes documentales.", "pages/07_Reportes_PDF.py"),
                ("Alertas Operacionales", "Alertas por horas, productividad y condiciones de turno.", "pages/06_Alertas_Operacionales.py"),
            ],
        ),
        (
            "Control y mejora",
            [
                ("Calidad de Datos", "Validación de consistencia, reglas y registros críticos.", "pages/12_Calidad_Datos.py"),
                ("Acciones Correctivas", "Seguimiento de compromisos derivados de alertas y calidad.", "pages/13_Acciones_Correctivas.py"),
                ("Auditoría", "Historial operacional, edición controlada y trazabilidad.", "pages/16_Auditoria_Historial.py"),
                ("Respaldos", "Integridad, exportaciones y respaldo manual.", "pages/18_Respaldos_Exportacion.py"),
            ],
        ),
        (
            "Análisis avanzado",
            [
                ("Panel Ejecutivo", "Vista resumida para jefatura y salud operacional.", "pages/08_Panel_Ejecutivo.py"),
                ("Alertas Inteligentes", "Motor incremental de alertas persistentes.", "pages/11_Alertas_Inteligentes.py"),
                ("Análisis Mensual", "Resumen mensual, rankings y diagnóstico automático.", "pages/09_Analisis_Mensual.py"),
                ("Machine Learning", "Predicción operacional y variables del modelo.", "pages/15_Machine_Learning.py"),
            ],
        ),
        (
            "Terreno y documentación",
            [
                ("Avance de Malla", "Planos, pozos, comparación y control visual.", "pages/04_Gestion_Planos.py"),
                ("Ortomosaico Vista Mina", "Vista mina y apoyo visual geoespacial.", "pages/05_Ortomosaico_Vista_Mina.py"),
                ("Biblioteca Técnica", "Documentos, manuales y procedimientos operacionales.", "pages/14_Biblioteca_Tecnica.py"),
            ],
        ),
    ]

    st.markdown('<div class="rp-section-title">Navegación por flujo</div>', unsafe_allow_html=True)
    for nombre_grupo, accesos in grupos:
        st.markdown(f'<div class="rp-section-title rp-nav-group">{nombre_grupo}</div>', unsafe_allow_html=True)
        columnas = st.columns(4)
        for columna, acceso in zip(columnas, accesos):
            with columna:
                _render_accesos([acceso])

