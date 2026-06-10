from html import escape

from ui.formatting import texto_visible
from ui.theme import aplicar_tema_profesional


def render_page_header(st_module, titulo, subtitulo=""):
    aplicar_tema_profesional()
    titulo_visible = escape(texto_visible(titulo))
    subtitulo_visible = escape(texto_visible(subtitulo)) if subtitulo else ""
    st_module.markdown(
        f"""
        <div class="rp-page-header">
            <div class="rp-page-kicker">Modulo operacional</div>
            <h1>{titulo_visible}</h1>
            <p style="color:rgba(255,255,255,0.72);font-size:0.85rem;margin:0.25rem 0 0;">{subtitulo_visible}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

