from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from ui.page_header import render_page_header
from dashboard import dashboard as dashboard_view
from ui.alerts_view import mostrar_alertas_operacionales
from ui.data_source import cargar_dataframe_fuente, seleccionar_fuente_datos
from ui.filters import aplicar_filtros
from ui.pdf_section import seccion_reporte_pdf
from utils import EXCEL_PATH, limpiar_entero, ruta_imagen_equipo


def main():
    if not app.requerir_acceso():
        return
    render_page_header(app.st, 
        "Dashboard Operacional",
        f"KPIs, productividad, alertas y seguimiento por equipo | Fuente: {EXCEL_PATH.parent}",
    )

    fuente = seleccionar_fuente_datos(app.st, key="dashboard_operacional_fuente")
    df_reportes = cargar_dataframe_fuente(fuente)
    app.st.caption(f"Fuente de datos activa: {fuente}")
    dashboard_view(
        df_reportes,
        aplicar_filtros_fn=aplicar_filtros,
        mostrar_alerta_reportes_faltantes_fn=app.mostrar_alerta_reportes_faltantes,
        mostrar_alertas_operacionales_fn=mostrar_alertas_operacionales,
        seccion_reporte_pdf_fn=seccion_reporte_pdf,
        resumen_operacional_equipos_fn=app.resumen_operacional_equipos,
        equipos_esperados_fn=app.equipos_esperados,
        ruta_imagen_equipo_fn=ruta_imagen_equipo,
        limpiar_entero_fn=limpiar_entero,
        color_estado_operacional_fn=app.color_estado_operacional,
        color_texto_estado_operacional_fn=app.color_texto_estado_operacional,
        columnas_horas_turno_fn=app.columnas_horas_turno,
        etiqueta_hora_fn=app.etiqueta_hora,
    )


main()
