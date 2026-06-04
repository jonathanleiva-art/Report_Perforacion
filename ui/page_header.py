from ui.formatting import texto_visible


def render_page_header(st_module, titulo, subtitulo=""):
    st_module.markdown(
        f"""
        <div class="rp-page-header">
            <div class="rp-page-kicker">Módulo operacional</div>
            <h1>{texto_visible(titulo)}</h1>
            <p>{texto_visible(subtitulo) if subtitulo else ""}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
