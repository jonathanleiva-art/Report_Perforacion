from io import BytesIO
from pathlib import Path
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
import db
from services import data_quality_service
from ui.formatting import dataframe_visible, texto_visible


def _opciones(columna):
    try:
        return db.obtener_valores_distintos_columna(columna)
    except Exception:
        return []


def _normalizar_rango(rango):
    if isinstance(rango, tuple) and len(rango) == 2 and all(valor is not None for valor in rango):
        return rango[0], rango[1]
    return None, None


def _filtros_sidebar():
    with app.st.sidebar:
        app.st.header("Filtros de calidad")
        rango = app.st.date_input("Rango de fechas", value=None, format="DD/MM/YYYY", key="calidad_fecha")
        turno = app.st.multiselect(
            "Turno",
            _opciones("Turno"),
            default=_opciones("Turno"),
            format_func=texto_visible,
            key="calidad_turno",
        )
        equipo = app.st.multiselect(
            "Equipo",
            _opciones("Modelo equipo"),
            default=_opciones("Modelo equipo"),
            format_func=texto_visible,
            key="calidad_equipo",
        )
        operador = app.st.multiselect(
            "Operador",
            _opciones("Operador"),
            default=_opciones("Operador"),
            format_func=texto_visible,
            key="calidad_operador",
        )

    fecha_desde, fecha_hasta = _normalizar_rango(rango)
    return {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "turno": turno,
        "equipo": equipo,
        "operador": operador,
    }


def _formato_estado(estado):
    return {
        "excelente": ("#16A34A", "Excelente", "La calidad está bajo control."),
        "aceptable": ("#2563EB", "Aceptable", "La calidad es estable con observaciones puntuales."),
        "observado": ("#D97706", "Observado", "Existen inconsistencias que requieren seguimiento."),
        "critico": ("#DC2626", "Crítico", "La calidad requiere corrección prioritaria."),
    }.get(
        estado.get("estado", "observado"),
        ("#D97706", "Observado", "Existen inconsistencias que requieren seguimiento."),
    )


def _mostrar_metricas(resultado):
    estado_color, estado_titulo, estado_texto = _formato_estado(resultado["estado"])
    col1, col2, col3, col4, col5 = app.st.columns(5)
    col1.metric("Score calidad", f"{resultado['score']:.2f}")
    col2.metric("Analizados", f"{resultado['evaluacion']['total_registros']:,.0f}")
    col3.metric("Errores", f"{resultado['evaluacion']['errores']:,.0f}")
    col4.metric("Advertencias", f"{resultado['evaluacion']['advertencias']:,.0f}")
    col5.metric("Reglas no evaluadas", f"{resultado['evaluacion']['reglas_no_evaluadas']:,.0f}")
    app.st.markdown(
        f"""
        <div style="border-left:6px solid {estado_color}; padding:0.75rem 1rem; background:#f8fafc; margin:0.5rem 0 1rem 0;">
            <strong>{estado_titulo}</strong><br/>
            {estado_texto}<br/>
            <span style="color:#475569;">{resultado['estado']['mensaje']}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _ordenar_detalle(detalle):
    if detalle.empty or "Estado" not in detalle.columns:
        return detalle

    orden = {"ERROR": 0, "WARNING": 1, "NO_EVALUADA": 2}
    resultado = detalle.copy()
    resultado["_orden"] = resultado["Estado"].map(orden).fillna(3)
    columnas = [col for col in ["_orden", "fila", "Regla", "Estado"] if col in resultado.columns]
    return resultado.sort_values(columnas).drop(columns=["_orden"])


def _armar_export_excel(resumen, detalle, reglas_no_evaluadas):
    salida = BytesIO()
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        resumen.to_excel(writer, index=False, sheet_name="Resumen")
        detalle.to_excel(writer, index=False, sheet_name="Observaciones")
        reglas_no_evaluadas.to_excel(writer, index=False, sheet_name="Reglas no evaluadas")
    salida.seek(0)
    return salida.getvalue()


def main():
    app.st.title("Calidad de Datos")
    app.st.caption(f"Diagnóstico defensivo de datos operacionales | Fuente oficial: {db.DB_PATH.name}")

    filtros = _filtros_sidebar()
    df = db.consultar_historial_filtrado(
        fecha_desde=filtros["fecha_desde"],
        fecha_hasta=filtros["fecha_hasta"],
        turno=filtros["turno"],
        equipo=filtros["equipo"],
        operador=filtros["operador"],
    )

    resultado = data_quality_service.generar_resumen_ejecutivo_calidad(df)
    detalle = _ordenar_detalle(resultado["evaluacion"]["detalle"])
    reglas_no_evaluadas = detalle[detalle["Estado"].astype(str).eq("NO_EVALUADA")].copy() if not detalle.empty and "Estado" in detalle.columns else detalle.head(0).copy()

    _mostrar_metricas(resultado)

    app.st.subheader("Resumen ejecutivo")
    c1, c2 = app.st.columns([2, 1])
    with c1:
        app.st.info(f"Recomendación operacional: {texto_visible(resultado['recomendacion_operacional'])}")
    with c2:
        app.st.download_button(
            "Descargar reporte Excel",
            data=_armar_export_excel(resultado["resumen"], detalle, reglas_no_evaluadas),
            file_name="reporte_calidad_datos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    if resultado["evaluacion"]["reglas_no_evaluadas"] > 0:
        app.st.warning(f"Hay {resultado['evaluacion']['reglas_no_evaluadas']} regla(s) no evaluada(s) por columna faltante.")

    col_a, col_b = app.st.columns([1, 1])
    with col_a:
        app.st.subheader("Principales 5 problemas detectados")
        if resultado["top_problemas"].empty:
            app.st.success("No se detectaron problemas relevantes en los filtros actuales.")
        else:
            app.st.dataframe(dataframe_visible(resultado["top_problemas"]), width="stretch", hide_index=True)

    with col_b:
        app.st.subheader("Registros críticos priorizados")
        if resultado["registros_criticos"].empty:
            app.st.success("No hay registros críticos priorizados para los filtros actuales.")
        else:
            app.st.dataframe(dataframe_visible(resultado["registros_criticos"]), width="stretch", hide_index=True)

    app.st.subheader("Observaciones")
    if detalle.empty:
        app.st.success("No se detectaron observaciones para los filtros actuales.")
    else:
        app.st.dataframe(
            dataframe_visible(detalle),
            width="stretch",
            hide_index=True,
            column_config={
                "Regla": app.st.column_config.TextColumn("Regla", pinned=True),
                "Estado": app.st.column_config.TextColumn("Estado", pinned=True),
                "Recomendación operacional": app.st.column_config.TextColumn("Recomendación operacional"),
            },
        )


main()
