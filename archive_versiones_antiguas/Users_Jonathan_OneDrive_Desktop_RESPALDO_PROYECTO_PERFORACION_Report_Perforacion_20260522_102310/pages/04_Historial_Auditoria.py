from pathlib import Path
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from audit.audit_log import AUDIT_LOG_PATH
from data import leer_reportes
from schema import columnas_equivalentes
from utils import EXCEL_PATH


def dataframe_visible(df):
    if hasattr(app, "dataframe_visible"):
        return app.dataframe_visible(df)
    resultado = df.copy()
    vistos = {}
    columnas = []
    for columna in resultado.columns:
        nombre = str(columna)
        vistos[nombre] = vistos.get(nombre, 0) + 1
        if vistos[nombre] > 1:
            nombre = f"{nombre} ({vistos[nombre]})"
        columnas.append(nombre)
    resultado.columns = columnas
    return resultado


def resolver_columna(df, clave):
    for nombre in columnas_equivalentes(clave):
        if nombre in df.columns:
            return nombre
    return None


def opciones_columna(df, clave):
    columna = resolver_columna(df, clave)
    if columna is None:
        return []
    serie = df[columna].dropna().astype(str).map(str.strip)
    return sorted(valor for valor in serie.unique() if valor)


def aplicar_filtros_historial(df):
    if df.empty:
        return df

    filtrado = df.copy()
    col_fecha = resolver_columna(filtrado, "fecha_turno")
    col_turno = resolver_columna(filtrado, "turno")
    col_equipo = resolver_columna(filtrado, "modelo_equipo")
    col_numero = resolver_columna(filtrado, "numero_equipo")
    col_operador = resolver_columna(filtrado, "operador")

    with app.st.sidebar:
        app.st.header("Filtros historial")

        if col_fecha and filtrado[col_fecha].notna().any():
            fechas = pd.to_datetime(filtrado[col_fecha], errors="coerce")
            fechas_validas = fechas.dropna()
            if not fechas_validas.empty:
                min_fecha = fechas_validas.min().date()
                max_fecha = fechas_validas.max().date()
                rango = app.st.date_input(
                    "Fecha",
                    value=(min_fecha, max_fecha),
                    min_value=min_fecha,
                    max_value=max_fecha,
                    key="historial_fecha",
                )
            else:
                rango = None
        else:
            rango = None

        turno = app.st.multiselect("Turno", opciones_columna(filtrado, "turno"), format_func=app.texto_visible, key="historial_turno")
        equipo = app.st.multiselect("Equipo", opciones_columna(filtrado, "modelo_equipo"), format_func=app.texto_visible, key="historial_equipo")
        numero = app.st.multiselect("Número equipo", opciones_columna(filtrado, "numero_equipo"), format_func=app.texto_visible, key="historial_numero")
        operador = app.st.multiselect("Operador", opciones_columna(filtrado, "operador"), format_func=app.texto_visible, key="historial_operador")

    if rango and len(rango) == 2 and col_fecha:
        fechas = pd.to_datetime(filtrado[col_fecha], errors="coerce").dt.date
        filtrado = filtrado[(fechas >= rango[0]) & (fechas <= rango[1])]
    if turno and col_turno:
        filtrado = filtrado[filtrado[col_turno].astype(str).isin(turno)]
    if equipo and col_equipo:
        filtrado = filtrado[filtrado[col_equipo].astype(str).isin(equipo)]
    if numero and col_numero:
        filtrado = filtrado[filtrado[col_numero].astype(str).isin(numero)]
    if operador and col_operador:
        filtrado = filtrado[filtrado[col_operador].astype(str).isin(operador)]

    return filtrado


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
    app.st.title("Sistema de Reporte de Perforación")
    app.st.caption(
        f"Historial y auditoría | Aplicación oficial: {EXCEL_PATH.parent} | Versión actual: {app.version_sistema()}"
    )

    df_reportes = leer_reportes()
    df_filtrado = aplicar_filtros_historial(df_reportes)

    app.st.subheader("Historial operacional")
    app.st.caption("Fuente: reportes_perforacion.xlsx vía data.leer_reportes()")
    if df_filtrado.empty:
        app.st.info("No hay registros operacionales para mostrar.")
    else:
        app.st.dataframe(dataframe_visible(df_filtrado), width="stretch", hide_index=True)

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
