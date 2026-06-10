import pandas as pd

from services.kpi_service import (
    calcular_kpi_operacional_productivo,
    detectar_registros_kpi_sospechosos,
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
        "N\u00famero equipo",
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


def test_kpi_operacional_productivo_equipo_9339_fuera_de_servicio():
    resultado = calcular_kpi_operacional_productivo(
        metros=0,
        pozos=0,
        horas_efectivas=6,
        horas_turno=12,
        horas_traslado=3.75,
        horas_averia=6,
        horas_otros=2.25,
        estatus_equipo="Fuera de servicio",
        observaciones="Equipo trasladado a taller de mantencion",
    )

    assert resultado["horas_efectivas_productivas"] == 0
    assert resultado["utilizacion_productiva"] == 0
    assert resultado["disponibilidad"] == 50
    assert resultado["rendimiento"] == 0
    assert resultado["caso_no_productivo"] is True
    assert resultado["clasificacion_operacional"] == "No productivo"
    assert "Registro con horas efectivas pero sin metros perforados" in resultado["alertas_coherencia"]


def test_detector_registros_kpi_sospechosos_identifica_he_sin_produccion_y_texto_no_productivo():
    df = pd.DataFrame([
        {
            "Fecha turno": "2026-05-01",
            "Turno": "Día",
            "Modelo equipo": "SmartROC D65",
            "Número equipo": "9339",
            "Operador": "Operador prueba",
            "Metros perforados": 0,
            "Pozos perforados turno": 0,
            "Horas efectivas perforando": 6,
            "Utilización": 50,
            "Estatus del Equipo": "Fuera de servicio",
            "Observaciones": "Traslado a taller de mantencion",
        },
        {
            "Fecha turno": "2026-05-01",
            "Turno": "Día",
            "Modelo equipo": "SmartROC D65",
            "Número equipo": "9340",
            "Operador": "Operador prueba",
            "Metros perforados": 120,
            "Pozos perforados turno": 4,
            "Horas efectivas perforando": 6,
            "Utilización": 60,
            "Estatus del Equipo": "Operativo",
            "Observaciones": "",
        },
    ])

    sospechosos = detectar_registros_kpi_sospechosos(df)

    assert len(sospechosos) == 1
    assert sospechosos.iloc[0]["Equipo"] == "SmartROC D65 9339"
    assert "metros = 0 y utilizacion > 0" in sospechosos.iloc[0]["Motivos"]
    assert "pozos = 0 y HE > 0" in sospechosos.iloc[0]["Motivos"]
