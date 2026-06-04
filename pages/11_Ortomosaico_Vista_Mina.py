from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from ui.page_header import render_page_header
from services import ortomosaico_service
from ui import ortomosaico_ui


ORTOMOSAICOS_DIR = ROOT_DIR / "ortomosaicos"


def main():
    if not app.requerir_acceso():
        return
    render_page_header(app.st, "Ortomosaico Vista Mina")
    app.st.caption("Vista referencial de apoyo para ubicación y seguimiento de trabajos de perforación.")

    ORTOMOSAICOS_DIR.mkdir(parents=True, exist_ok=True)
    archivos = ortomosaico_service.listar_archivos_ortomosaico(ORTOMOSAICOS_DIR)
    if not archivos:
        app.st.info("No hay archivos de ortomosaico disponibles en la carpeta `ortomosaicos/`.")
        return

    seleccionado = app.st.selectbox(
        "Archivo disponible",
        archivos,
        format_func=lambda ruta: ruta.name,
    )

    try:
        ortomosaico = ortomosaico_service.obtener_ortomosaico(seleccionado)
    except Exception as exc:
        app.st.error(f"No fue posible preparar el ortomosaico: {exc}")
        app.st.code(str(seleccionado))
        return

    ortomosaico_ui.renderizar_controles(app.st, ortomosaico)

    app.st.subheader("Vista interactiva de alta resolucion")
    modo_vista = app.st.radio(
        "Modo de vista",
        ["Vista completa", "Vista ampliada"],
        horizontal=True,
        index=0,
        key="ortomosaico_modo_vista",
    )
    altura_visor = (
        ortomosaico_ui.ALTURA_VISTA_AMPLIADA
        if modo_vista == "Vista ampliada"
        else ortomosaico_ui.ALTURA_VISTA_COMPLETA
    )
    app.st.caption(
        "Use la rueda del mouse para zoom, arrastre para desplazarse y la barra Plotly para resetear, exportar o ampliar la vista."
    )
    ortomosaico_ui.renderizar_visor(app.st, ortomosaico, altura=altura_visor)

    with app.st.expander("Detalle del archivo y capas futuras"):
        app.st.write(f"Fuente maestra: `{ortomosaico.ruta_maestra}`")
        app.st.write(f"Vista previa usada por Streamlit: `{ortomosaico.ruta_preview}`")
        app.st.write("El archivo TIFF original se conserva como fuente maestra.")
        app.st.write("La arquitectura queda preparada para puntos, coordenadas, pozos, equipos y poligonos de avance.")


if __name__ == "__main__":
    main()

