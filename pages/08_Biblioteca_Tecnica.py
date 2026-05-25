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
from ui.formatting import dataframe_visible, texto_visible


def _multiselect_todos(label, opciones, key):
    opciones = list(opciones or [])
    return app.st.multiselect(
        label,
        opciones,
        default=opciones,
        format_func=texto_visible,
        key=key,
    )


def _filtros_sidebar():
    categorias = documentation_service.obtener_categorias_documentales()
    fabricantes = documentation_service.obtener_fabricantes_documentales()
    equipos = documentation_service.obtener_equipos_documentales()
    criticidades = documentation_service.obtener_criticidades_documentales()

    with app.st.sidebar:
        app.st.header("Filtros bibliográficos")
        categoria = _multiselect_todos("Categoría", categorias, "biblioteca_categoria")
        fabricante = _multiselect_todos("Fabricante", fabricantes, "biblioteca_fabricante")
        equipo = _multiselect_todos("Equipo", equipos, "biblioteca_equipo")
        criticidad = _multiselect_todos("Criticidad", criticidades, "biblioteca_criticidad")
        buscar = app.st.text_input("Buscar por palabras clave", key="biblioteca_buscar")

    return {
        "categoria": categoria,
        "fabricante": fabricante,
        "equipo": equipo,
        "criticidad": criticidad,
        "buscar": buscar.strip(),
    }


def _resumen_indicadores(df):
    total = len(df)
    pdf = int(df["extension"].astype(str).str.lower().eq(".pdf").sum()) if "extension" in df.columns and not df.empty else 0
    criticos = int(df["criticidad"].astype(str).eq("Crítica").sum()) if "criticidad" in df.columns and not df.empty else 0
    categorias = int(df["categoria"].astype(str).nunique()) if "categoria" in df.columns and not df.empty else 0
    col1, col2, col3, col4 = app.st.columns(4)
    col1.metric("Documentos", total)
    col2.metric("PDF", pdf)
    col3.metric("Críticos", criticos)
    col4.metric("Categorías", categorias)


def _resumen_criticidad(df):
    conteos = {nivel: 0 for nivel in ["Crítica", "Alta", "Media", "Baja"]}
    if not df.empty and "criticidad" in df.columns:
        for nivel in conteos:
            conteos[nivel] = int((df["criticidad"].astype(str) == nivel).sum())

    colores = {
        "Crítica": "#DC2626",
        "Alta": "#D97706",
        "Media": "#2563EB",
        "Baja": "#16A34A",
    }
    cols = app.st.columns(4)
    for col, nivel in zip(cols, conteos):
        col.markdown(
            f"""
            <div style="border-left: 6px solid {colores[nivel]}; padding: 0.65rem 0.9rem; background: #f8fafc; min-height: 74px;">
                <div style="font-size: 0.85rem; color: #64748b;">Criticidad</div>
                <div style="font-size: 1.05rem; font-weight: 700; color: #0f172a;">{nivel}</div>
                <div style="font-size: 1.35rem; font-weight: 700; color: {colores[nivel]};">{conteos[nivel]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _ruta_doc_filtro(df):
    seleccionado = app.st.session_state.get("biblioteca_documento_seleccionado", "")
    if not seleccionado or df.empty:
        return {}
    coincidencia = df[df["ruta_relativa"].astype(str).eq(str(seleccionado))]
    if coincidencia.empty:
        return {}
    return coincidencia.iloc[0].to_dict()


def _render_pdf(documento):
    bytes_pdf = documentation_service.leer_bytes_documento(documento)
    if not bytes_pdf:
        app.st.warning("No fue posible abrir el archivo PDF.")
        return
    base64_pdf = b64encode(bytes_pdf).decode("utf-8")
    components.html(
        f"""
        <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" style="border:1px solid #e2e8f0;"></iframe>
        """,
        height=820,
        scrolling=True,
    )


def _previsualizar(documento):
    if not documento:
        return

    app.st.subheader("Vista documental")
    app.st.dataframe(
        dataframe_visible(pd.DataFrame([documento])),
        width="stretch",
        hide_index=True,
    )

    ruta_absoluta = documento.get("ruta_absoluta", "")
    if not ruta_absoluta:
        app.st.warning("No se encontró la ruta del documento.")
        return

    col1, col2 = app.st.columns([1, 1])
    with col1:
        if app.st.button("Abrir PDF", key=f"biblioteca_abrir_{documento.get('id', 'x')}"):
            app.st.session_state["biblioteca_documento_seleccionado"] = documento.get("ruta_relativa", "")
            app.st.rerun()
    with col2:
        bytes_doc = documentation_service.leer_bytes_documento(documento)
        app.st.download_button(
            "Descargar documento",
            data=bytes_doc,
            file_name=Path(ruta_absoluta).name,
            mime=documento.get("mimetype", "application/octet-stream"),
            use_container_width=True,
            key=f"biblioteca_descarga_{documento.get('id', 'x')}",
        )

    if Path(ruta_absoluta).suffix.lower() == ".pdf":
        _render_pdf(documento)
    elif Path(ruta_absoluta).suffix.lower() in {".md", ".txt"}:
        try:
            texto = Path(ruta_absoluta).read_text(encoding="utf-8")
        except Exception:
            texto = ""
        if texto:
            app.st.text_area("Contenido", value=texto[:5000], height=400)


def _tarjeta_documento(documento):
    with app.st.container(border=True):
        col1, col2 = app.st.columns([3, 1])
        with col1:
            app.st.markdown(f"### {texto_visible(documento.get('nombre', 'Documento'))}")
            app.st.caption(
                f"{texto_visible(documento.get('categoria', ''))} | "
                f"{texto_visible(documento.get('fabricante', ''))} | "
                f"{texto_visible(documento.get('equipo_asociado', ''))}"
            )
            app.st.write(
                f"Versión: {texto_visible(documento.get('version', ''))} | "
                f"Tipo: {texto_visible(documento.get('tipo_documento', ''))} | "
                f"Fecha: {texto_visible(documento.get('fecha_documento', ''))}"
            )
            app.st.caption(f"Palabras clave: {texto_visible(documento.get('palabras_clave', ''))}")
            app.st.caption(f"Criticidad: {texto_visible(documento.get('criticidad', ''))}")
            if texto_visible(documento.get("autor_responsable", "")):
                app.st.caption(f"Autor / responsable: {texto_visible(documento.get('autor_responsable', ''))}")
        with col2:
            if app.st.button("Ver", key=f"biblioteca_ver_{documento.get('id')}"):
                app.st.session_state["biblioteca_documento_seleccionado"] = documento.get("ruta_relativa", "")
                app.st.rerun()
            if app.st.download_button(
                "Descargar",
                data=documentation_service.leer_bytes_documento(documento),
                file_name=Path(documento.get("ruta_absoluta", "")).name,
                mime=documento.get("mimetype", "application/octet-stream"),
                use_container_width=True,
                key=f"biblioteca_download_{documento.get('id')}",
            ):
                pass


def main():
    app.st.title("Biblioteca Técnica Operacional")
    app.st.caption(
        f"Repositorio documental separado del histórico operacional | Fuente SQLite: {db.DB_PATH.name}"
    )

    documentation_service.asegurar_estructura_documental()
    filtros = _filtros_sidebar()
    documentos = documentation_service.listar_documentos(
        categoria=filtros["categoria"],
        fabricante=filtros["fabricante"],
        equipo=filtros["equipo"],
        criticidad=filtros["criticidad"],
        buscar=filtros["buscar"],
    )
    resumen = documentation_service.resumen_biblioteca_documental()

    _resumen_indicadores(documentos)
    _resumen_criticidad(documentos)

    if documentos.empty:
        app.st.info("No hay documentos cargados en la biblioteca técnica con los filtros actuales.")
    else:
        app.st.subheader("Documentos disponibles")
        for _, fila in documentos.iterrows():
            _tarjeta_documento(fila.to_dict())

    app.st.divider()
    seleccion = _ruta_doc_filtro(documentos)
    if seleccion:
        _previsualizar(seleccion)
    else:
        app.st.info("Selecciona un documento para ver su vista previa y metadata documental.")

    if resumen["detalle"].empty:
        app.st.caption("La biblioteca está lista para recibir documentos y metadata documental.")


main()
