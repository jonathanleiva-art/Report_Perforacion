from pathlib import Path

import pandas as pd
import streamlit as st

from alerts import evaluar_alertas_operacionales
import db
from schema import columnas_equivalentes
from utils import EXCEL_PATH


REPORTES_PDF_DIR = Path(EXCEL_PATH).parent / "reportes_pdf"


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

    st.subheader("Inicio")
    st.write(
        "Sistema operacional para registrar, analizar y auditar reportes de perforación con "
        "historial centralizado, alertas operacionales y generación de PDF."
    )
    st.caption(f"Excel activo: {EXCEL_PATH.resolve()}")

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

    st.markdown(
        """
        <style>
        .home-card {
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 0.9rem 0.95rem;
            background: #ffffff;
            min-height: 130px;
        }
        .home-card h4 {
            margin: 0 0 0.35rem 0;
            font-size: 1.0rem;
        }
        .home-card p {
            margin: 0 0 0.65rem 0;
            color: #4b5563;
            font-size: 0.92rem;
            line-height: 1.35;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Accesos rápidos")
    cards = st.columns(5)
    accesos = [
        ("Dashboard Operacional", "KPIs, alertas y seguimiento operativo.", "pages/01_Dashboard_Operacional.py"),
        ("Formulario Registro", "Ingreso de reportes diarios y control de turno.", "pages/02_Formulario_Registro.py"),
        ("Reportes PDF", "Generación y consulta de reportes documentales.", "pages/03_Reportes_PDF.py"),
        ("Historial Auditoría", "Consulta de historial operacional y trazabilidad.", "pages/04_Historial_Auditoria.py"),
        ("Alertas Operacionales", "Vista consolidada de alertas y recomendaciones.", "pages/05_Alertas_Operacionales.py"),
    ]

    for columna, (titulo, descripcion, pagina) in zip(cards, accesos):
        with columna:
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
