import base64
from pathlib import Path
import re
import sys

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from ui.page_header import render_page_header
import db
from services.malla_service import (
    TIPOS_POZO_MALLA_CONTROL,
    listar_archivos_planos_malla,
    listar_pozos_malla_control,
    limpiar_avance_malla,
    registrar_archivo_plano_malla,
    registrar_pozo_malla_control,
    obtener_preview_plano_malla,
    resumen_malla_control,
    actualizar_pozo_malla_control,
    obtener_archivo_plano_malla,
)
from ui.formatting import dataframe_visible, texto_visible


COLOR_TIPO_POZO = {
    "Producción": "#EF4444",
    "Buffer": "#10B981",
    "Precorte": "#059669",
    "Otro": "#64748B",
}

COLOR_ESTADO_POZO = {
    "pendiente": "#94A3B8",
    "realizado": "#2563EB",
}


def _mostrar_carga_plano():
    with app.st.expander("Cargar plano de perforación", expanded=True):
        app.st.caption("Carga manual de un PDF. El archivo queda guardado en SQLite y en la carpeta local del módulo.")
        with app.st.form("form_carga_plano_visual", clear_on_submit=False):
            archivo = app.st.file_uploader("Plano PDF", type=["pdf"], key="plano_pdf_control")
            enviar = app.st.form_submit_button("Guardar plano", type="primary")
            if enviar:
                resultado = registrar_archivo_plano_malla(archivo)
                if resultado["ok"]:
                    app.st.success(resultado["mensaje"])
                    app.st.session_state["plano_control_seleccionado"] = resultado["archivo_id"]
                    app.st.rerun()
                else:
                    app.st.error(resultado["mensaje"])


def _mostrar_planos_cargados():
    app.st.subheader("Planos cargados")
    planos = listar_archivos_planos_malla()
    if planos.empty:
        app.st.info("Todavía no hay planos cargados.")
        return

    columnas = [
        columna
        for columna in ["id", "nombre_archivo", "ruta_archivo", "tipo_archivo", "fecha_carga", "categoria"]
        if columna in planos.columns
    ]
    app.st.dataframe(dataframe_visible(planos[columnas]), width="stretch", hide_index=True)


def _mostrar_vista_previa_plano(detalle_plano):
    app.st.subheader("Vista previa del plano")
    preview_path = obtener_preview_plano_malla(detalle_plano.get("id"))
    if preview_path and Path(preview_path).exists():
        app.st.image(str(preview_path), caption="Vista previa rasterizada del plano", use_container_width=True)
        app.st.caption(f"Previsualización PNG guardada en: {preview_path}")
    else:
        app.st.info("No se generó una vista previa PNG para el plano seleccionado.")

    ruta_plano = Path(detalle_plano.get("ruta_archivo", ""))
    if ruta_plano.suffix.lower() == ".pdf" and ruta_plano.exists():
        with app.st.expander("Ver PDF original", expanded=False):
            try:
                pdf_bytes = ruta_plano.read_bytes()
                pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
                app.st.components.v1.html(
                    f"""
                    <iframe
                        src="data:application/pdf;base64,{pdf_b64}"
                        width="100%"
                        height="760"
                        style="border: 1px solid #CBD5E1; border-radius: 12px; background: #FFFFFF;"
                    ></iframe>
                    """,
                    height=780,
                    scrolling=True,
                )
                app.st.caption("El PDF original queda como respaldo visual.")
            except Exception:
                app.st.info("No fue posible incrustar el PDF directamente; la imagen rasterizada queda como vista principal.")


def _normalizar_tipo_pozo(valor):
    texto = texto_visible(valor).strip()
    if texto.lower().startswith("prod"):
        return "Producción"
    if texto.lower().startswith("buff"):
        return "Buffer"
    if texto.lower().startswith("prec"):
        return "Precorte"
    return "Otro"


def _normalizar_estado(valor):
    texto = texto_visible(valor).strip().lower()
    return "realizado" if texto in {"realizado", "hecho", "ok", "1", "true"} else "pendiente"


def _parsear_lineas_pozos(texto):
    registros = []
    errores = []
    for indice, linea in enumerate(texto.splitlines(), start=1):
        linea = linea.strip()
        if not linea:
            continue
        partes = [parte.strip() for parte in re.split(r"[,\t;|]+", linea) if parte.strip()]
        if not partes:
            continue
        numero_pozo = partes[0]
        tipo_pozo = _normalizar_tipo_pozo(partes[1]) if len(partes) > 1 else "Otro"
        metros_planificados = 0.0
        if len(partes) > 2:
            try:
                metros_planificados = float(str(partes[2]).replace(",", "."))
            except ValueError:
                errores.append(f"Línea {indice}: metros planificados inválidos.")
        estado = _normalizar_estado(partes[3]) if len(partes) > 3 else "pendiente"
        observacion = partes[4] if len(partes) > 4 else ""
        registros.append(
            {
                "numero_pozo": numero_pozo,
                "tipo_pozo": tipo_pozo,
                "metros_planificados": metros_planificados,
                "estado": estado,
                "realizado": estado == "realizado",
                "observacion": observacion,
            }
        )
    return registros, errores


def _mostrar_registro_asistido():
    planos = listar_archivos_planos_malla()
    app.st.subheader("Registrar pozos de la malla")
    if planos.empty:
        app.st.info("Primero carga un plano PDF para asociar los pozos.")
        return

    opciones = {
        f"{fila['nombre_archivo']} | {fila['fecha_carga']} | {fila['tipo_archivo']}": int(fila["id"])
        for _, fila in planos.iterrows()
    }
    plano_id_actual = app.st.session_state.get("plano_control_seleccionado")
    ids = list(opciones.values())
    indice = ids.index(plano_id_actual) if plano_id_actual in ids else 0

    seleccion = app.st.selectbox(
        "Plano cargado",
        list(opciones.keys()),
        index=indice,
        key="plano_control_edicion",
    )
    plano_id = opciones[seleccion]
    detalle_plano = obtener_archivo_plano_malla(plano_id)
    if detalle_plano is None:
        app.st.info("No fue posible cargar el plano seleccionado.")
        return

    app.st.caption(f"Archivo: {detalle_plano.get('nombre_archivo', '')}")
    app.st.caption(f"Ruta: {detalle_plano.get('ruta_archivo', '')}")
    app.st.caption("El plano se carga como PDF y se mantiene como referencia visual/manual. No se usa OCR todavía.")
    _mostrar_vista_previa_plano(detalle_plano)

    with app.st.form("form_carga_pozos_malla", clear_on_submit=False):
        app.st.caption("Pega una lista de pozos. Formato sugerido por línea: numero_pozo,tipo_pozo,metros_planificados,estado,observacion")
        texto_pozos = app.st.text_area(
            "Lista de pozos",
            height=180,
            key="pozos_lista_control",
            placeholder="1,Producción,12.5,pendiente\n2,Buffer,10,realizado\n3,Precorte,8,pendiente",
        )
        enviar = app.st.form_submit_button("Cargar pozos", type="primary")
        if enviar:
            registros, errores = _parsear_lineas_pozos(texto_pozos)
            if not registros:
                app.st.error("No se detectaron pozos válidos para cargar.")
            else:
                for registro in registros:
                    registro["archivo_plano_id"] = plano_id
                    registrar_pozo_malla_control(registro)
                if errores:
                    app.st.warning(" | ".join(errores))
                app.st.success(f"Se cargaron {len(registros):,} pozos en la malla.")
                app.st.session_state["plano_control_seleccionado"] = plano_id
                app.st.rerun()

    pozos = listar_pozos_malla_control(archivo_plano_id=plano_id)
    if pozos.empty:
        app.st.info("Aún no hay pozos cargados para este plano.")
        return

    filtro_tipo = app.st.multiselect(
        "Filtrar por tipo de pozo",
        sorted([valor for valor in pozos["tipo_pozo"].dropna().astype(str).unique() if valor]),
        default=[],
        key="filtro_tipo_malla",
    )
    filtro_estado = app.st.multiselect(
        "Filtrar por estado",
        sorted([valor for valor in pozos["estado"].dropna().astype(str).unique() if valor]),
        default=[],
        key="filtro_estado_malla",
    )

    filtrado = pozos.copy()
    if filtro_tipo:
        filtrado = filtrado[filtrado["tipo_pozo"].astype(str).isin(filtro_tipo)]
    if filtro_estado:
        filtrado = filtrado[filtrado["estado"].astype(str).isin(filtro_estado)]

    resumen = resumen_malla_control(archivo_plano_id=plano_id)
    c1, c2, c3, c4 = app.st.columns(4)
    c1.metric("Pozos totales", int(resumen["pozos_totales"]))
    c2.metric("Pozos realizados", int(resumen["pozos_realizados"]))
    c3.metric("Pozos pendientes", int(resumen["pozos_pendientes"]))
    c4.metric("Avance", f"{float(resumen['porcentaje_avance']):,.2f}%")

    c5, c6 = app.st.columns(2)
    c5.metric("Metros planificados", f"{float(resumen['metros_planificados_totales']):,.2f}")
    c6.metric("Avance por metros", f"{float(resumen['avance_metros']):,.2f}%")

    app.st.caption(
        "La marca realizado/pendiente es manual y se puede corregir en cualquier momento. "
        "La visualización usa colores por tipo y estado."
    )

    editable = filtrado.copy()
    editable["realizado"] = editable["realizado"].fillna(0).astype(int).astype(bool)
    editable["estado"] = editable["estado"].fillna("pendiente").astype(str)
    editable["tipo_pozo"] = editable["tipo_pozo"].fillna("Otro").astype(str)
    editable["observacion"] = editable["observacion"].fillna("").astype(str)
    columnas_editor = [col for col in ["id", "numero_pozo", "tipo_pozo", "metros_planificados", "estado", "realizado", "observacion"] if col in editable.columns]
    editado = app.st.data_editor(
        dataframe_visible(editable[columnas_editor]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "realizado": app.st.column_config.CheckboxColumn("Realizado"),
        },
        key="editor_pozos_malla_control",
    )
    if app.st.button("Guardar cambios en la malla", key="guardar_cambios_malla_control"):
        if not isinstance(editado, pd.DataFrame):
            app.st.error("No se pudo leer la tabla editada.")
        else:
            for _, fila in editado.iterrows():
                actualizar_pozo_malla_control(
                    int(fila["id"]),
                    {
                        "numero_pozo": fila.get("numero_pozo", ""),
                        "tipo_pozo": fila.get("tipo_pozo", "Otro"),
                        "metros_planificados": fila.get("metros_planificados", 0),
                        "estado": "realizado" if bool(fila.get("realizado")) else "pendiente",
                        "realizado": bool(fila.get("realizado")),
                        "observacion": fila.get("observacion", ""),
                    },
                )
            app.st.success("Cambios guardados correctamente.")
            app.st.rerun()

    app.st.subheader("Vista por colores")
    if filtrado.empty:
        app.st.info("No hay registros para mostrar con los filtros actuales.")
        return

    for _, fila in filtrado.iterrows():
        tipo = str(fila.get("tipo_pozo", "Otro"))
        estado = str(fila.get("estado", "pendiente"))
        fondo = COLOR_TIPO_POZO.get(tipo, "#64748B")
        opacidad = "1" if estado == "realizado" else "0.35"
        borde = "#1D4ED8" if bool(fila.get("realizado")) else "#94A3B8"
        app.st.markdown(
            f"""
            <div style="
                border: 2px solid {borde};
                border-radius: 12px;
                padding: 12px 14px;
                margin-bottom: 10px;
                background: linear-gradient(90deg, {fondo}{'CC' if estado == 'realizado' else '55'}, {fondo}22);
                color: #0F172A;
            ">
                <strong>Pozo {texto_visible(fila.get('numero_pozo', ''))}</strong><br>
                Tipo: {texto_visible(tipo)} | Estado: {texto_visible(estado)} | Realizado: {"Sí" if bool(fila.get("realizado")) else "No"}<br>
                Metros planificados: {float(fila.get("metros_planificados", 0) or 0):,.2f}<br>
                Observación: {texto_visible(fila.get("observacion", ""))}
            </div>
            """,
            unsafe_allow_html=True,
        )

    if any(str(valor).lower() == "realizado" for valor in filtrado["estado"].astype(str).tolist()):
        app.st.caption("Los pozos realizados aparecen con borde más fuerte.")


def _mostrar_futuro_ocr_ia():
    with app.st.expander("Futuro OCR / IA", expanded=False):
        app.st.markdown(
            """
            Futuras capacidades documentadas:
            - detectar automáticamente números de pozo desde PDF;
            - identificar colores del plano;
            - clasificar Producción, Buffer y Precorte;
            - comparar foto del operador contra el plano;
            - marcar avance directamente sobre imagen.
            """
        )


def main():
    if not app.requerir_acceso():
        return
    render_page_header(app.st, "Avance de Malla")
    app.st.caption(f"Fuente oficial: SQLite | Base: {db.DB_PATH}")
    _mostrar_carga_plano()
    _mostrar_planos_cargados()
    app.st.divider()
    _mostrar_registro_asistido()
    app.st.divider()
    _mostrar_futuro_ocr_ia()


main()

