import importlib
import sys

import streamlit as st


def test_importar_app_perforacion_no_configura_pagina(monkeypatch):
    llamadas = []

    def set_page_config_fake(**kwargs):
        llamadas.append(kwargs)

    monkeypatch.setattr(st, "set_page_config", set_page_config_fake)
    sys.modules.pop("app_perforacion", None)

    importlib.import_module("app_perforacion")

    assert llamadas == []


def test_configurar_pagina_principal_invoca_set_page_config(monkeypatch):
    import app_perforacion

    llamadas = []

    def set_page_config_fake(**kwargs):
        llamadas.append(kwargs)

    monkeypatch.setattr(app_perforacion.st, "set_page_config", set_page_config_fake)

    app_perforacion.configurar_pagina_principal()

    assert llamadas == [
        {
            "page_title": "Sistema de Gesti\u00f3n Operacional de Perforaci\u00f3n",
            "page_icon": "\u26cf\ufe0f",
            "layout": "wide",
        }
    ]
