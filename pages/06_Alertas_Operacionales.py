from datetime import date, timedelta
from pathlib import Path
import sqlite3
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from ui.page_header import render_page_header
import db
from operators import etiqueta_operador
from services import catalog_service
from ui.formatting import dataframe_visible, texto_visible
from utils import EXCEL_PATH


EQUIPOS_FLOTA = catalog_service.FLOTA_EQUIPOS
TURNOS_ESPERADOS = ["Día", "Noche"]


def mostrar_alertas_turnos_faltantes():
    hoy = date.today()
    inicio_periodo = hoy - timedelta(days=6)
    fechas_periodo = [inicio_periodo + timedelta(days=i) for i in range(7)]

    try:
        with sqlite3.connect(str(db.DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cols = db.columnas_tabla(conn)
            col_fecha  = db._resolver_columna_existente(cols, "Fecha turno", "Fecha")
            col_turno  = db._resolver_columna_existente(cols, "Turno")
            col_equipo = db._resolver_columna_existente(cols, "Número equipo", "Numero equipo", "Nro equipo")
            if not col_fecha or not col_turno or not col_equipo:
                app.st.warning("Estructura de la BD no compatible para consultar turnos faltantes.")
                return
            query = (
                f'SELECT {db.quote_identifier(col_fecha)},'
                f' {db.quote_identifier(col_turno)},'
                f' {db.quote_identifier(col_equipo)}'
                f' FROM {db.quote_identifier(db.TABLA_REGISTROS)}'
                f' WHERE {db.quote_identifier(col_fecha)} >= ?'
            )
            rows = conn.execute(query, (inicio_periodo.strftime("%Y-%m-%d"),)).fetchall()
            rows = [(r[0], r[1], r[2]) for r in rows]
    except Exception as exc:
        app.st.warning(f"No se pudo consultar turnos faltantes: {exc}")
        return

    registrados = set()
    for fecha_str, turno, numero in rows:
        try:
            fecha_d = pd.to_datetime(fecha_str, errors="coerce").date()
            if pd.isna(fecha_d):
                continue
            numero_str = str(numero).strip()
            try:
                numero_str = str(int(float(numero_str)))
            except (ValueError, TypeError):
                pass
            registrados.add((str(fecha_d), str(turno).strip(), numero_str))
        except Exception:
            continue

    faltantes_por_fecha: dict[str, list[str]] = {}
    for fecha_d in fechas_periodo:
        for turno in TURNOS_ESPERADOS:
            for equipo in EQUIPOS_FLOTA:
                if (str(fecha_d), turno, equipo) not in registrados:
                    label = fecha_d.strftime("%d-%m-%Y")
                    faltantes_por_fecha.setdefault(label, []).append(f"Equipo {equipo} – {turno}")

    app.st.subheader("Turnos faltantes — últimos 7 días")
    app.st.caption(f"Flota monitoreada: {', '.join(EQUIPOS_FLOTA)} | Turnos: {', '.join(TURNOS_ESPERADOS)}")
    if not faltantes_por_fecha:
        app.st.success(
            f"Todos los turnos registrados: los {len(EQUIPOS_FLOTA)} equipos de flota "
            f"tienen reporte para Día y Noche en los últimos 7 días."
        )
    else:
        total_faltantes = sum(len(v) for v in faltantes_por_fecha.values())
        app.st.caption(f"{total_faltantes} combinación(es) turno-equipo sin reporte en el período.")
        for label in sorted(faltantes_por_fecha, key=lambda x: pd.to_datetime(x, dayfirst=True)):
            faltantes = faltantes_por_fecha[label]
            app.st.error(
                f"**{label}** — Faltan {len(faltantes)} reporte(s): "
                + " | ".join(faltantes)
            )


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

    mostrar_alertas_turnos_faltantes()

    app.st.divider()
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
