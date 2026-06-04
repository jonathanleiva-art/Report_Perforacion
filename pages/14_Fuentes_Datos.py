from pathlib import Path
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from services import data_source_selector_service as selector_service
from services import source_adapter_service, source_routing_helpers
from ui.formatting import dataframe_visible, texto_visible
from ui.page_header import render_page_header


def _formatear_fecha(valor):
    if not valor:
        return ""
    fecha = pd.to_datetime(valor, errors="coerce")
    if pd.notna(fecha):
        return fecha.strftime("%Y-%m-%d")
    return str(valor)


def _enriquecer_fuentes(fuentes):
    if fuentes.empty:
        return fuentes

    filas = []
    for _, fuente in fuentes.iterrows():
        item = fuente.to_dict()
        id_fuente = item.get("id_fuente")
        validacion = source_adapter_service.validar_fuente_soportada(id_fuente)
        resumen = source_adapter_service.calcular_resumen_fuente_normalizado(id_fuente)
        tipo_fuente = resumen.get("tipo_fuente") or validacion.get("tipo_fuente") or item.get("tipo_dashboard")
        soporte = validacion.get("soporte")

        item.update({
            "tipo_dashboard": tipo_fuente,
            "soporte": soporte,
            "registros": resumen.get("registros"),
            "metros_totales": resumen.get("metros_totales"),
            "fecha_min": resumen.get("fecha_min") or item.get("fecha_min"),
            "fecha_max": resumen.get("fecha_max") or item.get("fecha_max"),
            "mensaje_operacional": source_routing_helpers.obtener_mensaje_orientacion(tipo_fuente, soporte),
            "mensaje_adaptador": validacion.get("mensaje") or resumen.get("mensaje") or "",
        })
        filas.append(item)
    return pd.DataFrame(filas)


def _tabla_fuentes(fuentes):
    if fuentes.empty:
        return fuentes
    resultado = fuentes.copy()
    for columna in ["fecha_min", "fecha_max", "fecha_importacion"]:
        if columna in resultado.columns:
            resultado[columna] = resultado[columna].map(_formatear_fecha)
    columnas = [
        "id_fuente",
        "nombre_fuente",
        "tipo_fuente",
        "tipo_dashboard",
        "estado",
        "soporte",
        "registros",
        "metros_totales",
        "fecha_min",
        "fecha_max",
        "archivo_origen",
        "recomendacion_dashboard",
        "mensaje_operacional",
    ]
    visibles = [columna for columna in columnas if columna in resultado.columns]
    return resultado[visibles]


def _mostrar_resumen(resumen, validacion=None, mensaje_operacional=""):
    if not resumen:
        app.st.info("No hay resumen disponible para la fuente seleccionada.")
        return
    fila_1 = app.st.columns(4)
    fila_1[0].metric("Registros", f"{int(resumen.get('registros') or 0):,}")
    fila_1[1].metric("Metros totales", f"{float(resumen.get('metros_totales') or 0):,.2f}")
    fila_1[2].metric("Fecha minima", _formatear_fecha(resumen.get("fecha_min")) or "Sin fecha")
    fila_1[3].metric("Fecha maxima", _formatear_fecha(resumen.get("fecha_max")) or "Sin fecha")

    fila_2 = app.st.columns(4)
    fila_2[0].metric("Equipos", f"{int(resumen.get('equipos') or 0):,}")
    fila_2[1].metric("Operadores", f"{int(resumen.get('operadores') or 0):,}")
    fila_2[2].metric("Tipo fuente", texto_visible(resumen.get("tipo_fuente", "")))
    fila_2[3].metric("Soporte", texto_visible((validacion or {}).get("soporte", "")))

    if mensaje_operacional:
        app.st.info(texto_visible(mensaje_operacional))
    mensaje_adaptador = (validacion or {}).get("mensaje") or resumen.get("mensaje")
    if mensaje_adaptador:
        app.st.caption(texto_visible(mensaje_adaptador))


def main():
    if not app.requerir_acceso():
        return
    render_page_header(
        app.st,
        "Fuentes de Datos",
        "Selector informativo de fuentes operacionales disponibles. No mezcla datos ni abre dashboards.",
    )

    fuentes = selector_service.listar_fuentes_disponibles()
    if fuentes.empty:
        app.st.info("No hay fuentes disponibles.")
        return
    fuentes_enriquecidas = _enriquecer_fuentes(fuentes)

    app.st.subheader("Fuentes disponibles")
    app.st.dataframe(dataframe_visible(_tabla_fuentes(fuentes_enriquecidas)), width="stretch", hide_index=True)

    opciones = {
        f"{fila.id_fuente} - {texto_visible(fila.nombre_fuente)}": fila.id_fuente
        for fila in fuentes_enriquecidas.itertuples()
    }
    seleccion = app.st.selectbox(
        "Fuente para revisar",
        options=list(opciones.keys()),
        key="fuentes_datos_selector",
    )
    id_fuente = opciones[seleccion]
    fuente = selector_service.obtener_fuente_seleccionable(id_fuente)
    validacion = source_adapter_service.validar_fuente_soportada(id_fuente)
    resumen = source_adapter_service.calcular_resumen_fuente_normalizado(id_fuente)
    mensaje_operacional = source_routing_helpers.obtener_mensaje_orientacion(
        resumen.get("tipo_fuente") or validacion.get("tipo_fuente"),
        validacion.get("soporte"),
    )

    app.st.subheader("Detalle de fuente seleccionada")
    if fuente:
        detalle = _enriquecer_fuentes(pd.DataFrame([fuente]))
        app.st.dataframe(dataframe_visible(_tabla_fuentes(detalle)), width="stretch", hide_index=True)
    _mostrar_resumen(resumen, validacion=validacion, mensaje_operacional=mensaje_operacional)

    col_recomendacion, col_validacion = app.st.columns(2)
    if col_recomendacion.button("Ver recomendación", key="fuentes_ver_recomendacion"):
        col_recomendacion.info(texto_visible(mensaje_operacional))
    if col_validacion.button("Validar soporte", key="fuentes_validar_soporte"):
        soporte = texto_visible(validacion.get("soporte", ""))
        mensaje = texto_visible(validacion.get("mensaje", "")) or "Fuente validada para consulta informativa."
        col_validacion.info(f"Soporte: {soporte}. {mensaje}")

    app.st.info(
        "Esta pagina solo orienta la seleccion. La integracion o mezcla de fuentes debe definirse en una fase posterior."
    )


main()
