from io import BytesIO
from pathlib import Path
import re
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from config import DATA_DIR
from services import ciclos_service, operational_excel_service, source_service
from ui.formatting import dataframe_visible
from ui.page_header import render_page_header


IMPORTS_DIR = DATA_DIR / "imports_ciclos"


def _nombre_seguro(nombre):
    base = Path(nombre or "excel_ciclos.xlsx").name
    return re.sub(r"[^A-Za-z0-9_. -]", "_", base)


def _xlsx_bytes(df):
    salida = BytesIO()
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Resumen")
    salida.seek(0)
    return salida


def _importar_excel():
    app.st.subheader("Importar Excel de ciclos")
    archivo = app.st.file_uploader(
        "Excel de ciclos de perforacion",
        type=["xls", "xlsx", "xlsm"],
        key="fuentes_excel_upload",
    )
    nombre_fuente = app.st.text_input(
        "Nombre visible de la fuente",
        placeholder="Ejemplo: Ciclos de Perforacion Excel - Mayo 2026",
        key="fuentes_excel_nombre",
    )
    observacion = app.st.text_area(
        "Observacion",
        placeholder="Contexto opcional del archivo importado",
        key="fuentes_excel_observacion",
    )
    if app.st.button("Importar Excel", type="primary", key="fuentes_excel_importar"):
        if archivo is None:
            app.st.warning("Selecciona un archivo Excel para importar.")
            return
        IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
        destino = IMPORTS_DIR / _nombre_seguro(archivo.name)
        destino.write_bytes(archivo.getbuffer())
        try:
            resultado = ciclos_service.importar_excel_ciclos(
                excel_path=destino,
                nombre_fuente=nombre_fuente.strip() or None,
                observacion=observacion.strip(),
            )
        except Exception as exc:
            app.st.error(f"No fue posible importar el Excel: {exc}")
            return
        app.st.success(
            "Excel importado: "
            f"{resultado['filas_importadas']:,} nuevos, "
            f"{resultado['duplicados_omitidos']:,} duplicados omitidos."
        )
        app.st.caption(f"Fuente registrada: {resultado.get('id_fuente')}")
        app.st.caption(f"Operadores pendientes CSV: {resultado.get('pendientes_csv')}")
        app.st.rerun()


def _administrar_fuentes():
    app.st.subheader("Fuentes importadas")
    fuentes = ciclos_service.resumen_fuentes_excel()
    if fuentes.empty:
        app.st.info("No hay fuentes Excel registradas.")
        return

    app.st.dataframe(dataframe_visible(fuentes), width="stretch", hide_index=True)
    app.st.download_button(
        "Exportar resumen",
        data=_xlsx_bytes(fuentes),
        file_name="resumen_fuentes_excel.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="fuentes_excel_exportar_resumen",
    )

    opciones = {
        f"{int(fila.id_fuente)} - {fila.nombre_fuente}": int(fila.id_fuente)
        for fila in fuentes.itertuples(index=False)
    }
    seleccion = app.st.selectbox(
        "Fuente a administrar",
        list(opciones.keys()),
        index=0,
        key="fuentes_excel_admin_select",
    )
    id_fuente = opciones[seleccion]
    fila = fuentes[fuentes["id_fuente"].astype(int).eq(id_fuente)].iloc[0]
    activa = str(fila.get("estado", "")).lower() == "activa"

    col1, col2, col3 = app.st.columns(3)
    with col1:
        nuevo_estado = app.st.toggle("Fuente activa", value=activa, key=f"fuente_activa_{id_fuente}")
        if nuevo_estado != activa:
            ciclos_service.actualizar_estado_fuente(id_fuente, nuevo_estado)
            app.st.success("Estado actualizado.")
            app.st.rerun()
    with col2:
        if app.st.button("Recalcular operadores", key=f"fuente_recalcular_{id_fuente}"):
            resultado = ciclos_service.recalcular_operadores_ciclos()
            app.st.success(f"Operadores recalculados en {resultado['registros_actualizados']:,} ciclos.")
    with col3:
        confirmar = app.st.checkbox("Confirmar eliminacion", key=f"fuente_confirmar_eliminar_{id_fuente}")
        if app.st.button("Eliminar fuente", disabled=not confirmar, key=f"fuente_eliminar_{id_fuente}"):
            resultado = ciclos_service.eliminar_fuente(id_fuente)
            app.st.warning(
                f"Fuente eliminada. Ciclos eliminados: {resultado['ciclos_eliminados']:,}."
            )
            app.st.rerun()


def _visualizar_fuentes_operacionales():
    app.st.subheader("Excel operacional importado")
    fuentes = operational_excel_service.resumen_fuentes_operacionales()
    if fuentes.empty:
        app.st.info("No hay fuentes Excel operacionales importadas.")
        return

    columnas = [
        "id_fuente",
        "nombre_fuente",
        "archivo_origen",
        "fecha_importacion",
        "fecha_min",
        "fecha_max",
        "total_registros",
        "registros_importados",
        "metros_importados",
        "equipos",
        "operadores",
        "estado",
        "activo",
    ]
    app.st.dataframe(dataframe_visible(fuentes[columnas]), width="stretch", hide_index=True)
    app.st.download_button(
        "Exportar resumen operacional",
        data=_xlsx_bytes(fuentes),
        file_name="resumen_fuentes_excel_operacional.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="fuentes_excel_operacional_exportar_resumen",
    )

    opciones = {
        f"{int(fila.id_fuente)} - {fila.nombre_fuente}": int(fila.id_fuente)
        for fila in fuentes.itertuples(index=False)
    }
    seleccion = app.st.selectbox(
        "Fuente operacional",
        list(opciones.keys()),
        index=0,
        key="fuentes_excel_operacional_select",
    )
    id_fuente = opciones[seleccion]
    registros = operational_excel_service.leer_operacional_dashboard(id_fuente=id_fuente)

    resumen = operational_excel_service.resumen_fuentes_operacionales()
    fila = resumen[resumen["id_fuente"].astype(int).eq(id_fuente)].iloc[0]
    activa = int(fila.get("activo") or 0) == 1

    col1, col2, col3, col4 = app.st.columns(4)
    col1.metric("Registros", f"{int(fila.get('registros_importados') or 0):,}")
    col2.metric("Metros", f"{float(fila.get('metros_importados') or 0):,.2f}")
    col3.metric("Equipos", f"{int(fila.get('equipos') or 0):,}")
    col4.metric("Operadores", f"{int(fila.get('operadores') or 0):,}")

    app.st.caption(f"Rango operacional: {fila.get('fecha_min') or 'No detectado'} a {fila.get('fecha_max') or 'No detectado'}")
    if not registros.empty:
        columnas_preview = [
            columna
            for columna in [
                "Fecha turno",
                "Turno",
                "Equipo",
                "Operador",
                "Metros perforados",
                "Horas efectivas perforando",
                "Horas averia equipo",
                "Horas Totales",
                "Disponibilidad %",
                "Utilizacion",
            ]
            if columna in registros.columns
        ]
        app.st.dataframe(dataframe_visible(registros[columnas_preview].head(200)), width="stretch", hide_index=True)
        if len(registros) > 200:
            app.st.caption(f"Mostrando 200 de {len(registros):,} registros importados.")

    col_estado, col_accion = app.st.columns(2)
    with col_estado:
        nuevo_estado = app.st.toggle("Fuente activa", value=activa, key=f"fuente_operacional_activa_{id_fuente}")
        if nuevo_estado != activa:
            source_service.actualizar_estado_fuente(
                id_fuente,
                "importada" if nuevo_estado else "inactiva",
                activo=1 if nuevo_estado else 0,
            )
            app.st.success("Estado actualizado.")
            app.st.rerun()
    with col_accion:
        if app.st.button("Usar en dashboard", key=f"fuente_operacional_dashboard_{id_fuente}"):
            app.st.session_state["dashboard_data_source"] = "excel_operacional"
            app.st.session_state["dashboard_data_source_id"] = id_fuente
            app.st.session_state["dashboard_data_source_label"] = str(fila.get("nombre_fuente") or seleccion)
            app.st.success("Fuente operacional seleccionada para el dashboard.")


def _comparar_fuentes():
    app.st.subheader("Comparar fuentes")
    fuentes = ciclos_service.listar_fuentes_datos(solo_activas=True)
    if len(fuentes) < 2:
        app.st.info("Se requieren al menos dos fuentes activas para comparar.")
        return

    opciones = {
        f"{int(fila.id_fuente)} - {fila.nombre_fuente}": int(fila.id_fuente)
        for fila in fuentes.itertuples(index=False)
    }
    col1, col2 = app.st.columns(2)
    actual = col1.selectbox("Excel actual", list(opciones.keys()), index=0, key="comparar_fuente_actual")
    anterior = col2.selectbox("Excel anterior", list(opciones.keys()), index=1, key="comparar_fuente_anterior")
    if opciones[actual] == opciones[anterior]:
        app.st.warning("Selecciona dos fuentes distintas.")
        return

    comparacion = ciclos_service.comparar_fuentes(opciones[actual], opciones[anterior])
    resumen = pd.DataFrame([comparacion["resumen_actual"], comparacion["resumen_anterior"]])
    resumen["fuente"] = ["Actual", "Anterior"]
    app.st.dataframe(dataframe_visible(resumen), width="stretch", hide_index=True)

    app.st.caption("Metros por equipo")
    app.st.dataframe(dataframe_visible(comparacion["metros_por_equipo"]), width="stretch", hide_index=True)
    app.st.caption("Metros por operador")
    app.st.dataframe(dataframe_visible(comparacion["metros_por_operador"]), width="stretch", hide_index=True)


def main():
    if not app.requerir_acceso(admin=True):
        return
    render_page_header(
        app.st,
        "Administrar fuentes Excel",
        "Registro, activacion y comparacion de Excel importados de ciclos de perforacion.",
    )
    tab_importar, tab_fuentes, tab_operacional, tab_comparar = app.st.tabs([
        "Importar",
        "Fuentes",
        "Operacional importado",
        "Comparar",
    ])
    with tab_importar:
        _importar_excel()
    with tab_fuentes:
        _administrar_fuentes()
    with tab_operacional:
        _visualizar_fuentes_operacionales()
    with tab_comparar:
        _comparar_fuentes()


main()
