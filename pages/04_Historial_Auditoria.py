from pathlib import Path
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
import db
from audit.audit_log import AUDIT_LOG_PATH
from ui.formatting import dataframe_visible, texto_visible
from utils import EXCEL_PATH


def filtros_historial_sql():
    with app.st.sidebar:
        app.st.header("Filtros historial")

        rango = app.st.date_input(
            "Fecha",
            value=None,
            key="historial_fecha",
        )
        turno = app.st.multiselect(
            "Turno",
            db.obtener_valores_distintos_columna("Turno"),
            format_func=texto_visible,
            key="historial_turno",
        )
        equipo = app.st.multiselect(
            "Equipo",
            db.obtener_valores_distintos_columna("Modelo equipo"),
            format_func=texto_visible,
            key="historial_equipo",
        )
        numero = app.st.multiselect(
            "Número equipo",
            db.obtener_valores_distintos_columna("Número equipo"),
            format_func=texto_visible,
            key="historial_numero",
        )
        operador = app.st.multiselect(
            "Operador",
            db.obtener_valores_distintos_columna("Operador"),
            format_func=texto_visible,
            key="historial_operador",
        )
        banco = app.st.multiselect(
            "Banco",
            db.obtener_valores_distintos_columna("Banco"),
            format_func=texto_visible,
            key="historial_banco",
        )
        malla = app.st.multiselect(
            "Malla",
            db.obtener_valores_distintos_columna("Malla"),
            format_func=texto_visible,
            key="historial_malla",
        )

    fecha_desde = fecha_hasta = None
    if isinstance(rango, tuple) and len(rango) == 2:
        fecha_desde, fecha_hasta = rango

    return {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "turno": turno,
        "equipo": equipo,
        "operador": operador,
        "banco": banco,
        "malla": malla,
    }


def leer_audit_log():
    path = Path(AUDIT_LOG_PATH)
    if not path.exists():
        return None

    try:
        audit_df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

    if audit_df.empty:
        return pd.DataFrame()

    return audit_df


def main():
    app.st.title("PerfoControl – Sistema de Gestión Operacional de Perforación")
    app.st.caption(
        f"Historial y auditoría | Aplicación oficial: {EXCEL_PATH.parent} | Versión actual: {app.version_sistema()}"
    )

    filtros = filtros_historial_sql()
    total_registros = db.contar_historial_filtrado(**filtros)
    df_filtrado = db.consultar_historial_filtrado(**filtros)

    app.st.subheader("Historial operacional")
    app.st.caption("Fuente: SQLite vía consultas SQL filtradas")
    if df_filtrado.empty:
        app.st.info("No hay registros operacionales para mostrar.")
    else:
        filas_por_pagina = app.st.number_input(
            "Filas por página",
            min_value=1,
            max_value=1000,
            value=min(250, total_registros),
            step=25,
            key="historial_filas_pagina",
        )
        total_paginas = max(1, (total_registros + int(filas_por_pagina) - 1) // int(filas_por_pagina))
        pagina = app.st.number_input(
            "Página",
            min_value=1,
            max_value=total_paginas,
            value=1,
            step=1,
            key="historial_pagina",
        )
        inicio = (int(pagina) - 1) * int(filas_por_pagina)
        fin = min(inicio + int(filas_por_pagina), total_registros)
        app.st.caption(f"Mostrando {inicio + 1}-{fin} de {total_registros} registros.")
        pagina_df = db.consultar_historial_filtrado(
            **filtros,
            limit=int(filas_por_pagina),
            offset=inicio,
        )
        app.st.dataframe(dataframe_visible(pagina_df), width="stretch", hide_index=True)

    app.st.subheader("Audit log")
    app.st.caption("Fuente: logs/audit_log.csv vía audit.audit_log.AUDIT_LOG_PATH")
    audit_df = leer_audit_log()
    audit_path = Path(AUDIT_LOG_PATH)

    if audit_df is None:
        app.st.info("No existe logs/audit_log.csv.")
    elif audit_df.empty:
        if audit_path.exists():
            app.st.info("logs/audit_log.csv existe, pero aún no contiene eventos.")
        else:
            app.st.info("No existe logs/audit_log.csv.")
    else:
        app.st.dataframe(dataframe_visible(audit_df), width="stretch", hide_index=True)


main()
