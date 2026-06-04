import pandas as pd

from ui.filters import _aplicar_filtros_dataframe


def test_aplicar_filtros_dataframe_usa_campos_normalizados_operacionales():
    df = pd.DataFrame([
        {
            "fecha_turno": pd.Timestamp("2024-10-01").date(),
            "equipo": "9271",
            "operador": "Operador A",
            "turno": "Dia",
            "metros": 100,
        },
        {
            "fecha_turno": pd.Timestamp("2024-12-01").date(),
            "equipo": "9272",
            "operador": "Operador B",
            "turno": "Noche",
            "metros": 200,
        },
    ])

    filtrado = _aplicar_filtros_dataframe(
        df,
        {
            "fecha_inicio": pd.Timestamp("2024-10-01").date(),
            "fecha_fin": pd.Timestamp("2024-10-31").date(),
            "operadores": ["Operador A"],
            "equipos": ["9271"],
            "turnos": ["Dia"],
        },
        [],
    )

    assert len(filtrado) == 1
    assert filtrado.iloc[0]["operador"] == "Operador A"
    assert float(filtrado.iloc[0]["metros"]) == 100.0


def test_aplicar_filtros_dataframe_devuelve_cero_si_operador_no_existe_en_rango():
    df = pd.DataFrame([
        {
            "fecha_turno": pd.Timestamp("2024-10-01").date(),
            "equipo": "9271",
            "operador": "Operador A",
            "turno": "Dia",
            "metros": 100,
        },
        {
            "fecha_turno": pd.Timestamp("2024-12-01").date(),
            "equipo": "9272",
            "operador": "Operador B",
            "turno": "Noche",
            "metros": 200,
        },
    ])

    filtrado = _aplicar_filtros_dataframe(
        df,
        {
            "fecha_inicio": pd.Timestamp("2024-10-01").date(),
            "fecha_fin": pd.Timestamp("2024-10-31").date(),
            "operadores": ["Operador B"],
        },
        [],
    )

    assert filtrado.empty
