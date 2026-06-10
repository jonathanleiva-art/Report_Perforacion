from base64 import b64encode
from pathlib import Path
import sys

import pandas as pd
import streamlit.components.v1 as components


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
import db
from services import documentation_service
from ui.components import document_tile, section_header
from ui.formatting import dataframe_visible, texto_visible
from ui.page_header import render_page_header


CRITICIDADES = ["Baja", "Media", "Alta", "Crítica"]


def _opciones_columna(df, columna, base=None):
    valores = list(base or [])
    if not df.empty and columna in df.columns:
        valores.extend(df[columna].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].tolist())
    return list(dict.fromkeys(valores))


def _formatear_fecha(valor):
    fecha = pd.to_datetime(valor, errors="coerce")
    if pd.notna(fecha):
        return fecha.strftime("%Y-%m-%d %H:%M")
    return texto_visible(valor)


def _render_resumen(resumen):
    section_header("Resumen documental", "Estado general de documentos activos por tipo y criticidad.", kicker="Biblioteca")
    col1, col2, col3, col4 = app.st.columns(4)
    col1.metric("Total documentos", resumen["total"])
    col2.metric("Total PDF", resumen["pdf"])
    col3.metric("Críticos", resumen["criticos"])
    col4.metric("Categorías", resumen["categorias"])


def _render_agregar_documento():
    section_header("Agregar documento tecnico", "Carga controlada de archivos PDF para consulta operacional.", kicker="Carga")
    with app.st.form("form_agregar_documento_tecnico", clear_on_submit=True):
        titulo = app.st.text_input("Título del documento")
        col1, col2 = app.st.columns(2)
        tipo_documento = col1.selectbox("Tipo de documento", documentation_service.TIPOS_DOCUMENTO_BIBLIOTECA)
        equipo_asociado = col2.selectbox("Equipo asociado", documentation_service.EQUIPOS_BIBLIOTECA)

        col3, col4 = app.st.columns(2)
        categoria = col3.text_input("Categoría")
        criticidad = col4.selectbox("Criticidad", CRITICIDADES, index=1)

        observacion = app.st.text_area("Observación", height=90)
        archivo = app.st.file_uploader("Archivo PDF", type=["pdf"])
        guardar = app.st.form_submit_button("Cargar documento")

    if not guardar:
        return

    if archivo is None:
        app.st.error("Debes seleccionar un archivo PDF.")
        return

    try:
        documento = documentation_service.registrar_documento_biblioteca(
            {
                "titulo": titulo,
                "tipo_documento": tipo_documento,
                "equipo_asociado": equipo_asociado,
                "categoria": categoria,
                "criticidad": criticidad,
                "observacion": observacion,
            },
            contenido_pdf=archivo.getvalue(),
            nombre_archivo=archivo.name,
        )
    except (ValueError, OSError) as exc:
        app.st.error(texto_visible(str(exc)))
        return

    app.st.success(f"Documento cargado correctamente: {texto_visible(documento.get('titulo', titulo))}")


def _render_botones_equipo():
    section_header("Accesos rapidos por equipo", "Filtra la biblioteca usando equipos frecuentes.", kicker="Equipos")
    columnas = app.st.columns(3)
    for idx, equipo in enumerate(documentation_service.EQUIPOS_BIBLIOTECA):
        if columnas[idx % 3].button(equipo, key=f"biblioteca_equipo_rapido_{equipo}"):
            app.st.session_state["biblioteca_filtro_equipo_rapido"] = equipo
            app.st.rerun()


def _render_accesos_tipo_documento():
    section_header("Categorias documentales", "Accesos directos por familia documental.", kicker="Tipos")
    columnas = app.st.columns(4)
    for idx, tipo in enumerate(documentation_service.TIPOS_DOCUMENTO_BIBLIOTECA):
        with columnas[idx % 4]:
            document_tile(tipo, "Filtrar por tipo documental")
            if app.st.button("Ver documentos", key=f"biblioteca_tipo_rapido_{tipo}", use_container_width=True):
                app.st.session_state["biblioteca_tipo_documento"] = [tipo]
                app.st.rerun()


def _render_filtros(documentos_base):
    with app.st.sidebar:
        app.st.header("Filtros biblioteca")
        tipo = app.st.multiselect(
            "Tipo documento",
            _opciones_columna(documentos_base, "tipo_documento", documentation_service.TIPOS_DOCUMENTO_BIBLIOTECA),
            key="biblioteca_tipo_documento",
        )
        equipo_default = app.st.session_state.get("biblioteca_filtro_equipo_rapido")
        equipos = _opciones_columna(documentos_base, "equipo_asociado", documentation_service.EQUIPOS_BIBLIOTECA)
        equipo = app.st.multiselect(
            "Equipo asociado",
            equipos,
            default=[equipo_default] if equipo_default in equipos else [],
            key="biblioteca_equipo_asociado",
        )
        criticidad = app.st.multiselect("Criticidad", CRITICIDADES, key="biblioteca_criticidad")
        categoria = app.st.multiselect(
            "Categoría",
            _opciones_columna(documentos_base, "categoria"),
            key="biblioteca_categoria",
        )
        texto = app.st.text_input("Texto libre por título", key="biblioteca_texto_titulo")
        if app.st.button("Restablecer filtro equipo", key="biblioteca_reset_equipo"):
            app.st.session_state.pop("biblioteca_filtro_equipo_rapido", None)
            app.st.rerun()

    return {
        "tipo_documento": tipo,
        "equipo_asociado": equipo,
        "criticidad": criticidad,
        "categoria": categoria,
        "texto": texto,
    }


def _abrir_pdf(documento):
    bytes_pdf = documentation_service.leer_bytes_documento_biblioteca(documento)
    if not bytes_pdf:
        app.st.warning("No fue posible abrir el PDF seleccionado.")
        return
    base64_pdf = b64encode(bytes_pdf).decode("utf-8")
    components.html(
        f"""
        <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="760" style="border:1px solid #e2e8f0;"></iframe>
        """,
        height=780,
        scrolling=True,
    )


def _render_listado(documentos):
    section_header("Documentos tecnicos", "Listado filtrado y acciones disponibles por documento.", kicker="Listado")
    columnas = [
        "titulo",
        "tipo_documento",
        "equipo_asociado",
        "criticidad",
        "categoria",
        "fecha_carga",
    ]
    tabla = documentos[[col for col in columnas if col in documentos.columns]].copy()
    if "fecha_carga" in tabla.columns:
        tabla["fecha_carga"] = tabla["fecha_carga"].map(_formatear_fecha)
    app.st.dataframe(dataframe_visible(tabla), width="stretch", hide_index=True)

    for _, fila in documentos.iterrows():
        documento = fila.to_dict()
        with app.st.container(border=True):
            col1, col2, col3, col4 = app.st.columns([3, 1, 1, 1])
            with col1:
                document_tile(
                    texto_visible(documento.get("titulo")),
                    f"{texto_visible(documento.get('tipo_documento'))} | "
                    f"{texto_visible(documento.get('equipo_asociado'))} | "
                    f"{texto_visible(documento.get('criticidad'))}",
                )
            if col2.button("Abrir PDF", key=f"abrir_pdf_{documento.get('id_documento')}"):
                app.st.session_state["biblioteca_pdf_abierto"] = int(documento["id_documento"])
                app.st.rerun()
            col3.download_button(
                "Descargar",
                data=documentation_service.leer_bytes_documento_biblioteca(documento),
                file_name=documento.get("nombre_archivo") or "documento.pdf",
                mime="application/pdf",
                key=f"descargar_pdf_{documento.get('id_documento')}",
                use_container_width=True,
            )
            if col4.button("Desactivar", key=f"desactivar_pdf_{documento.get('id_documento')}"):
                documentation_service.desactivar_documento_biblioteca(documento["id_documento"])
                app.st.success("Documento desactivado correctamente.")
                app.st.rerun()


def _render_pdf_abierto(documentos):
    id_abierto = app.st.session_state.get("biblioteca_pdf_abierto")
    if not id_abierto or documentos.empty:
        return
    coincidencias = documentos[documentos["id_documento"].astype(int).eq(int(id_abierto))]
    if coincidencias.empty:
        return
    app.st.subheader("Vista PDF")
    _abrir_pdf(coincidencias.iloc[0].to_dict())


def _render_sugerencias():
    section_header("Documentos sugeridos para cargar", "Base documental recomendada para una operacion minera.", kicker="Pendientes")
    columnas = app.st.columns(2)
    for idx, sugerencia in enumerate(documentation_service.SUGERENCIAS_DOCUMENTOS_BIBLIOTECA):
        columnas[idx % 2].write(f"- {sugerencia}")


def main():
    if not app.requerir_acceso():
        return
    render_page_header(app.st, "Biblioteca Técnica")
    app.st.caption(
        f"Repositorio documental separado del histórico operacional | Tabla SQLite: biblioteca_documentos | Base: {db.DB_PATH.name}"
    )

    documentation_service.asegurar_estructura_biblioteca_tecnica()
    documentation_service.asegurar_tabla_biblioteca_documentos()

    _render_agregar_documento()
    app.st.divider()

    documentos_base = documentation_service.listar_documentos_biblioteca()
    _render_botones_equipo()
    _render_accesos_tipo_documento()
    filtros = _render_filtros(documentos_base)
    documentos = documentation_service.listar_documentos_biblioteca(**filtros)
    resumen = documentation_service.resumen_biblioteca_tecnica()

    _render_resumen(resumen)
    if documentos.empty:
        app.st.info("No hay documentos técnicos para los filtros seleccionados.")
    else:
        _render_listado(documentos)
        _render_pdf_abierto(documentos)

    app.st.divider()
    _render_sugerencias()


main()
