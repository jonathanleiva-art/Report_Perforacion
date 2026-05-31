import pandas as pd

from services.kpi_service import (
    calcular_rendimiento_productivo,
    calcular_resumen_productivo_por_equipo,
    calcular_resumen_productivo_por_operador,
    calcular_totales_productivos,
    obtener_registros_productivos,
    obtener_series_productivas,
)


def _df_kpi():
    return pd.DataFrame(
        [
            {
                "Fecha turno": "2026-05-01",
                "Modelo equipo": "Sandvik D75KS",
                "Número equipo": "9245",
                "Equipo": "Sandvik D75KS 9245",
                "Operador": "Jonathan Leiva",
                "Metros perforados": 100,
                "Horas efectivas perforando": 5,
            },
            {
                "Fecha turno": "2026-05-02",
                "Modelo equipo": "Sandvik D75KS",
                "Número equipo": "9245",
                "Equipo": "Sandvik D75KS 9245",
                "Operador": "Jonathan Leiva",
                "Metros perforados": 50,
                "Horas efectivas perforando": 0,
            },
            {
                "Fecha turno": "2026-05-03",
                "Modelo equipo": "FlexiROC D65",
                "Número equipo": "9272",
                "Equipo": "FlexiROC D65 9272",
                "Operador": "Carlos Rondon",
                "Metros perforados": 150,
                "Horas efectivas perforando": 10,
            },
            {
                "Fecha turno": "2026-05-04",
                "Modelo equipo": "FlexiROC D65",
                "Número equipo": "9272",
                "Equipo": "FlexiROC D65 9272",
                "Operador": "Carlos Rondon",
                "Metros perforados": 0,
                "Horas efectivas perforando": 4,
            },
        ]
    )


def test_obtener_series_productivas_aplica_regla_unica_y_no_muta():
    df = _df_kpi()
    original = df.copy(deep=True)

    series = obtener_series_productivas(df)

    assert series["metros"].tolist() == [100, 50, 150, 0]
    assert series["horas_efectivas"].tolist() == [5, 0, 10, 4]
    assert series["productivos"].tolist() == [True, False, True, False]
    pd.testing.assert_frame_equal(df, original)


def test_obtener_registros_productivos_devuelve_copia_filtrada():
    df = _df_kpi()

    productivos = obtener_registros_productivos(df)
    productivos.loc[productivos.index[0], "Metros perforados"] = 999

    assert len(productivos) == 2
    assert df.iloc[0]["Metros perforados"] == 100
    assert productivos["Operador"].tolist() == ["Jonathan Leiva", "Carlos Rondon"]


def test_calcular_totales_productivos_devuelve_estructura_estable():
    resultado = calcular_totales_productivos(_df_kpi())

    assert resultado == {
        "metros_productivos": 250.0,
        "horas_efectivas_productivas": 15.0,
        "registros_productivos": 2,
        "rendimiento_m_h": 16.67,
    }


def test_calcular_rendimiento_productivo_global_y_agrupado():
    df = _df_kpi()

    rendimiento = calcular_rendimiento_productivo(df)
    por_operador = calcular_rendimiento_productivo(df, ["Operador"]).sort_values("Operador").reset_index(drop=True)

    assert round(rendimiento, 2) == 16.67
    assert list(por_operador.columns) == [
        "Operador",
        "Metros perforados",
        "Horas efectivas perforando",
        "Rendimiento m/h",
        "Registros productivos",
    ]
    assert por_operador.loc[0, "Operador"] == "Carlos Rondon"
    assert por_operador.loc[0, "Metros perforados"] == 150
    assert por_operador.loc[0, "Horas efectivas perforando"] == 10
    assert por_operador.loc[0, "Rendimiento m/h"] == 15
    assert por_operador.loc[1, "Rendimiento m/h"] == 20


def test_calcular_resumen_productivo_por_equipo_y_operador():
    df = _df_kpi()

    equipos = calcular_resumen_productivo_por_equipo(df).sort_values("Equipo").reset_index(drop=True)
    operadores = calcular_resumen_productivo_por_operador(df).sort_values("Operador").reset_index(drop=True)

    assert list(equipos.columns) == [
        "Modelo equipo",
        "NÃºmero equipo",
        "Equipo",
        "Metros perforados",
        "Horas efectivas perforando",
        "Rendimiento m/h",
        "Registros productivos",
    ]
    assert equipos["Equipo"].tolist() == ["FlexiROC D65 9272", "Sandvik D75KS 9245"]
    assert equipos["Metros perforados"].tolist() == [150, 100]
    assert equipos["Horas efectivas perforando"].tolist() == [10, 5]
    assert equipos["Rendimiento m/h"].tolist() == [15, 20]
    assert operadores["Operador"].tolist() == ["Carlos Rondon", "Jonathan Leiva"]
    assert operadores["Registros productivos"].tolist() == [1, 1]


def test_api_central_maneja_dataframe_vacio_y_columnas_faltantes():
    df = pd.DataFrame({"Operador": ["Uno", "Dos"]})

    assert obtener_registros_productivos(df).empty
    assert calcular_totales_productivos(df) == {
        "metros_productivos": 0.0,
        "horas_efectivas_productivas": 0.0,
        "registros_productivos": 0,
        "rendimiento_m_h": 0.0,
    }
    assert calcular_rendimiento_productivo(df) == 0.0
    assert calcular_rendimiento_productivo(df, ["Operador"]).empty
    assert calcular_resumen_productivo_por_equipo(pd.DataFrame()).empty
    assert calcular_resumen_productivo_por_operador(pd.DataFrame()).empty
