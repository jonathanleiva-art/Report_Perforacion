from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

from config import REPORTS_PDF_DIR


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from ui.page_header import render_page_header
from ui.data_source import cargar_dataframe_fuente, seleccionar_fuente_datos
from ui.pdf_section import seccion_reporte_pdf
from utils import EXCEL_PATH


REPORTES_PDF_DIR = REPORTS_PDF_DIR


def dataframe_visible(df):
    return df.copy()


def mostrar_pdf_generados():
    app.st.subheader("PDF generados")
    if not REPORTES_PDF_DIR.exists():
        app.st.info("No existe la carpeta reportes_pdf.")
        return

    archivos = sorted(
        REPORTES_PDF_DIR.glob("*.pdf"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not archivos:
        app.st.info("No hay reportes PDF generados.")
        return

    app.st.dataframe(
        dataframe_visible(pd.DataFrame(
            [
                {
                    "Archivo": path.name,
                    "Fecha modificación": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "Tamaño KB": round(path.stat().st_size / 1024, 2),
                }
                for path in archivos
            ]
        )),
        width="stretch",
        hide_index=True,
    )


def main():
    if not app.requerir_acceso():
        return
    render_page_header(app.st, 
        "Reportes PDF",
        f"Generación, consulta y control documental de reportes | Fuente: {EXCEL_PATH.parent}",
    )

    fuente = seleccionar_fuente_datos(app.st, key="reportes_pdf_fuente")
    df_reportes = cargar_dataframe_fuente(fuente)
    app.st.caption(f"Fuente de datos activa: {fuente}")
    seccion_reporte_pdf(df_reportes)
    mostrar_pdf_generados()


main()
