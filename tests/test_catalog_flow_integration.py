import pandas as pd

import app_perforacion
from services import kpi_service
from ui import forms_sections


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _FakeStreamlit:
    def __init__(self):
        self.selectbox_calls = []
        self.text_inputs = []

    def columns(self, count):
        if isinstance(count, int):
            return [_Context() for _ in range(count)]
        return [_Context() for _ in count]

    def selectbox(self, label, options, **kwargs):
        opciones = list(options)
        self.selectbox_calls.append((label, opciones))
        if label == "Operador":
            return opciones[0] if opciones else None
        return opciones[0] if opciones else ""

    def text_input(self, label, **kwargs):
        self.text_inputs.append((label, kwargs))
        return kwargs.get("value", "")

    def date_input(self, label, **_kwargs):
        return "2026-06-05"

    def image(self, *_args, **_kwargs):
        return None


def test_app_equipos_esperados_usa_catalog_service(monkeypatch):
    monkeypatch.setattr(
        app_perforacion.catalog_service,
        "equipos_esperados_activos",
        lambda: [("Modelo Catalogo", "EQ-01")],
    )

    assert app_perforacion.equipos_esperados() == [("Modelo Catalogo", "EQ-01")]


def test_kpi_resumen_operacional_usa_equipos_del_catalogo(monkeypatch):
    monkeypatch.setattr(
        kpi_service.catalog_service,
        "equipos_esperados_activos",
        lambda: [("Modelo Catalogo", "EQ-01")],
    )

    resumen = kpi_service.resumen_operacional_equipos(pd.DataFrame())

    assert resumen["Modelo equipo"].tolist() == ["Modelo Catalogo"]
    assert resumen["N\u00famero equipo"].tolist() == ["EQ-01"]


def test_formulario_equipo_operador_usa_catalogos(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(forms_sections, "st", fake_st)
    monkeypatch.setattr(
        forms_sections.catalog_service,
        "equipos_por_modelo_activos",
        lambda: {"Modelo Catalogo": ["EQ-01"]},
    )
    monkeypatch.setattr(
        forms_sections.catalog_service,
        "nombres_operadores_activos",
        lambda: ["Operador Catalogo"],
    )
    monkeypatch.setattr(
        forms_sections.catalog_service,
        "codigos_por_nombre_operador_activo",
        lambda: {"Operador Catalogo": "000001"},
    )
    monkeypatch.setattr(forms_sections, "ruta_imagen_equipo", lambda *_args: None)

    resultado = forms_sections.render_equipo_operador_fecha(lambda key: key)

    assert ("Modelo equipo", ["Modelo Catalogo"]) in fake_st.selectbox_calls
    assert ("Numero equipo", ["EQ-01"]) in fake_st.selectbox_calls
    assert ("Operador", ["Operador Catalogo"]) in fake_st.selectbox_calls
    assert resultado["modelo_equipo"] == "Modelo Catalogo"
    assert resultado["numero_equipo"] == "EQ-01"
    assert resultado["operador"] == "Operador Catalogo"
    assert resultado["codigo_operador"] == "000001"
