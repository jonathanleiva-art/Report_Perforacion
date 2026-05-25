import pandas as pd

from data import preparar_dataframe


def test_preparar_dataframe_normaliza_columnas_mojibake():
    df = pd.DataFrame([
        {
            "Número equipo": "9274.0",
            "Petróleo litros": "120",
            "Tipo detención": "mantencion",
        }
    ])

    resultado = preparar_dataframe(df)

    assert "Número equipo" in resultado.columns
    assert "Petróleo litros" in resultado.columns
    assert "Tipo detención" in resultado.columns
    assert resultado.iloc[0]["Número equipo"] == "9274"
    assert resultado.iloc[0]["Petróleo litros"] == 120
    assert resultado.iloc[0]["Tipo detención"] == "Mantención Programada"


def test_preparar_dataframe_fusiona_columnas_duplicadas():
    df = pd.DataFrame(
        [["Ana", "Ana", "10", "2.5"]],
        columns=["Operador", "Operador", "Metros perforados", "Metros perforados"],
    )

    resultado = preparar_dataframe(df)

    assert list(resultado.columns).count("Operador") == 1
    assert list(resultado.columns).count("Metros perforados") == 1
    assert resultado.iloc[0]["Operador"] == "Ana"
    assert resultado.iloc[0]["Metros perforados"] == 12.5


def test_preparar_dataframe_convierte_columnas_numericas():
    df = pd.DataFrame([
        {
            "Metros perforados": "15,5",
            "Horas efectivas perforando": ["2", "3.5"],
            "Total horas ingresadas": None,
        }
    ])

    resultado = preparar_dataframe(df)

    assert resultado.iloc[0]["Metros perforados"] == 0
    assert resultado.iloc[0]["Horas efectivas perforando"] == 5.5
    assert resultado.iloc[0]["Total horas ingresadas"] == 0


def test_preparar_dataframe_preserva_columnas_esperadas():
    df = pd.DataFrame([
        {
            "Fecha turno": "2026-05-23",
            "Modelo equipo": "PV271",
            "Número equipo": "9274",
            "Operador": "Valeria Millan",
            "Turno": "Noche",
        }
    ])

    resultado = preparar_dataframe(df)

    for columna in [
        "Fecha turno",
        "Modelo equipo",
        "Número equipo",
        "Operador",
        "Turno",
        "Equipo",
    ]:
        assert columna in resultado.columns
    assert resultado.iloc[0]["Equipo"] == "PV271 9274"


def test_preparar_dataframe_maneja_valores_vacios():
    df = pd.DataFrame([
        {
            "Operador": None,
            "Turno": float("nan"),
            "Banco": "",
            "Metros perforados": None,
        }
    ])

    resultado = preparar_dataframe(df)

    assert resultado.iloc[0]["Operador"] == ""
    assert resultado.iloc[0]["Turno"] == ""
    assert resultado.iloc[0]["Banco"] == ""
    assert resultado.iloc[0]["Metros perforados"] == 0


def test_preparar_dataframe_normaliza_texto_visible():
    df = pd.DataFrame([
        {
            "Turno": " Día ",
            "Tipo detención": "geologia, agua, sin marcacion",
        }
    ])

    resultado = preparar_dataframe(df)

    assert resultado.iloc[0]["Turno"] == "Día"
    assert resultado.iloc[0]["Tipo detención"] == (
        "Geología, Relleno de agua, Standby por falta de tajo/Patio"
    )
