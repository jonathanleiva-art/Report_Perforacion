import pandas as pd

import db
from services import data_quality_service


def crear_dataframe_calidad_completo():
    return pd.DataFrame(
        [
            {
                "Fecha turno": "2026-05-20",
                "Modelo equipo": "FlexiROC D65",
                "Número equipo": "9272",
                "Operador": "Ana Soto",
                "Turno": "Día",
                "Metros perforados": 100,
                "Horas efectivas perforando": 5,
                "Horas detención No efectivas": 3,
                "Horas detención mecánica": 4,
                "Mantención Programada": 0,
                "Disponibilidad %": 90,
                "Rendimiento m/h": 20,
            },
            {
                "Fecha turno": "",
                "Modelo equipo": "",
                "Número equipo": "",
                "Operador": "",
                "Turno": "",
                "Metros perforados": None,
                "Horas efectivas perforando": None,
                "Horas detención No efectivas": None,
                "Horas detención mecánica": None,
                "Mantención Programada": 1,
                "Disponibilidad %": 100,
                "Rendimiento m/h": 0,
            },
            {
                "Fecha turno": "2026-05-20",
                "Modelo equipo": "FlexiROC D65",
                "Número equipo": "9272",
                "Operador": "Ana Soto",
                "Turno": "Día",
                "Metros perforados": 0,
                "Horas efectivas perforando": 6,
                "Horas detención No efectivas": 3,
                "Horas detención mecánica": 3,
                "Mantención Programada": 1,
                "Disponibilidad %": 100,
                "Rendimiento m/h": 0,
            },
            {
                "Fecha turno": "2026-05-21",
                "Modelo equipo": "Sandvik D75KS",
                "Número equipo": "9245",
                "Operador": "Luis Perez",
                "Turno": "Noche",
                "Metros perforados": 200,
                "Horas efectivas perforando": 1,
                "Horas detención No efectivas": 5,
                "Horas detención mecánica": 6,
                "Mantención Programada": 0,
                "Disponibilidad %": 95,
                "Rendimiento m/h": 200,
            },
            {
                "Fecha turno": "2026-05-22",
                "Modelo equipo": "SmartROC D65",
                "Número equipo": "9339",
                "Operador": "Carlos Rondon",
                "Turno": "Día",
                "Metros perforados": 50,
                "Horas efectivas perforando": 5,
                "Horas detención No efectivas": 4,
                "Horas detención mecánica": 1,
                "Mantención Programada": 0,
                "Disponibilidad %": 100,
                "Rendimiento m/h": 0,
            },
        ]
    )


def crear_db_temporal(tmp_path, df):
    db_path = tmp_path / "reportes_perforacion.sqlite"
    db.crear_tablas(db_path=db_path, columnas=list(df.columns))
    db.insertar_dataframe_reportes(df, db_path=db_path, source="test")
    return db_path


def test_evaluar_calidad_datos_detecta_reglas_y_duplicados(tmp_path):
    df = crear_dataframe_calidad_completo()
    db_path = crear_db_temporal(tmp_path, df)

    resultado = data_quality_service.evaluar_calidad_datos(db_path=db_path)

    assert resultado["total_registros"] == 5
    assert resultado["errores"] > 0
    assert resultado["advertencias"] > 0
    assert resultado["reglas_no_evaluadas"] == 0
    assert not resultado["detalle"].empty
    assert "Duplicado por Fecha turno + Turno + Número equipo + Operador" in set(resultado["detalle"]["Regla"].astype(str))
    assert "Mantención Programada con horas efectivas > 0" in set(resultado["detalle"]["Regla"].astype(str))
    assert "Rendimiento m/h sobre 120" in set(resultado["detalle"]["Regla"].astype(str))
    assert resultado["recomendacion_operacional"]


def test_evaluar_calidad_datos_no_rompe_si_faltan_columnas(tmp_path):
    df = pd.DataFrame(
        [
            {
                "Fecha turno": "2026-05-20",
                "Modelo equipo": "FlexiROC D65",
                "Número equipo": "9272",
                "Operador": "Ana Soto",
                "Turno": "Día",
                "Metros perforados": 100,
                "Horas efectivas perforando": 5,
                "Horas detención No efectivas": 3,
                # faltan Horas detención mecánica y Mantención Programada
                "Disponibilidad %": 90,
                "Rendimiento m/h": 20,
            }
        ]
    )
    db_path = crear_db_temporal(tmp_path, df)

    resultado = data_quality_service.evaluar_calidad_datos(db_path=db_path)

    assert resultado["total_registros"] == 1
    assert resultado["reglas_no_evaluadas"] >= 1
    assert not resultado["detalle"].empty
    assert "NO_EVALUADA" in set(resultado["detalle"]["Estado"].astype(str))


def test_calcular_score_y_clasificacion_calidad():
    assert data_quality_service.clasificar_estado_calidad(95)["estado"] == "excelente"
    assert data_quality_service.clasificar_estado_calidad(80)["estado"] == "aceptable"
    assert data_quality_service.clasificar_estado_calidad(65)["estado"] == "observado"
    assert data_quality_service.clasificar_estado_calidad(50)["estado"] == "critico"

    df = crear_dataframe_calidad_completo()
    score = data_quality_service.calcular_score_calidad(df)
    assert isinstance(score, float)
    assert 0 <= score <= 100


def test_generar_resumen_ejecutivo_calidad_devuelve_top_problemas_y_criticos():
    df = crear_dataframe_calidad_completo()
    resumen = data_quality_service.generar_resumen_ejecutivo_calidad(df)

    assert "score" in resumen
    assert "estado" in resumen
    assert "resumen" in resumen
    assert "top_problemas" in resumen
    assert "registros_criticos" in resumen
    assert not resumen["resumen"].empty
    assert "Score calidad" in resumen["resumen"].columns
    assert len(resumen["top_problemas"]) <= 5
    assert "Estado predominante" in resumen["top_problemas"].columns
    assert "Recomendación operacional" in resumen["top_problemas"].columns
    assert "Recomendación operacional" in resumen["resumen"].columns
    assert resumen["recomendacion_operacional"]
    assert isinstance(resumen["registros_criticos"], pd.DataFrame)
