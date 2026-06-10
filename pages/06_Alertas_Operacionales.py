from pathlib import Path
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from ui.page_header import render_page_header
import db
from operators import etiqueta_operador
from ui.formatting import dataframe_visible, texto_visible
from utils import EXCEL_PATH


TIPOS_ALERTA = [
    "Disponibilidad 100% con mantención",
    "Utilización muy baja",
    "Rendimiento bajo",
    "Horas turno distintas de 12",
]


def opciones_columna_sql(columna):
    return db.obtener_valores_distintos_columna(columna)


def filtros_alertas_sql():
    with app.st.sidebar:
        app.st.header("Filtros alertas")

        rango = app.st.date_input(
            "Fecha",
            value=None,
            key="alertas_fecha",
        )
        equipo = app.st.multiselect(
            "Equipo",
            opciones_columna_sql("Modelo equipo"),
            format_func=texto_visible,
            key="alertas_equipo",
        )
        operador = app.st.multiselect(
            "Operador",
            opciones_columna_sql("Operador"),
            format_func=lambda valor: texto_visible(etiqueta_operador(valor)),
            key="alertas_operador",
        )
        tipo_alerta = app.st.multiselect(
            "Tipo de alerta",
            TIPOS_ALERTA,
            format_func=texto_visible,
            key="alertas_tipo",
        )

    fecha_desde = fecha_hasta = None
    if isinstance(rango, tuple) and len(rango) == 2:
        fecha_desde, fecha_hasta = rango

    return {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "equipo": equipo,
        "operador": operador,
        "tipo_alerta": tipo_alerta,
    }


def formatear_detalle(detalle):
    if detalle.empty:
        return detalle

    resultado = detalle.copy()
    columnas_fecha = [col for col in resultado.columns if "Fecha" in col]
    for columna in columnas_fecha:
        resultado[columna] = pd.to_datetime(resultado[columna], errors="coerce", dayfirst=True).dt.strftime("%d-%m-%Y")
    return resultado


def main():
    if not app.requerir_acceso():
        return
    render_page_header(app.st, 
        "Alertas Operacionales",
        f"Alertas por disponibilidad, utilización, rendimiento y horas de turno | Fuente: {EXCEL_PATH.parent}",
    )

    filtros = filtros_alertas_sql()
    total_registros = db.contar_historial_filtrado(
        fecha_desde=filtros["fecha_desde"],
        fecha_hasta=filtros["fecha_hasta"],
        equipo=filtros["equipo"],
        operador=filtros["operador"],
    )

    app.st.subheader("Alertas operacionales")
    app.st.caption("Fuente: SQLite vía consultas SQL filtradas y services.alert_service.evaluar_alertas_operacionales()")

    filas_por_pagina = app.st.number_input(
        "Filas por página",
        min_value=1,
        max_value=1000,
        value=min(250, max(total_registros, 1)),
        step=25,
        key="alertas_filas_pagina",
    )
    total_paginas = max(1, (total_registros + int(filas_por_pagina) - 1) // int(filas_por_pagina))
    pagina = app.st.number_input(
        "Página",
        min_value=1,
        max_value=total_paginas,
        value=1,
        step=1,
        key="alertas_pagina",
    )
    inicio = (int(pagina) - 1) * int(filas_por_pagina)

    resultado = db.consultar_alertas_operacionales_filtradas(
        fecha_desde=filtros["fecha_desde"],
        fecha_hasta=filtros["fecha_hasta"],
        equipo=filtros["equipo"],
        operador=filtros["operador"],
        tipo_alerta=filtros["tipo_alerta"],
        limit=int(filas_por_pagina),
        offset=inicio,
    )

    mensajes = resultado.get("mensajes", [])
    detalle = resultado.get("detalle", pd.DataFrame())
    sin_alertas = bool(resultado.get("sin_alertas", False))
    if mensajes:
        for nivel, mensaje in mensajes:
            if nivel == "error":
                app.st.error(texto_visible(mensaje))
            elif nivel == "warning":
                app.st.warning(texto_visible(mensaje))
            else:
                app.st.info(texto_visible(mensaje))

    if sin_alertas or detalle.empty:
        app.st.info("No se detectaron alertas operacionales para los filtros seleccionados.")
    else:
        detalle = formatear_detalle(detalle)
        total_detalle = len(detalle)
        app.st.caption(
            f"Mostrando {inicio + 1}-{inicio + total_detalle} de {total_registros} registros analizados."
        )
        if total_detalle > 0:
            app.st.dataframe(dataframe_visible(detalle), width="stretch", hide_index=True)
        if "Recomendación operacional" in detalle.columns:
            app.st.caption("La tabla incluye la recomendación operacional asociada cuando aplica.")


main()
