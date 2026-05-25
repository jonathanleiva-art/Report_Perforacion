import streamlit as st
from unicodedata import normalize

from ui.formatting import texto_visible
from utils import limpiar_entero, unir_valores


def clave_detencion(valor):
    texto = texto_visible(valor).strip().lower()
    texto = normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.split())


def detenciones_seleccionadas_por_hora(tipo_detencion):
    asociaciones = {
        "horas_averia": ("averia", "averia mecanica"),
        "horas_combustible": ("combustible",),
        "horas_agua": ("agua", "relleno de agua", "abastecimiento agua"),
        "horas_colacion": ("colacion",),
        "horas_traslado": ("traslado",),
        "horas_standby": ("standby por falta de tajo/patio",),
        "horas_tronadura": ("tronadura",),
        "horas_mantencion": ("mantencion", "mantencion programada"),
        "horas_cambios_aceros": ("cambio de aceros", "cambios de aceros"),
        "horas_cambio_turno": ("cambio turno", "cambio de turno"),
        "horas_falta_operador": ("falta operador",),
        "horas_otros": ("otros",),
    }
    seleccionadas = {clave_detencion(detencion) for detencion in tipo_detencion}
    return {
        clave
        for clave, opciones in asociaciones.items()
        if any(opcion in seleccionadas for opcion in opciones)
    }


def alerta_horas_detencion_cero(etiqueta):
    st.warning(f"Seleccionaste esta detención, pero sus horas están en 0. ({etiqueta})")


def texto_lista(valores):
    return unir_valores(str(valor).strip() for valor in valores if str(valor).strip())


def texto_lista_enteros(valores):
    return unir_valores(limpiar_entero(valor) for valor in valores if str(valor).strip())


def dividir_valores_libres(valor):
    texto = str(valor).replace("/", ",")
    return [item.strip() for item in texto.split(",") if item.strip()]


def limpiar_valores_etiquetas(valores, enteros=False):
    limpios = []
    for valor in valores:
        for item in dividir_valores_libres(valor):
            limpio = limpiar_entero(item) if enteros else item
            if limpio and limpio not in limpios:
                limpios.append(limpio)

    return limpios
