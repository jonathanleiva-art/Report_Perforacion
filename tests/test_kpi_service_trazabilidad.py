import pandas as pd

from services.kpi_service import comparar_base_vs_analisis_kpis, trazabilidad_kpis_productivos


def test_trazabilidad_kpis_productivos_calcula_totales_y_excluidos():
    df = pd.DataFrame(
        [
            {
                "Fecha turno": "2026-05-01",
                "Turno": "Noche",
                "Modelo equipo": "Sandvik D75KS",
                "Número equipo": "9245",
                "Operador": "Operador Productivo",
                "Tipo de perforacion": "Produccion",
                "Tipo detencion": "Colacion",
                "Metros perforados": 100,
                "Horas efectivas perforando": 5,
            },
            {
                "Fecha turno": "2026-05-02",
                "Turno": "Noche",
                "Equipo": "FlexiROC D65 9272",
                "Operador": "Operador Sin Horas",
                "Tipo de perforacion": "Buffer",
                "Tipo detencion": "Traslado",
                "Metros perforados": 50,
                "Horas efectivas perforando": 0,
            },
            {
                "Fecha turno": "2026-05-03",
                "Turno": "Dia",
                "Equipo": "SmartROC D65 9339",
                "Operador": "Operador Sin Metros",
                "Tipo de perforacion": "Produccion",
                "Tipo detencion": "Standby",
                "Metros perforados": 0,
                "Horas efectivas perforando": 3,
            },
        ]
    )

    resultado = trazabilidad_kpis_productivos(df)

    assert resultado["metros_totales"] == 150
    assert resultado["metros_productivos"] == 100
    assert resultado["metros_excluidos"] == 50
    assert resultado["horas_efectivas_totales"] == 8
    assert resultado["horas_efectivas_productivas"] == 5
    assert resultado["horas_excluidas"] == 3
    assert resultado["registros_totales"] == 3
    assert resultado["registros_productivos"] == 1
    assert resultado["registros_excluidos"] == 2
    assert set(resultado["detalle_registros_excluidos"]["Motivo exclusión"]) == {
        "Metros > 0 sin horas",
        "Horas > 0 sin metros",
    }


def test_trazabilidad_kpis_productivos_detecta_ceros_negativos_e_invalidos():
    df = pd.DataFrame(
        [
            {"Metros perforados": 0, "Horas efectivas perforando": 0},
            {"Metros perforados": -10, "Horas efectivas perforando": 2},
            {"Metros perforados": "abc", "Horas efectivas perforando": 1},
            {"Metros perforados": 20, "Horas efectivas perforando": "sin dato"},
        ]
    )

    resultado = trazabilidad_kpis_productivos(df)

    assert resultado["registros_productivos"] == 0
    assert resultado["registros_excluidos"] == 4
    assert list(resultado["detalle_registros_excluidos"]["Motivo exclusión"]) == [
        "Sin metros y sin horas",
        "Datos negativos",
        "Datos inválidos",
        "Datos inválidos",
    ]


def test_trazabilidad_kpis_productivos_no_muta_dataframe_original():
    df = pd.DataFrame(
        {
            "Metros perforados": ["100", "0"],
            "Horas efectivas perforando": ["5", "0"],
        }
    )
    original = df.copy(deep=True)

    trazabilidad_kpis_productivos(df)

    pd.testing.assert_frame_equal(df, original)


def test_trazabilidad_kpis_productivos_devuelve_estructura_estable_sin_columnas():
    df = pd.DataFrame({"Operador": ["Uno", "Dos"]})

    resultado = trazabilidad_kpis_productivos(df)

    assert resultado["metros_totales"] == 0
    assert resultado["horas_efectivas_totales"] == 0
    assert resultado["registros_totales"] == 2
    assert resultado["registros_excluidos"] == 2
    assert list(resultado["detalle_registros_excluidos"].columns) == [
        "Fecha turno",
        "Turno",
        "Equipo",
        "Operador",
        "Tipo de perforación",
        "Tipo detención",
        "Metros perforados",
        "Horas efectivas perforando",
        "Motivo exclusión",
    ]


def test_trazabilidad_kpis_productivos_devuelve_estructura_estable_con_dataframe_vacio():
    resultado = trazabilidad_kpis_productivos(pd.DataFrame())

    assert resultado["registros_totales"] == 0
    assert resultado["registros_productivos"] == 0
    assert resultado["registros_excluidos"] == 0
    assert resultado["detalle_registros_excluidos"].empty


def test_comparar_base_vs_analisis_kpis_detecta_registro_ausente_y_causa_por_filtro():
    df_base = pd.DataFrame(
        [
            {
                "id": 931,
                "Fecha turno": "2026-05-19",
                "Turno": "Noche",
                "Modelo equipo": "Sandvik D75KS",
                "Número equipo": "9245",
                "Operador": "Jonathan Leiva",
                "Tipo de perforacion": "Produccion",
                "Tipo detencion": "Combustible, Traslado, Otros",
                "Metros perforados": 564.6,
                "Horas efectivas perforando": 10,
            },
            {
                "id": 932,
                "Fecha turno": "2026-05-19",
                "Turno": "Noche",
                "Modelo equipo": "Sandvik D75KS",
                "Número equipo": "9277",
                "Operador": "Carlos Rondon",
                "Tipo de perforacion": "Produccion",
                "Metros perforados": 100,
                "Horas efectivas perforando": 5,
            },
        ]
    )
    df_analisis = df_base[df_base["id"].eq(932)].copy()

    resultado = comparar_base_vs_analisis_kpis(
        df_base,
        df_analisis,
        filtros={"operadores": ["Carlos Rondon"]},
    )

    assert resultado["registros_base"] == 2
    assert resultado["registros_analisis"] == 1
    assert resultado["registros_ausentes"] == 1
    assert resultado["metros_ausentes"] == 564.6
    assert resultado["horas_ausentes"] == 10
    detalle = resultado["detalle_registros_ausentes"]
    assert detalle.iloc[0]["id"] == 931
    assert detalle.iloc[0]["Equipo"] == "Sandvik D75KS 9245"
    assert detalle.iloc[0]["Posible causa"] == "Filtro operador"
