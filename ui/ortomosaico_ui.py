import plotly.graph_objects as go

from services import ortomosaico_service


ALTURA_VISTA_COMPLETA = 850
ALTURA_VISTA_AMPLIADA = 950


def construir_figura_ortomosaico(ortomosaico, altura=ALTURA_VISTA_COMPLETA):
    imagen = ortomosaico_service.imagen_data_uri(ortomosaico.ruta_preview)
    ancho = ortomosaico.ancho_preview
    alto = ortomosaico.alto_preview

    fig = go.Figure()
    fig.add_layout_image(
        dict(
            source=imagen,
            xref="x",
            yref="y",
            x=0,
            y=alto,
            sizex=ancho,
            sizey=alto,
            sizing="stretch",
            layer="below",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[],
            y=[],
            mode="markers",
            name="Puntos operacionales futuros",
            marker=dict(size=8, color="#DC2626"),
            hovertemplate="x=%{x}<br>y=%{y}<extra></extra>",
        )
    )
    fig.update_xaxes(
        range=[0, ancho],
        showgrid=False,
        zeroline=False,
        visible=False,
        constrain="domain",
    )
    fig.update_yaxes(
        range=[0, alto],
        showgrid=False,
        zeroline=False,
        visible=False,
        scaleanchor="x",
        scaleratio=1,
    )
    fig.update_layout(
        height=altura,
        margin=dict(l=0, r=0, t=0, b=0),
        dragmode="pan",
        hovermode="closest",
        showlegend=False,
        plot_bgcolor="#f8fafc",
        paper_bgcolor="#ffffff",
        autosize=True,
    )
    return fig


def config_plotly_interactivo():
    return {
        "scrollZoom": True,
        "displayModeBar": True,
        "displaylogo": False,
        "responsive": True,
        "doubleClick": "reset",
        "modeBarButtonsToAdd": [
            "zoom2d",
            "pan2d",
            "select2d",
            "lasso2d",
            "resetScale2d",
            "toImage",
        ],
        "toImageButtonOptions": {
            "format": "png",
            "filename": "ortomosaico_vista_mina",
            "height": 1200,
            "width": 1800,
            "scale": 2,
        },
    }


def renderizar_controles(st, ortomosaico):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Archivo maestro", ortomosaico.extension)
    col2.metric("Tamano maestro", ortomosaico_service.formato_tamano(ortomosaico.tamano_bytes))
    col3.metric("Resolucion TIFF", f"{ortomosaico.ancho} x {ortomosaico.alto}")
    col4.metric("Preview", f"{ortomosaico.ancho_preview} x {ortomosaico.alto_preview}")


def renderizar_visor(st, ortomosaico, altura=ALTURA_VISTA_COMPLETA):
    fig = construir_figura_ortomosaico(ortomosaico, altura=altura)
    st.plotly_chart(
        fig,
        use_container_width=True,
        config=config_plotly_interactivo(),
    )
